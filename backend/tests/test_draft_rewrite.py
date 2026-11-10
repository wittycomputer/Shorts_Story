"""Catch explicit rewrite regressions without loading ML libraries.

These checks cover length, paragraph provenance, and obvious qualifier losses.
They do not establish that an arbitrary generated claim is factually correct.
"""
import copy
from contextlib import nullcontext
import json
import sys
from threading import Event
from types import ModuleType, SimpleNamespace

import pytest

import inference


@pytest.fixture
def rewrite_project():
    scenes = [
        dict(id=1, narration='다회용 컵을 빌립니다.', caption='직접 수정한 첫 제목',
             image_prompt_en='a user edited reusable cup illustration', source_ids=['P1']),
        dict(id=2, narration='사용한 컵을 반납합니다.', caption='직접 수정한 둘째 제목',
             image_prompt_en='a user edited campus return station', source_ids=['P2']),
    ]
    return dict(
        id='e' * 32, owner_uid='rewrite-test-owner', status='queued',
        title='Rewrite regression', target_seconds=60, style='explain',
        text='학교는 다회용 컵을 빌려 주고 회수한 컵을 세척합니다. 반납 장소도 운영합니다.',
        paragraphs=[
            dict(id='P1', text='학교는 다회용 컵을 빌려 주며, 반납된 컵을 세척하여 다시 제공합니다.'),
            dict(id='P2', text='학생은 사용한 컵을 반납하며, 반납 장소와 세척 및 회수 과정을 함께 운영합니다.'),
        ],
        scenes=scenes, warnings=[], result=None, source='test fixture',
        created_at=0, updated_at=0,
    )


@pytest.fixture
def fake_generator(monkeypatch):
    """Exercise the production retry/parser path using only in-memory token IDs."""
    def install(responses):
        state = SimpleNamespace(prompts=[], generate_calls=0, releases=0)
        outputs = iter(json.dumps({'scenes': scenes}, ensure_ascii=False) for scenes in responses)

        class Inputs(dict):
            def __init__(self):
                self.input_ids = SimpleNamespace(shape=(1, 1))
                super().__init__(input_ids=self.input_ids)

            def to(self, device):
                assert device == 'fake-cpu'
                return self

        class Tokenizer:
            def apply_chat_template(self, messages, **_):
                # Copy: production appends feedback to the same messages list.
                state.prompts.append(copy.deepcopy(messages))
                return 'in-memory prompt'

            def __call__(self, prompt, **_):
                assert prompt == 'in-memory prompt'
                return Inputs()

            def decode(self, tokens, **_):
                assert len(tokens) == 1
                return tokens[0]

        class Model:
            device = 'fake-cpu'

            def generate(self, **_):
                state.generate_calls += 1
                # One prompt token precedes the generated JSON, as in production.
                return [[0, next(outputs)]]

        def tokenizer_loader(location, **kwargs):
            assert location == 'in-memory-local-model'
            assert kwargs['local_files_only'] is True
            return Tokenizer()

        def model_loader(location, **kwargs):
            assert location == 'in-memory-local-model'
            assert kwargs['local_files_only'] is True
            return Model()

        fake_torch = ModuleType('torch')
        fake_torch.cuda = SimpleNamespace(is_available=lambda: False)
        fake_torch.float32 = 'fake-float32'
        fake_torch.inference_mode = nullcontext
        fake_transformers = ModuleType('transformers')
        fake_transformers.AutoTokenizer = SimpleNamespace(from_pretrained=tokenizer_loader)
        fake_transformers.AutoModelForCausalLM = SimpleNamespace(from_pretrained=model_loader)
        fake_transformers.BitsAndBytesConfig = SimpleNamespace
        fake_transformers.StoppingCriteria = type('StoppingCriteria', (), {})
        fake_transformers.StoppingCriteriaList = list
        monkeypatch.setitem(sys.modules, 'torch', fake_torch)
        monkeypatch.setitem(sys.modules, 'transformers', fake_transformers)
        monkeypatch.setattr(inference, 'model_path', lambda _role: 'in-memory-local-model')

        def release():
            state.releases += 1

        monkeypatch.setattr(inference, 'release_memory', release)
        return state

    return install


def test_copied_rewrite_is_retried_and_valid_budget_keeps_user_visual_edits(
    rewrite_project, fake_generator,
):
    existing = rewrite_project['scenes']
    original = copy.deepcopy(rewrite_project)
    revised = [
        {**existing[0],
         'narration': '학교는 다회용 컵을 빌려 주고 학생은 사용한 컵을 반납합니다. 회수한 컵은 세척한 뒤 다시 제공합니다.',
         'caption': '모델이 바꾸려는 첫 제목', 'image_prompt_en': 'an unwanted replacement image',
         'source_ids': ['P1']},
        {**existing[1],
         'narration': '학생은 사용한 컵을 반납 장소에 돌려줍니다. 반납 장소와 세척 및 회수 과정을 함께 운영합니다.',
         'caption': '모델이 바꾸려는 둘째 제목', 'image_prompt_en': 'another unwanted replacement image',
         'source_ids': ['P2']},
    ]
    budget = sum(len(scene['narration']) for scene in revised)
    copied_length = sum(len(scene['narration']) for scene in existing)
    assert copied_length < budget * 0.90
    state = fake_generator([copy.deepcopy(existing), revised])

    result = inference.generate_draft(
        rewrite_project, lambda *_: None, Event(),
        narration_characters=budget, existing_scenes=existing,
    )

    assert state.generate_calls == 2
    assert len(state.prompts) == 2
    feedback = state.prompts[1]
    assert [message['role'] for message in feedback] == ['system', 'user', 'assistant', 'user']
    assert json.loads(feedback[-2]['content'])['scenes'] == existing
    assert str(copied_length) in feedback[-1]['content']
    assert str(budget) in feedback[-1]['content']
    assert '90~110%' in feedback[-1]['content']
    assert [scene['narration'] for scene in result] == [scene['narration'] for scene in revised]
    assert [scene['source_ids'] for scene in result] == [scene['source_ids'] for scene in revised]
    for actual, user_edited in zip(result, existing):
        assert actual['id'] == user_edited['id']
        assert actual['caption'] == user_edited['caption']
        assert actual['image_prompt_en'] == user_edited['image_prompt_en']
    assert rewrite_project == original
    assert state.releases == 1


@pytest.mark.parametrize('moved_refs', [['P2'], ['P1', 'P2']], ids=['other-scene', 'extra-paragraph'])
def test_rewrite_cannot_import_another_scenes_paragraph_even_at_the_right_length(
    rewrite_project, fake_generator, moved_refs,
):
    original = copy.deepcopy(rewrite_project)
    moved = copy.deepcopy(rewrite_project['scenes'])
    moved[0]['source_ids'] = moved_refs
    budget = sum(len(scene['narration']) for scene in moved)
    # Both P1 and P2 exist, so structural parsing alone would accept this.
    state = fake_generator([copy.deepcopy(moved), copy.deepcopy(moved)])

    with pytest.raises(RuntimeError, match=r'장면 1.*source_ids'):
        inference.generate_draft(
            rewrite_project, lambda *_: None, Event(),
            narration_characters=budget, existing_scenes=rewrite_project['scenes'],
        )

    assert state.generate_calls == 2
    assert 'source_ids' in state.prompts[1][-1]['content']
    assert state.releases == 1
    assert rewrite_project == original


@pytest.mark.parametrize('before,after,marker', [
    ('공항 공격으로 피해가 발생한 것으로 보도됐습니다.',
     '공항 공격으로 피해가 발생했습니다.', '보도'),
    ('기관은 앞으로 공급이 증가할 것으로 전망했습니다.',
     '앞으로 공급은 증가합니다.', '전망'),
    ('시장에서는 공급 차질에 대한 우려가 커졌습니다.',
     '시장에서는 공급 차질이 발생했습니다.', '우려'),
], ids=['reported-to-confirmed', 'forecast-to-confirmed', 'concern-to-confirmed'])
def test_timing_rewrite_cannot_turn_qualified_information_into_a_confirmed_fact(
    rewrite_project, fake_generator, before, after, marker,
):
    rewrite_project['scenes'][0]['narration'] = before
    rewrite_project['scenes'][0]['caption'] = '출처의 확실성 유지'
    rewrite_project['paragraphs'][0]['text'] = before
    original = copy.deepcopy(rewrite_project)
    revised = copy.deepcopy(rewrite_project['scenes'])
    revised[0]['narration'] = after
    # Give the bad output its exact length budget: rejection must be semantic,
    # not an accidental failure of the independent length guard.
    budget = sum(len(scene['narration']) for scene in revised)
    state = fake_generator([copy.deepcopy(revised), copy.deepcopy(revised)])

    with pytest.raises(RuntimeError, match=marker):
        inference.generate_draft(
            rewrite_project, lambda *_: None, Event(),
            narration_characters=budget, existing_scenes=rewrite_project['scenes'],
        )

    assert state.generate_calls == 2
    assert marker in state.prompts[1][-1]['content']
    assert state.releases == 1
    assert rewrite_project == original


def test_timing_rewrite_rejects_losing_a_contrast_even_when_the_budget_is_met(
    rewrite_project, fake_generator,
):
    before = '공급이 늘었지만 시장 가격은 올랐습니다.'
    rewrite_project['scenes'][0]['narration'] = before
    rewrite_project['scenes'][0]['caption'] = '공급과 가격의 대비'
    rewrite_project['paragraphs'][0]['text'] = before
    original = copy.deepcopy(rewrite_project)
    revised = copy.deepcopy(rewrite_project['scenes'])
    revised[0]['narration'] = '공급이 늘어 시장 가격은 올랐습니다.'
    budget = sum(len(scene['narration']) for scene in revised)
    state = fake_generator([copy.deepcopy(revised), copy.deepcopy(revised)])

    with pytest.raises(RuntimeError, match='대비'):
        inference.generate_draft(
            rewrite_project, lambda *_: None, Event(),
            narration_characters=budget, existing_scenes=rewrite_project['scenes'],
        )

    assert state.generate_calls == 2
    assert '대비' in state.prompts[1][-1]['content']
    assert state.releases == 1
    assert rewrite_project == original


@pytest.mark.parametrize('before,after', [
    ('피해가 발생한 것으로 보도됐습니다.', '피해가 발생한 것으로 전해졌습니다.'),
    ('공급이 늘었지만 가격은 올랐습니다.', '공급이 늘었습니다. 그러나 가격은 올랐습니다.'),
], ids=['equivalent-reporting-qualifier', 'equivalent-contrast'])
def test_qualified_rephrasing_is_accepted_without_requiring_identical_wording(
    rewrite_project, fake_generator, before, after,
):
    rewrite_project['scenes'][0]['narration'] = before
    rewrite_project['paragraphs'][0]['text'] = before
    original = copy.deepcopy(rewrite_project)
    revised = copy.deepcopy(rewrite_project['scenes'])
    revised[0]['narration'] = after
    budget = sum(len(scene['narration']) for scene in revised)
    state = fake_generator([revised])

    result = inference.generate_draft(
        rewrite_project, lambda *_: None, Event(),
        narration_characters=budget, existing_scenes=rewrite_project['scenes'],
    )

    assert state.generate_calls == 1
    assert result == revised
    assert state.releases == 1
    assert rewrite_project == original


def test_two_undersized_rewrites_raise_without_mutating_the_reviewed_draft(
    rewrite_project, fake_generator,
):
    original = copy.deepcopy(rewrite_project)
    state = fake_generator([copy.deepcopy(original['scenes']), copy.deepcopy(original['scenes'])])

    with pytest.raises(RuntimeError, match='90~110%'):
        inference.generate_draft(
            rewrite_project, lambda *_: None, Event(),
            narration_characters=200, existing_scenes=rewrite_project['scenes'],
        )

    assert state.generate_calls == 2
    assert state.releases == 1
    assert rewrite_project == original


def test_rejected_length_rewrites_allow_worker_to_finish_with_original_audio(
    rewrite_project, fake_generator, tmp_path, monkeypatch,
):
    import server

    original_scenes = copy.deepcopy(rewrite_project['scenes'])
    state = fake_generator([copy.deepcopy(original_scenes), copy.deepcopy(original_scenes)])
    monkeypatch.setattr(server, 'DATA', tmp_path)
    server.save(copy.deepcopy(rewrite_project))
    monkeypatch.setattr(server, 'generate_images', lambda *_: None)
    monkeypatch.setattr(server, 'generate_draft', inference.generate_draft)
    audio = [dict(duration=3) for _ in original_scenes]
    voice_calls, render_calls = [], []

    def voice(candidate, *_):
        voice_calls.append(copy.deepcopy(candidate['scenes']))
        return audio

    def render(candidate, _folder, selected_audio, *_):
        assert candidate['scenes'] == original_scenes
        assert selected_audio is audio
        render_calls.append(candidate['id'])
        return {'duration': 60}

    monkeypatch.setattr(server, 'synthesize', voice)
    monkeypatch.setattr(server, 'render_video', render)
    server.worker(rewrite_project['id'], 'render', Event())

    result = server.read(rewrite_project['id'])
    assert state.generate_calls == 2
    assert voice_calls == [original_scenes]  # Rejected text must never reach a second TTS call.
    assert render_calls == [rewrite_project['id']]
    assert result['status'] == 'completed'
    assert result['error'] is None
    assert result['scenes'] == original_scenes
    assert result['result'] == {'duration': 60}

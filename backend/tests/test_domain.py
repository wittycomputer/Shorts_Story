import json
import pytest
from pydantic import ValidationError
from domain import CreateProject, allocate_timing, parse_scenes, paragraphs, speech_phrases, ass_time, wrap_caption


def test_blank_and_oversized_articles_are_rejected():
    with pytest.raises(ValidationError):
        CreateProject(text=' ' * 80)
    with pytest.raises(ValidationError):
        CreateProject(text='가' * 12001)


def test_source_ids_must_exist():
    scene = {'id': 1, 'narration': '대여를 시작합니다.', 'caption': '시작', 'image_prompt_en': 'cup in a cafe', 'source_ids': ['P99']}
    with pytest.raises(ValueError, match='문단'):
        parse_scenes(json.dumps({'scenes': [scene, {**scene, 'id': 2}]}), paragraphs('다회용 컵을 빌립니다.'))


def test_duplicate_scene_ids_are_rejected():
    scene = {'id': 1, 'narration': '대여를 시작합니다.', 'image_prompt_en': 'cup in a cafe', 'source_ids': ['P1']}
    with pytest.raises(ValueError):
        parse_scenes(json.dumps({'scenes': [scene, scene]}), paragraphs('원문입니다.'))


def test_timing_never_truncates_narration():
    speed, pauses = allocate_timing([6.0, 7.0, 5.0, 7.0], 30)
    assert sum([6, 7, 5, 7]) / speed + sum(pauses) + 2 == pytest.approx(30)
    assert 0.85 <= speed <= 1.25


@pytest.mark.parametrize('durations,target', [
    ([1, 1], 60),
    ([3.37, 2.78, 2.36, 4.04, 3.86, 5.26, 2.32, 2.02], 60),
    ([20, 20, 20, 20], 30),
    ([40, 40], 45),
])
def test_short_and_long_narrations_finish_at_requested_length(durations, target):
    speed, pauses = allocate_timing(durations, target)
    assert sum(durations) / speed + sum(pauses) + 2 == pytest.approx(target)
    assert speed >= 0.85
    assert all(pause > 0 for pause in pauses)


@pytest.mark.parametrize('durations', [[], [0], [-1], [float('nan')], [float('inf')]])
def test_invalid_audio_still_rejected(durations):
    with pytest.raises(ValueError, match='음성 길이'):
        allocate_timing(durations, 60)


@pytest.mark.parametrize('speed', [0.125, 0.85, 1.0, 1.25, 4.5, 12.0])
def test_tempo_chain_uses_supported_factors_and_preserves_speed(speed):
    import math
    from media import tempo_filter
    factors = [float(filter.split('=')[1]) for filter in tempo_filter(speed).split(',')]
    assert all(0.5 <= factor <= 2.0 for factor in factors)
    assert math.prod(factors) == pytest.approx(speed)


def test_caption_splitting_retains_every_word_and_bounds_width():
    original = '캠퍼스에서 다회용 컵을 빌리고 반납합니다. 사용한 컵은 세척합니다.'
    phrases = speech_phrases(original, 22)
    assert ''.join(''.join(phrases).split()) == ''.join(original.split())
    assert all(len(p) <= 22 for p in phrases)
    assert all(len(line) <= 18 for line in wrap_caption(original).splitlines())
    assert ass_time(59.999) == '0:01:00.00'


def test_api_rejects_editing_busy_jobs_and_stale_downloads(tmp_path, monkeypatch):
    import server
    from fastapi.testclient import TestClient
    monkeypatch.setattr(server, 'DATA', tmp_path)
    pid = 'a' * 32
    p = dict(id=pid, owner_uid='alice', status='generating', scenes=[], paragraphs=[{'id': 'P1', 'text': '원문'}], text='원문', created_at=0)
    server.save(p)
    client = TestClient(server.app)
    monkeypatch.setitem(server.app.dependency_overrides, server.current_user, lambda: 'alice')
    assert client.get(f'/files/{pid}/shorts.mp4').status_code == 409
    assert client.get('/projects/not-a-project').status_code == 404
    scene = {'id': 1, 'narration': '대여를 시작합니다.', 'image_prompt_en': 'cup in cafe', 'source_ids': ['P1']}
    result = client.put(f'/projects/{pid}/scenes', json={'scenes': [scene, {**scene, 'id': 2}]})
    assert result.status_code == 409

from threading import Event

import pytest
import server
from inference import Cancelled


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DATA', tmp_path)
    scene = dict(id=1, narration='원문에 있는 짧은 설명입니다.', caption='첫 장면',
                 image_prompt_en='a calm landscape', source_ids=['P1'])
    project = dict(id='d' * 32, owner_uid='alice', status='queued', title='Timing regression',
                   target_seconds=60, text='원문에 있는 짧은 설명과 이를 뒷받침하는 추가 정보입니다.',
                   paragraphs=[dict(id='P1', text='원문에 있는 추가 정보입니다.')],
                   scenes=[scene, {**scene, 'id': 2}], warnings=[], result=None,
                   created_at=0, updated_at=0, source='fixture')
    server.save(project)
    monkeypatch.setattr(server, 'generate_images', lambda *_: None)
    return project


def test_worker_automatically_expands_short_voice_before_render(project, monkeypatch):
    synthesize_folders, rendered = [], []
    def voice(candidate, folder, *_):
        synthesize_folders.append(folder)
        return [dict(duration=3 if len(synthesize_folders) == 1 else 24) for _ in candidate['scenes']]
    def rewrite(candidate, progress, event, *, narration_characters, existing_scenes):
        assert narration_characters > sum(len(s['narration']) for s in existing_scenes)
        return [{**s, 'narration': '원문을 바탕으로 자동 보충한 설명입니다.'} for s in existing_scenes]
    monkeypatch.setattr(server, 'synthesize', voice)
    monkeypatch.setattr(server, 'generate_draft', rewrite)
    monkeypatch.setattr(server, 'render_video', lambda candidate, *_: rendered.append(candidate) or {'duration': 60})
    server.worker(project['id'], 'render', Event())
    updated = server.read(project['id'])
    assert updated['status'] == 'completed'
    assert updated['error'] is None
    assert updated['scenes'][0]['narration'] == '원문을 바탕으로 자동 보충한 설명입니다.'
    assert synthesize_folders[1] != synthesize_folders[0]
    assert rendered[0]['scenes'] == updated['scenes']


def test_rewrite_failure_keeps_valid_audio_and_completes(project, monkeypatch):
    original_audio = [dict(duration=3) for _ in project['scenes']]
    monkeypatch.setattr(server, 'synthesize', lambda *_: original_audio)
    def unavailable(*args, **kwargs):
        raise ValueError('Invalid model JSON')
    monkeypatch.setattr(server, 'generate_draft', unavailable)
    def render(candidate, folder, audio, *_):
        assert audio is original_audio
        assert candidate['scenes'] == project['scenes']
        return {'duration': 60}
    monkeypatch.setattr(server, 'render_video', render)
    server.worker(project['id'], 'render', Event())
    assert server.read(project['id'])['status'] == 'completed'


def test_rewrite_cancellation_stays_cancelled(project, monkeypatch):
    monkeypatch.setattr(server, 'synthesize', lambda *_: [dict(duration=3), dict(duration=3)])
    def cancelled(*args, **kwargs):
        raise Cancelled('cancelled')
    monkeypatch.setattr(server, 'generate_draft', cancelled)
    monkeypatch.setattr(server, 'render_video', lambda *_: pytest.fail('Cancelled work must not render'))
    server.worker(project['id'], 'render', Event())
    assert server.read(project['id'])['status'] == 'cancelled'


def test_adjusted_voice_failure_does_not_replace_original_scene_data(project, monkeypatch):
    original_audio = [dict(duration=3), dict(duration=3)]
    calls = []
    def voice(candidate, folder, *_):
        calls.append(folder)
        if len(calls) == 2:
            raise RuntimeError('TTS retry failed')
        return original_audio
    monkeypatch.setattr(server, 'synthesize', voice)
    monkeypatch.setattr(server, 'generate_draft', lambda *args, **kwargs: [
        {**s, 'narration': '자동 보충된 설명입니다.'} for s in project['scenes']])
    def render(candidate, folder, audio, *_):
        assert audio is original_audio
        assert candidate['scenes'] == project['scenes']
        return {'duration': 60}
    monkeypatch.setattr(server, 'render_video', render)
    server.worker(project['id'], 'render', Event())
    assert server.read(project['id'])['status'] == 'completed'
    assert calls[0] != calls[1]


def test_less_suitable_rewrite_keeps_the_original_narration(project, monkeypatch):
    original_audio = [dict(duration=3), dict(duration=3)]
    voices = iter([original_audio, [dict(duration=200), dict(duration=200)]])
    monkeypatch.setattr(server, 'synthesize', lambda *_: next(voices))
    monkeypatch.setattr(server, 'generate_draft', lambda *args, **kwargs: [
        {**s, 'narration': '너무 길게 보충된 설명입니다.'} for s in project['scenes']])
    def render(candidate, folder, audio, *_):
        assert audio is original_audio
        assert candidate['scenes'] == project['scenes']
        return {'duration': 60}
    monkeypatch.setattr(server, 'render_video', render)
    server.worker(project['id'], 'render', Event())
    assert server.read(project['id'])['status'] == 'completed'


def test_large_tempo_adjustment_produces_real_audio(tmp_path):
    import shutil
    import subprocess
    import soundfile as sf
    from media import tempo_filter
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('FFmpeg is not installed in this unit-test environment')
    output = tmp_path / 'adjusted.wav'
    result = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
        '-i', 'sine=frequency=440:sample_rate=16000:duration=6',
        '-af', tempo_filter(4.5), str(output)], capture_output=True)
    assert result.returncode == 0
    assert sf.info(output).duration == pytest.approx(6 / 4.5, abs=0.12)

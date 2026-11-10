import copy
import hashlib
import json
from threading import Event

import numpy as np
import pytest


@pytest.fixture
def voices(tmp_path, monkeypatch):
    import inference
    import korean_voice
    calls = []
    class Voice:
        sample_rate = 44100
        def __init__(self, location, voice):
            self.voice = voice
        def generate(self, text):
            calls.append((self.voice, text))
            return np.sin(np.arange(44100) * 0.05).astype(np.float32) * 0.15
    model_dir = tmp_path / 'models'
    model_dir.mkdir()
    (model_dir / 'models.lock.json').write_text(json.dumps({'tts': {
        'repo': 'supertone-oss-archive/supertonic-3', 'revision': 'test-revision'}}))
    monkeypatch.setattr(inference, 'BASE', model_dir)
    monkeypatch.setattr(inference, 'model_path', lambda _: 'local-test-double')
    monkeypatch.setattr(korean_voice, 'KoreanVoice', Voice)
    monkeypatch.setattr(inference, 'release_memory', lambda: None)
    return calls


def test_synthesis_preserves_sentences_captions_and_replaces_mms_cache(tmp_path, voices):
    import inference
    text = '지수는 전월 88.6에서 81.9로 내려갔으며, 고용과 경기 전망도 함께 살펴봐야 합니다.'
    project = {'voice': 'F1', 'scenes': [{'id': 1, 'narration': text}]}
    original = copy.deepcopy(project)
    # Even an old cached phrase with the same original text must be regenerated.
    audio_dir = tmp_path / 'audio'
    audio_dir.mkdir()
    (audio_dir / '01_00.wav').write_bytes(b'old-cache')
    (audio_dir / '01_00.sha256').write_text(hashlib.sha256(text.encode()).hexdigest())
    records = inference.synthesize(project, tmp_path, lambda *_: None, Event())
    assert len(voices) == 1 and voices[0][0] == 'F1'
    assert '팔십팔 점 육' in voices[0][1] and '팔십일 점 구' in voices[0][1]
    assert len(records[0]['phrases']) == 1
    assert records[0]['phrases'][0]['text'] == text
    assert project == original
    inference.synthesize(project, tmp_path, lambda *_: None, Event())
    assert len(voices) == 1
    project['voice'] = 'M1'
    inference.synthesize(project, tmp_path, lambda *_: None, Event())
    assert len(voices) == 2 and voices[-1][0] == 'M1'


def test_legacy_project_defaults_to_male_and_new_revision_invalidates_cache(tmp_path, voices):
    import inference
    project = {'scenes': [{'id': 1, 'narration': '기존 작업도 새 한국어 모델로 읽습니다.'}]}
    inference.synthesize(project, tmp_path, lambda *_: None, Event())
    assert voices[0][0] == 'M1'
    lock = inference.BASE / 'models.lock.json'
    entry = json.loads(lock.read_text())
    entry['tts']['revision'] = 'next-revision'
    lock.write_text(json.dumps(entry))
    inference.synthesize(project, tmp_path, lambda *_: None, Event())
    assert len(voices) == 2


def test_old_model_setup_is_rejected_instead_of_silently_using_mms(tmp_path, voices):
    import inference
    (inference.BASE / 'models.lock.json').write_text(json.dumps({'tts': {'repo': 'facebook/mms-tts-kor'}}))
    with pytest.raises(RuntimeError, match='setup.bat'):
        inference.synthesize({'scenes': []}, tmp_path, lambda *_: None, Event())
    assert voices == []


def test_cancelled_synthesis_does_not_publish_cache(tmp_path, voices, monkeypatch):
    import inference
    import korean_voice
    event = Event()
    def cancelled(self, text):
        event.set()
        return np.ones(44100, dtype=np.float32)
    monkeypatch.setattr(korean_voice.KoreanVoice, 'generate', cancelled)
    with pytest.raises(inference.Cancelled):
        inference.synthesize({'scenes': [{'id': 1, 'narration': '취소할 작업입니다.'}]}, tmp_path, lambda *_: None, event)
    assert not list((tmp_path / 'audio').iterdir())

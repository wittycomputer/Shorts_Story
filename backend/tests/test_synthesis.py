import copy
import hashlib
from threading import Event
from types import SimpleNamespace

import numpy as np


def test_synthesis_uses_whole_sentences_reading_forms_and_invalidates_old_cache(tmp_path, monkeypatch):
    import torch
    import transformers
    import inference

    spoken_inputs = []
    class Tokenizer:
        def __call__(self, text, **_):
            spoken_inputs.append(text)
            return {'input_ids': torch.tensor([[1]])}
    class Voice:
        config = SimpleNamespace(sampling_rate=16000)
        def eval(self):
            return self
        def __call__(self, **_):
            wave = np.sin(np.arange(16000) * 0.05).astype(np.float32) * 0.15
            return SimpleNamespace(waveform=torch.from_numpy(wave).unsqueeze(0))
    monkeypatch.setattr(inference, 'model_path', lambda _: 'local-test-double')
    monkeypatch.setattr(transformers.AutoTokenizer, 'from_pretrained', lambda *_a, **_k: Tokenizer())
    monkeypatch.setattr(transformers.VitsModel, 'from_pretrained', lambda *_a, **_k: Voice())
    monkeypatch.setattr(inference, 'release_memory', lambda: None)
    removed_hooks = []
    monkeypatch.setattr('speech_rhythm.install_rhythm_control',
                        lambda *_: (SimpleNamespace(remove=lambda: removed_hooks.append(True)), {}))
    text = '지수는 전월 88.6에서 81.9로 내려갔으며, 고용과 경기 전망도 함께 살펴봐야 합니다.'
    project = {'scenes': [{'id': 1, 'narration': text}]}
    original = copy.deepcopy(project)
    # Even an old cached phrase with the same original text must be regenerated.
    audio_dir = tmp_path / 'audio'
    audio_dir.mkdir()
    (audio_dir / '01_00.wav').write_bytes(b'old-cache')
    (audio_dir / '01_00.sha256').write_text(hashlib.sha256(text.encode()).hexdigest())
    records = inference.synthesize(project, tmp_path, lambda *_: None, Event())
    assert len(spoken_inputs) == 1
    assert removed_hooks == [True]
    assert '팔십팔 점 육' in spoken_inputs[0] and '팔십일 점 구' in spoken_inputs[0]
    assert len(records[0]['phrases']) == 1
    assert records[0]['phrases'][0]['text'] == text
    assert project == original
    inference.synthesize(project, tmp_path, lambda *_: None, Event())
    assert len(spoken_inputs) == 1  # Valid new cache is reusable.

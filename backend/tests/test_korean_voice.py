import numpy as np
import pytest
from korean_voice import KoreanVoice


@pytest.mark.parametrize('voice', ['M1', 'F1'])
def test_explicit_korean_offline_model_whole_sentence_and_rng_restoration(monkeypatch, voice):
    import supertonic
    calls = []
    class TTS:
        sample_rate = 44100
        def __init__(self, **kwargs):
            assert kwargs['auto_download'] is False
            assert kwargs['model_dir'] == 'offline-model'
            assert kwargs['model'] == 'supertonic-3'
        def get_voice_style(self, name):
            assert name == voice
            return name
        def synthesize(self, text, **kwargs):
            calls.append((text, kwargs))
            return np.random.randn(1, 44100), np.array([1.0])
    monkeypatch.setattr(supertonic, 'TTS', TTS)
    engine = KoreanVoice('offline-model', voice)
    text = '단어 사이를 잘라 붙이지 않고 완결된 한국어 문장을 그대로 읽습니다.'
    np.random.seed(123)
    expected = np.random.random()
    np.random.seed(123)
    first = engine.generate(text)
    assert np.random.random() == expected
    assert np.array_equal(first, engine.generate(text))
    assert calls[0][0] == text
    assert calls[0][1]['lang'] == 'ko'
    assert calls[0][1]['voice_style'] == voice
    assert calls[0][1]['max_chunk_length'] >= len(text)
    assert calls[0][1]['total_steps'] == 12


def test_unknown_voice_is_rejected_before_loading():
    with pytest.raises(ValueError, match='목소리'):
        KoreanVoice('unused', '../voice')

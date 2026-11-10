from threading import Event

import numpy as np
import pytest
import soundfile as sf

from narration import clean_waveform, prepare_narration, SENTENCE_PAUSE


def test_quiet_consonant_tail_survives_cleaning_and_edges_are_smooth():
    rate = 16000
    # A loud vowel followed by a quiet /s/-like ending, below the old 0.008 cutoff.
    wave = np.concatenate([np.zeros(1600), np.full(3200, 0.3),
                           np.full(2400, 0.002), np.zeros(3200)]).astype(np.float32)
    cleaned = clean_waveform(wave, rate)
    assert np.count_nonzero(cleaned == np.float32(0.002)) == 2400
    assert cleaned[0] == cleaned[-1] == 0
    assert len(cleaned) >= 3200 + 2400 + round(rate * 0.16)


@pytest.mark.parametrize('wave', [np.zeros(1000), np.full(1000, np.nan), np.ones((1000, 2))])
def test_invalid_or_silent_wave_cannot_be_exported(wave):
    with pytest.raises(RuntimeError):
        clean_waveform(wave, 16000)


def test_continuous_track_keeps_both_sentence_endings_and_original_captions(tmp_path):
    rate = 16000
    sentences = ['지수는 88.6에서 81.9로 하락했습니다.',
                 '두 번째 문장도 마지막 음절까지 이어집니다.']
    waves = [np.full(rate * 3, 0.15), np.full(rate * 4, -0.25)]
    records = []
    for i, (text, wave) in enumerate(zip(sentences, waves)):
        path = tmp_path / f'sentence_{i}.wav'
        sf.write(path, wave, rate, subtype='FLOAT')
        records.append({'id': i + 1, 'phrases': [{'text': text, 'file': str(path), 'duration': len(wave) / rate}]})
    project = {'target_seconds': 30, 'scenes': [{'id': 1}, {'id': 2}]}
    timeline = prepare_narration(project, tmp_path, records, Event())
    track, actual_rate = sf.read(tmp_path / 'narration.wav')
    assert actual_rate == rate
    assert np.count_nonzero(track > 0.1) == len(waves[0])
    assert np.count_nonzero(track < -0.2) == len(waves[1])
    assert timeline['scenes'][-1]['end'] == pytest.approx(30, abs=0.001)
    assert ''.join(c['text'] for c in timeline['captions']).replace(' ', '') == ''.join(sentences).replace(' ', '')
    assert any('88.6' in c['text'] and '81.9' in c['text'] for c in timeline['captions'])
    assert timeline['captions'][0]['start'] == 0
    assert timeline['captions'][-1]['end'] <= timeline['scenes'][-1]['speech_end']


def test_sentence_pause_and_captions_use_measured_audio_not_stale_metadata(tmp_path):
    rate = 16000
    phrases = []
    for i in range(2):
        path = tmp_path / f'{i}.wav'
        sf.write(path, np.full(rate, 0.1), rate)
        phrases.append({'text': f'{i + 1}번 문장입니다.', 'file': str(path), 'duration': 99})
    project = {'target_seconds': 30, 'scenes': [{'id': 1}, {'id': 2}]}
    audio = [{'phrases': phrases}, {'phrases': phrases[:1]}]
    result = prepare_narration(project, tmp_path, audio, Event())
    assert result['captions'][1]['start'] == pytest.approx((1 + SENTENCE_PAUSE) / result['speed'])
    assert result['scenes'][0]['speech_end'] == pytest.approx((2 + SENTENCE_PAUSE) / result['speed'])


def test_rate_mismatch_is_rejected_before_export(tmp_path):
    records = []
    for rate in (16000, 22050):
        path = tmp_path / f'{rate}.wav'
        sf.write(path, np.ones(rate) * 0.1, rate)
        records.append({'phrases': [{'text': '문장입니다.', 'file': str(path)}]})
    with pytest.raises(RuntimeError, match='샘플레이트'):
        prepare_narration({'target_seconds': 30, 'scenes': [{'id': 1}, {'id': 2}]},
                          tmp_path, records, Event())

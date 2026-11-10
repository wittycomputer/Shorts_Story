from types import SimpleNamespace

import pytest

from speech_rhythm import plan_durations, install_rhythm_control, RHYTHM_PROFILE

VOCAB = {'u': 0, 'a': 7, 'g': 19, ' ': 21, 'n': 16, 'r': 20}
IDS = [0, 19, 0, 7, 0, 21, 0, 16, 0, 7, 0, 20, 0]
FRAMES = [1, 30, 1, 8, 1, 8, 32, 25, 1, 8, 1, 30, 1]


def plan(frames=FRAMES, ids=IDS, blanks=True):
    return plan_durations(frames, ids, space_id=21, consonant_ids={19, 16, 20},
                          blank_id=0, frames_per_second=62.5, interspersed_blanks=blanks)


def test_excessive_separator_and_onsets_shorten_but_internal_letters_survive():
    result, report = plan()
    assert sum(result[4:7]) <= 13  # 0.22 seconds, rounded down to model frames.
    assert result[1] == result[7] == 11
    assert result[3] == FRAMES[3] and result[9] == FRAMES[9]
    assert result[11] == FRAMES[11]  # A long consonant inside the word stays.
    assert all(value >= 1 for value in result)
    assert report == {'word_boundaries_adjusted': 1, 'onsets_adjusted': 2}
    assert FRAMES == [1, 30, 1, 8, 1, 8, 32, 25, 1, 8, 1, 30, 1]


def test_letter_u_shares_blank_id_but_a_spoken_vowel_is_never_shortened():
    ids = IDS.copy()
    ids[3] = 0  # VITS Korean uses ID 0 for both interspersed blanks and vowel u.
    frames = FRAMES.copy()
    frames[3] = 45
    result, _ = plan(frames, ids)
    assert result[3] == 45


def test_natural_short_word_boundary_is_unchanged():
    frames = [2] * len(IDS)
    result, report = plan(frames)
    assert result == frames
    assert report == {'word_boundaries_adjusted': 0, 'onsets_adjusted': 0}


def test_noninterspersed_tokens_keep_neighboring_phonemes():
    result, _ = plan([30, 8, 40, 25, 45], [19, 7, 21, 16, 0], blanks=False)
    assert result == [11, 8, 13, 11, 45]


def test_duration_hook_generates_the_planned_number_of_frames_and_is_removable():
    import torch
    model = SimpleNamespace(config=SimpleNamespace(sampling_rate=16000, upsample_rates=[8, 8, 2, 2]),
                            speaking_rate=RHYTHM_PROFILE['speaking_rate'],
                            duration_predictor=torch.nn.Identity())
    tokenizer = SimpleNamespace(get_vocab=lambda: VOCAB, pad_token_id=0, add_blank=True)
    inputs = {'input_ids': torch.tensor([IDS])}
    log_durations = torch.log((torch.tensor(FRAMES, dtype=torch.float32) - .25) * model.speaking_rate)[None, None, :]
    before = log_durations.clone()
    handle, report = install_rhythm_control(model, tokenizer, inputs)
    adjusted = model.duration_predictor(log_durations)
    result = torch.ceil(torch.exp(adjusted) / model.speaking_rate).long()[0, 0].tolist()
    assert result == plan()[0]
    assert report['word_boundaries_adjusted'] == 1
    torch.testing.assert_close(log_durations, before)
    handle.remove()
    torch.testing.assert_close(model.duration_predictor(log_durations), before)


def test_every_phoneme_remains_and_every_vowel_keeps_its_predicted_length():
    import random
    rng = random.Random(42)
    for _ in range(100):
        frames = [rng.randint(1, 60) for _ in IDS]
        result, _ = plan(frames)
        assert len(result) == len(frames)
        assert all(1 <= after <= before for before, after in zip(frames, result))
        assert result[3] == frames[3] and result[9] == frames[9]


def test_misaligned_tokens_are_rejected():
    with pytest.raises(ValueError):
        plan([1, 2], [0])

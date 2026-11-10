"""Bound excessive VITS word-boundary durations before waveform generation."""
from __future__ import annotations

import math

RHYTHM_PROFILE = {"speaking_rate": 0.90, "duration_noise": 0.35,
                  "word_boundary_seconds": 0.22, "onset_trigger_seconds": 0.26,
                  "onset_limit_seconds": 0.18}


def plan_durations(durations: list[int], token_ids: list[int], *, space_id: int,
                   consonant_ids: set[int], blank_id: int, frames_per_second: float,
                   interspersed_blanks: bool) -> tuple[list[int], dict]:
    """Change only word separators and excessively long initial consonants.

    Internal letters and all vowels retain their model-predicted durations.
    Every input token keeps at least one frame; spoken tokens are never removed.
    """
    if len(durations) != len(token_ids) or frames_per_second <= 0:
        raise ValueError("음성 토큰과 시간 정보가 일치하지 않습니다.")
    result = list(durations)
    report = {"word_boundaries_adjusted": 0, "onsets_adjusted": 0}
    has_blanks = interspersed_blanks and all(t == blank_id for t in token_ids[::2])
    spaces = [i for i, token in enumerate(token_ids) if token == space_id]
    for index in spaces:
        group = [index]
        if has_blanks:
            group = list(range(max(0, index-1), min(len(result), index+2)))
        current = [result[i] for i in group]
        cap = max(len(group), math.floor(frames_per_second * RHYTHM_PROFILE["word_boundary_seconds"]))
        if sum(current) <= cap:
            continue
        # Preserve relative spacing, with a positive frame for each separator.
        budget = cap - len(group)
        weights = [max(0, value-1) for value in current]
        total = sum(weights)
        shares = [budget * weight / total for weight in weights]
        allocated = [1 + math.floor(share) for share in shares]
        for i in sorted(range(len(group)), key=lambda i: shares[i] % 1, reverse=True)[:cap-sum(allocated)]:
            allocated[i] += 1
        for i, value in zip(group, allocated):
            result[i] = value
        report["word_boundaries_adjusted"] += 1
    first = 1 if has_blanks else 0
    onsets = [first] + [index + (2 if has_blanks else 1) for index in spaces]
    trigger = math.ceil(frames_per_second * RHYTHM_PROFILE["onset_trigger_seconds"])
    limit = max(1, math.floor(frames_per_second * RHYTHM_PROFILE["onset_limit_seconds"]))
    for index in onsets:
        if index < len(result) and token_ids[index] in consonant_ids and result[index] > trigger:
            result[index] = limit
            report["onsets_adjusted"] += 1
    return result, report


def install_rhythm_control(model, tokenizer, inputs):
    """Use the installed VITS duration predictor hook; remove it after generation."""
    import torch

    vocab = tokenizer.get_vocab()
    if ' ' not in vocab:
        raise RuntimeError("한국어 음성 모델의 단어 경계를 찾을 수 없습니다.")
    frame_seconds = math.prod(model.config.upsample_rates) / model.config.sampling_rate
    token_batches = inputs['input_ids'].detach().cpu().tolist()
    consonants = {vocab[c] for c in 'bcdfghjklmnpqrstvwxyz' if c in vocab}
    report = {"word_boundaries_adjusted": 0, "onsets_adjusted": 0}

    def adjust(_module, _args, log_durations):
        changed = log_durations.clone()
        rate = model.speaking_rate
        counts = torch.ceil(torch.exp(log_durations) / rate).detach().cpu().long().tolist()
        for batch, tokens in enumerate(token_batches):
            planned, changes = plan_durations(
                counts[batch][0], tokens, space_id=vocab[' '],
                consonant_ids=consonants, blank_id=tokenizer.pad_token_id,
                frames_per_second=1 / frame_seconds,
                interspersed_blanks=tokenizer.add_blank,
            )
            for key, value in changes.items():
                report[key] += value
            for index, (before, after) in enumerate(zip(counts[batch][0], planned)):
                if before != after:
                    # ceil(exp(log_duration) / speaking_rate) must equal after,
                    # including under floating-point rounding.
                    changed[batch, 0, index] = math.log((after - 0.25) * rate)
        return changed

    handle = model.duration_predictor.register_forward_hook(adjust)
    return handle, report

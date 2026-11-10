"""Sentence audio and captions share one continuous, sample-accurate PCM timeline."""
from __future__ import annotations

import re
from pathlib import Path
from threading import Event

import numpy as np
import soundfile as sf

from domain import allocate_timing, speech_phrases

SENTENCE_PAUSE = 0.10
VOICE_PIPELINE_VERSION = "ko-sentences-pcm-v2"


def clean_waveform(wave: np.ndarray, sample_rate: int) -> np.ndarray:
    """Remove model padding conservatively, keeping quiet consonants and breaths."""
    wave = np.asarray(wave, dtype=np.float32)
    if wave.ndim != 1 or len(wave) < 200 or not np.isfinite(wave).all():
        raise RuntimeError("음성 모델이 유효한 파형을 생성하지 못했습니다.")
    # RMS windows avoid trimming to the last loud vowel. Keep a generous tail.
    window = max(1, round(sample_rate * 0.01))
    padded = np.pad(wave, (0, (-len(wave)) % window))
    energy = np.sqrt(np.mean(padded.reshape(-1, window) ** 2, axis=1))
    active = np.flatnonzero(energy > max(0.00015, float(energy.max()) * 0.003))
    if not len(active):
        raise RuntimeError("음성 모델이 무음만 생성했습니다. 다시 시도해 주세요.")
    start = max(0, active[0] * window - round(sample_rate * 0.08))
    end = min(len(wave), (active[-1] + 1) * window + round(sample_rate * 0.16))
    wave = wave[start:end].copy()
    # Very short edge fades remove clicks without crossfading spoken syllables.
    fade = min(round(sample_rate * 0.003), len(wave) // 2)
    if fade:
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)
    peak = float(np.max(np.abs(wave)))
    if peak > 0.98:
        wave *= 0.98 / peak
    return wave


def prepare_narration(project: dict, folder: Path, audio: list[dict], cancel: Event) -> dict:
    """Build one audio track; visual frame rounding never truncates speech."""
    from inference import checkpoint
    from korean_speech import normalize_for_speech

    if len(audio) != len(project["scenes"]):
        raise ValueError("장면과 음성의 개수가 일치하지 않습니다.")
    scene_waves, sentences = [], []
    sample_rate = None
    for record in audio:
        chunks, entries, offset = [], [], 0
        for index, phrase in enumerate(record["phrases"]):
            checkpoint(cancel)
            wave, rate = sf.read(phrase["file"], dtype="float32")
            if wave.ndim != 1 or not len(wave) or not np.isfinite(wave).all():
                raise RuntimeError("음성 파형이 올바르지 않습니다.")
            if sample_rate is not None and rate != sample_rate:
                raise RuntimeError("음성 샘플레이트가 일치하지 않습니다.")
            sample_rate = rate
            entries.append({"text": phrase["text"], "start": offset / rate,
                            "duration": len(wave) / rate})
            chunks.append(wave)
            offset += len(wave)
            if index < len(record["phrases"]) - 1:
                pause = np.zeros(round(SENTENCE_PAUSE * rate), dtype=np.float32)
                chunks.append(pause)
                offset += len(pause)
        if not chunks:
            raise ValueError("장면에 재생할 음성이 없습니다.")
        scene_waves.append(np.concatenate(chunks))
        sentences.append(entries)

    durations = [len(wave) / sample_rate for wave in scene_waves]
    speed, pauses = allocate_timing(durations, project["target_seconds"])
    chunks, captions, timeline = [], [], []
    cursor_samples = 0
    for index, (wave, entries, pause) in enumerate(zip(scene_waves, sentences, pauses)):
        checkpoint(cancel)
        start = cursor_samples / sample_rate / speed
        for sentence in entries:
            # Caption length does not determine TTS boundaries. Timing inside a
            # sentence is estimated by spoken length; sentence timing is measured.
            texts = speech_phrases(sentence["text"])
            weights = [max(1, len(re.sub(r"\s", "", normalize_for_speech(t)))) for t in texts]
            total = sum(weights)
            offset = start + sentence["start"] / speed
            sentence_end = offset + sentence["duration"] / speed
            for text, weight in zip(texts, weights):
                end = min(sentence_end, offset + sentence["duration"] / speed * weight / total)
                captions.append({"start": offset, "end": end, "text": text})
                offset = end
            if texts:
                captions[-1]["end"] = sentence_end
        chunks.append(wave)
        cursor_samples += len(wave)
        padding = round(pause * speed * sample_rate)
        if index == len(audio) - 1:
            padding += round(2.0 * speed * sample_rate)
        chunks.append(np.zeros(padding, dtype=np.float32))
        cursor_samples += padding
        end = cursor_samples / sample_rate / speed
        # Image boundaries follow the audio, rounded to video frames only.
        timeline.append({"id": project["scenes"][index]["id"], "start": start,
                         "end": end, "speech_end": start + durations[index] / speed,
                         "pause": pause})
    sf.write(folder / "narration.wav", np.concatenate(chunks), sample_rate, subtype="PCM_16")
    return {"speed": speed, "scenes": timeline, "captions": captions,
            "caption_timing": "measured-sentences-estimated-caption-chunks",
            "voice_pipeline": VOICE_PIPELINE_VERSION}

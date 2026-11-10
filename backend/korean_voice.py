"""Local Korean synthesis with explicit language conditioning and preset voices."""
from __future__ import annotations

import numpy as np

VOICE_PRESETS = ("M1", "F1")
TTS_PROFILE = {"engine": "supertonic-3", "language": "ko",
               "steps": 12, "speed": 1.05, "seed": 42}


class KoreanVoice:
    def __init__(self, location: str, voice_name: str):
        from supertonic import TTS

        if voice_name not in VOICE_PRESETS:
            raise ValueError("지원하지 않는 내레이션 목소리입니다.")
        self.engine = TTS(model="supertonic-3", model_dir=location, auto_download=False,
                          intra_op_num_threads=4, inter_op_num_threads=1)
        self.style = self.engine.get_voice_style(voice_name)
        self.sample_rate = self.engine.sample_rate

    def generate(self, spoken: str) -> np.ndarray:
        # The SDK samples with numpy's RNG. Keep reproducible voices without
        # changing the caller's RNG state (the server has one inference worker).
        state = np.random.get_state()
        try:
            np.random.seed(TTS_PROFILE["seed"])
            wave, _ = self.engine.synthesize(
                spoken, voice_style=self.style, total_steps=TTS_PROFILE["steps"],
                speed=TTS_PROFILE["speed"], lang=TTS_PROFILE["language"],
                max_chunk_length=max(300, len(spoken) + 1), silence_duration=0.10)
        finally:
            np.random.set_state(state)
        # Keep Hangul input; no romanization or manual phoneme-duration edits.
        wave = np.asarray(wave, dtype=np.float32)
        if wave.ndim != 2 or wave.shape[0] != 1:
            raise RuntimeError("한국어 음성 모델의 출력 형식이 올바르지 않습니다.")
        return wave[0]

"""Project schema and timing rules shared by the API, worker, and tests."""
from __future__ import annotations

import json
import math
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class CreateProject(BaseModel):
    title: str = Field(default="새로운 이야기", max_length=80)
    text: str = Field(min_length=40, max_length=12000)
    source: str = Field(default="직접 작성한 글", max_length=300)
    target_seconds: Literal[30, 45, 60] = 45
    style: Literal["explain", "news"] = "explain"

    @field_validator("text")
    @classmethod
    def useful_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 40:
            raise ValueError("내용을 40자 이상 입력해 주세요.")
        return value


class Scene(BaseModel):
    id: int = Field(ge=1, le=12)
    narration: str = Field(min_length=3, max_length=300)
    caption: str = Field(default="", max_length=120)
    image_prompt_en: str = Field(min_length=5, max_length=1000)
    source_ids: list[str] = Field(min_length=1, max_length=30)

    @field_validator("narration", "image_prompt_en")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 문장은 사용할 수 없습니다.")
        return value.strip()


class EditScenes(BaseModel):
    scenes: list[Scene] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def unique_ids(self):
        if [s.id for s in self.scenes] != list(range(1, len(self.scenes) + 1)):
            raise ValueError("장면 번호는 1부터 순서대로 이어져야 합니다.")
        return self


def paragraphs(text: str) -> list[dict]:
    chunks = [p.strip() for p in re.split(r"\n\s*\n|(?<=[.!?。])\s+", text) if p.strip()]
    # Break only long paragraphs. The original text is always retained separately.
    parts = []
    for chunk in chunks:
        while len(chunk) > 800:
            at = chunk.rfind(" ", 0, 800)
            if at < 200:
                at = 800
            parts.append(chunk[:at].strip())
            chunk = chunk[at:].strip()
        parts.append(chunk)
    return [{"id": f"P{i + 1}", "text": part} for i, part in enumerate(parts)]


def parse_scenes(raw: str, source_paragraphs: list[dict]) -> list[dict]:
    """Reject malformed or ungrounded structure; never silently fabricate a draft."""
    raw = raw.split("</think>")[-1].strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI 응답에서 장면 JSON을 찾지 못했습니다.")
    obj = json.loads(raw[start:end + 1])
    result = EditScenes.model_validate({"scenes": obj["scenes"]})
    ids = {p["id"] for p in source_paragraphs}
    for scene in result.scenes:
        if not set(scene.source_ids).issubset(ids):
            raise ValueError("존재하지 않는 원문 문단을 인용했습니다.")
    return [s.model_dump() for s in result.scenes]


def factual_warnings(scenes: list[dict], original: str) -> list[str]:
    source_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", original))
    narration_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", " ".join(s["narration"] for s in scenes)))
    extra = sorted(narration_numbers - source_numbers)
    warnings = ["AI 대본의 사실과 표현을 원문과 비교해 주세요."]
    if extra:
        warnings.append("원문에 없는 숫자 확인: " + ", ".join(extra))
    return warnings


def speech_phrases(text: str, limit: int = 40) -> list[str]:
    """Each phrase gets its own WAV so captions use measured audio boundaries."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?。])\s*", text) if s.strip()]
    phrases = []
    for sentence in sentences:
        words = sentence.split()
        current = ""
        for word in words:
            if current and len(current) + len(word) + 1 > limit:
                phrases.append(current)
                current = ""
            if len(word) > limit:
                if current:
                    phrases.append(current)
                    current = ""
                while len(word) > limit:
                    phrases.append(word[:limit])
                    word = word[limit:]
            current = (current + " " + word).strip()
        if current:
            phrases.append(current)
    return phrases


def allocate_timing(durations: list[float], target: int, outro: float = 2.0) -> tuple[float, list[float]]:
    """Return narration speed and per-scene pause. Never cut audio to fit a target."""
    if not durations or any(not math.isfinite(d) or d <= 0 for d in durations):
        raise ValueError("음성 길이가 올바르지 않습니다.")
    available = target - outro
    if available <= 0:
        raise ValueError("목표 길이가 너무 짧습니다.")
    speed = max(1.0, sum(durations) / (available - 0.12 * len(durations)))
    if speed > 1.25:
        raise ValueError("대본이 목표 길이보다 깁니다. 문장을 줄이거나 더 긴 영상을 선택해 주세요.")
    remaining = available - sum(durations) / speed
    # A short source stays short; don't pad 20 seconds of silent stills.
    if remaining / len(durations) > 3.0:
        raise ValueError("대본이 목표 길이보다 짧습니다. 원문에 근거한 내용을 보충해 주세요.")
    total = sum(durations)
    pauses = [remaining * d / total for d in durations]
    return speed, pauses


def ass_time(seconds: float) -> str:
    cs = max(0, round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def wrap_caption(text: str, width: int = 18) -> str:
    lines, current = [], ""
    for word in text.replace("\n", " ").split():
        if len(current) + len(word) + 1 > width and current:
            lines.append(current)
            current = ""
        while len(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        current = (current + " " + word).strip()
    if current:
        lines.append(current)
    return "\n".join(lines)

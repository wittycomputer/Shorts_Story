"""Measured narration timing, animated stills, Korean subtitles, and MP4 export."""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from threading import Event

from domain import ass_time, srt_time, wrap_caption
from inference import checkpoint
from narration import prepare_narration


def run_ffmpeg(args: list[str], cwd: Path, cancel: Event):
    command = [shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    with (cwd / "ffmpeg.log").open("ab") as log:
        proc = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=log,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            while True:
                checkpoint(cancel)
                try:
                    code = proc.wait(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    pass
            if code:
                tail = (cwd / "ffmpeg.log").read_text("utf-8", errors="replace")[-1800:]
                raise RuntimeError("영상 합성 실패: " + tail)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


def ass_escape(text: str) -> str:
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N")


def tempo_filter(speed: float) -> str:
    """Chain supported atempo factors; large adjustments retain the whole audio."""
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("음성 속도가 올바르지 않습니다.")
    factors = []
    while speed > 2.0:
        factors.append(2.0)
        speed /= 2.0
    while speed < 0.5:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return ",".join(f"atempo={factor:.10f}" for factor in factors)


def render_video(project: dict, folder: Path, audio: list[dict], progress, cancel: Event) -> dict:
    narration = prepare_narration(project, folder, audio, cancel)
    speed = narration["speed"]
    subtitles = narration["captions"]
    events = [(entry["start"], entry["end"], "Subtitle", wrap_caption(entry["text"], 18))
              for entry in subtitles]
    clips = []
    cursor = 0.0
    # Stretch/normalize a single PCM track. AAC is encoded only once at export,
    # so image cuts cannot truncate quiet endings or introduce codec gaps.
    run_ffmpeg(["-i", "narration.wav", "-af",
                f"{tempo_filter(speed)},loudnorm=I=-16:TP=-1.5:LRA=11,apad",
                "-t", str(project["target_seconds"]), "-ar", "48000", "-c:a", "pcm_s16le",
                "narration-timed.wav"], folder, cancel)
    for i, timing in enumerate(narration["scenes"]):
        checkpoint(cancel)
        scene = project["scenes"][i]
        progress(67 + int(21 * i / len(audio)), f'장면 {i + 1} 영상을 합성하는 중')
        # Fixed 30 fps, round boundaries to frames. The last clip ends exactly at target.
        end_frame = round(timing["end"] * 30)
        if i == len(audio) - 1:
            end_frame = project["target_seconds"] * 30
        duration = end_frame / 30 - cursor
        caption = scene.get("caption") or scene["narration"][:22]
        events.append((cursor, cursor + duration, "Heading", wrap_caption(caption, 17)))
        image_name = f'scene_{scene["id"]:02d}.png'
        clip = f"clip_{i + 1:02d}.mp4"
        filters = (
            "[0:v]split[back][front];"
            "[back]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=24:2,eq=brightness=-0.18[bg];"
            "[front]scale=900:900,zoompan=z='min(max(zoom,pzoom)+0.00018,1.08)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=720x720:fps=30[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]"
        )
        run_ffmpeg(["-loop", "1", "-framerate", "30", "-i", image_name,
                    "-filter_complex", filters, "-map", "[v]", "-an",
                    "-t", f"{duration:.8f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "23", "-threads", "4", clip], folder, cancel)
        clips.append(clip)
        cursor += duration
    target = project["target_seconds"]
    events.append((0, target, "Label", "AI 생성 삽화"))
    events.append((target - 2, target, "Source", "출처: " + wrap_caption(project["source"][:110], 27)))
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Subtitle,Malgun Gothic,44,&H00FFFFFF,&H00FFFFFF,&H00201712,&HAA201712,-1,0,0,0,100,100,0,0,3,12,0,2,55,55,210,1
Style: Heading,Malgun Gothic,42,&H00FFFFFF,&H00FFFFFF,&H88201712,&H88201712,-1,0,0,0,100,100,0,0,1,2,0,8,60,60,165,1
Style: Label,Malgun Gothic,25,&H00C3E392,&H00FFFFFF,&H00201712,&H00201712,0,0,0,0,100,100,0,0,1,1,0,8,50,50,92,1
Style: Source,Malgun Gothic,28,&H00FFFFFF,&H00FFFFFF,&H00201712,&HAA201712,0,0,0,0,100,100,0,0,3,8,0,2,50,50,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [f"Dialogue: 0,{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{ass_escape(t)}" for a, b, style, t in events]
    (folder / "captions.ass").write_text(header + "\n".join(lines), "utf-8-sig")
    srt = []
    for i, entry in enumerate(subtitles):
        srt.append(f'{i + 1}\n{srt_time(entry["start"])} --> {srt_time(entry["end"])}\n{wrap_caption(entry["text"],18)}\n')
    (folder / "subtitles.srt").write_text("\n".join(srt), "utf-8-sig")
    (folder / "concat.txt").write_text("\n".join(f"file '{clip}'" for clip in clips), "utf-8")
    progress(91, "장면을 연결하고 한글 자막을 넣는 중")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", "narration-timed.wav",
                "-map", "0:v:0", "-map", "1:a:0", "-vf", "ass=captions.ass",
                "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "22", "-threads", "4", "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
                "-movflags", "+faststart", "-t", str(target), "output.pending.mp4"], folder, cancel)
    checkpoint(cancel)
    probe = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_streams", "-show_format",
                            "-of", "json", "output.pending.mp4"], cwd=folder, capture_output=True, text=True, check=True)
    metadata = json.loads(probe.stdout)
    actual = float(metadata["format"]["duration"])
    video = next(x for x in metadata["streams"] if x["codec_type"] == "video")
    if abs(actual - target) > 0.3 or video["width"] != 720 or video["height"] != 1280:
        raise RuntimeError("완성 영상의 길이 또는 해상도 검증에 실패했습니다.")
    if not any(x["codec_type"] == "audio" for x in metadata["streams"]):
        raise RuntimeError("완성 영상에 오디오가 없습니다.")
    os.replace(folder / "output.pending.mp4", folder / "shorts.mp4")
    result = {"duration": actual, "width": 720, "height": 1280, "fps": 30, "speech_speed": speed,
              "bytes": (folder / "shorts.mp4").stat().st_size, "captions": subtitles,
              "voice_pipeline": narration["voice_pipeline"], "caption_timing": narration["caption_timing"],
              "scene_timing": narration["scenes"]}
    (folder / "render.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    return result

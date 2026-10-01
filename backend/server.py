from __future__ import annotations

import copy
import json
import logging
import os
import re
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, RLock, Thread

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse

from domain import CreateProject, EditScenes, factual_warnings, paragraphs
from inference import Cancelled, checkpoint, generate_draft, generate_images, synthesize
from media import render_video
from firebase_service import current_user, public_settings, write_project

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("SHORTORY_DATA", str(BASE / "data"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
lock = RLock()
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="shortory-ai")
events: dict[str, Event] = {}
ACTIVE = {"queued", "scripting", "generating", "cancel_requested"}
log = logging.getLogger("shortory")
sync_wake = Event()
sync_stop = Event()


def folder_for(project_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", project_id):
        raise HTTPException(404, "작업을 찾을 수 없습니다.")
    folder = DATA / project_id
    if not (folder / "project.json").exists():
        raise HTTPException(404, "작업을 찾을 수 없습니다.")
    return folder


def read(project_id: str) -> dict:
    with lock:
        return json.loads((folder_for(project_id) / "project.json").read_text("utf-8"))


def save(project: dict, *, sync: bool = True):
    with lock:
        if sync and project.get('owner_uid'):
            project['_sync_pending'] = True
            project['_sync_version'] = project.get('_sync_version', 0) + 1
            project['db_sync'] = 'pending'
        folder = DATA / project["id"]
        folder.mkdir(exist_ok=True)
        tmp = folder / "project.pending.json"
        tmp.write_text(json.dumps(project, ensure_ascii=False, indent=2), "utf-8")
        os.replace(tmp, folder / "project.json")
    if sync:
        sync_wake.set()


def update(project_id: str, **fields):
    with lock:
        project = read(project_id)
        project.update(fields, updated_at=time.time())
        # Progress is polled locally. Persist important state changes to Firestore.
        save(project, sync=not set(fields).issubset({'progress', 'message'}))


def owned(project_id: str, uid: str) -> dict:
    project = read(project_id)
    if project.get('owner_uid') != uid:
        # Do not disclose that another user's record exists.
        raise HTTPException(404, '작업을 찾을 수 없습니다.')
    return project


def public(project: dict) -> dict:
    return {k: v for k, v in project.items() if not k.startswith('_')}


def sync_once():
    """Durable outbox: retry after outage/restart, never fail a completed video."""
    for f in DATA.glob('*/project.json'):
        if sync_stop.is_set():
            return
        try:
            snapshot = read(f.parent.name)
            if not snapshot.get('owner_uid') or not snapshot.get('_sync_pending'):
                continue
            write_project(public(snapshot))
            with lock:
                latest = read(snapshot['id'])
                if latest.get('_sync_version') == snapshot.get('_sync_version'):
                    latest.update(_sync_pending=False, db_sync='synced', db_synced_at=time.time())
                    save(latest, sync=False)
        except Exception as exc:
            # Log the failure type only; credentials, token, and article stay private.
            log.warning('Firestore sync will retry: %s (%s)', f.parent.name, type(exc).__name__)


def sync_loop():
    while not sync_stop.is_set():
        sync_wake.wait(30)
        sync_wake.clear()
        if sync_stop.wait(1):
            break
        sync_once()


def worker(project_id: str, kind: str, event: Event):
    start = time.perf_counter()
    def progress(value, message):
        checkpoint(event)
        update(project_id, progress=value, message=message)
    try:
        checkpoint(event)
        update(project_id, status="scripting" if kind == "draft" else "generating", error=None)
        project = read(project_id)
        if kind == "draft":
            scenes = generate_draft(project, progress, event)
            checkpoint(event)
            update(project_id, scenes=scenes, status="draft_ready", progress=100, message="대본을 확인하고 영상을 생성해 주세요.",
                   warnings=factual_warnings(scenes, project["text"]), result=None)
        else:
            folder = folder_for(project_id)
            generate_images(project, folder, progress, event)
            audio = synthesize(project, folder, progress, event)
            duration = sum(record["duration"] for record in audio)
            speech_budget = project["target_seconds"] - 2 - 0.12 * len(audio)
            if duration > 0 and not speech_budget * 0.70 <= duration <= speech_budget * 1.25:
                # Use measured TTS timing to improve the draft automatically. Failure
                # to rewrite must not prevent valid existing audio from becoming a video.
                try:
                    progress(65, "목표 길이에 맞게 대본을 자동으로 조정하는 중")
                    characters = sum(len(scene["narration"]) for scene in project["scenes"])
                    characters = max(12 * len(audio), min(280 * len(audio),
                                     round(characters * speech_budget * 0.94 / duration)))
                    scenes = generate_draft(project,
                        lambda _value, _message: progress(65, "원문을 바탕으로 대본 분량을 맞추는 중"), event,
                        narration_characters=characters, existing_scenes=project["scenes"])
                    checkpoint(event)
                    adjusted = {**project, "scenes": scenes}
                    adjusted_folder = folder / "timing-adjusted"
                    adjusted_folder.mkdir(exist_ok=True)
                    adjusted_audio = synthesize(adjusted, adjusted_folder,
                        lambda _value, message: progress(66, message), event)
                    checkpoint(event)
                    adjusted_duration = sum(record["duration"] for record in adjusted_audio)
                    if abs(adjusted_duration - speech_budget) < abs(duration - speech_budget):
                        project, audio = adjusted, adjusted_audio
                        update(project_id, scenes=scenes, warnings=factual_warnings(scenes, project["text"]),
                               message="대본과 음성 길이를 자동으로 맞췄습니다.")
                except Cancelled:
                    raise
                except Exception as exc:
                    log.warning("Automatic narration adjustment skipped: %s", type(exc).__name__)
                    progress(66, "음성 속도와 장면 길이를 자동으로 맞추는 중")
            result = render_video(project, folder, audio, progress, event)
            checkpoint(event)
            update(project_id, status="completed", progress=100, message="숏츠가 완성됐습니다.", result=result)
        update(project_id, last_run_seconds=round(time.perf_counter() - start, 2))
    except Cancelled:
        update(project_id, status="cancelled", message="작업을 취소했습니다. 저장된 단계부터 다시 시도할 수 있습니다.")
    except Exception as exc:
        log.exception("Job failed: %s", project_id)
        update(project_id, status="failed", message="작업을 완료하지 못했습니다.", error=str(exc)[:2400])
    finally:
        with lock:
            events.pop(project_id, None)


def enqueue(project_id: str, kind: str):
    with lock:
        project = read(project_id)
        if project["status"] in ACTIVE or project_id in events:
            raise HTTPException(409, "이미 진행 중인 작업입니다.")
        if len(events) >= 5:
            raise HTTPException(429, "대기 중인 작업이 많습니다. 잠시 후 다시 시도해 주세요.")
        event = Event()
        events[project_id] = event
        update(project_id, status="queued", task=kind, progress=0, error=None, result=None,
               message="앞선 작업이 끝나면 시작합니다.")
        executor.submit(worker, project_id, kind, event)


@asynccontextmanager
async def lifespan(_app):
    sync_stop.clear()
    for f in DATA.glob("*/project.json"):
        project = json.loads(f.read_text("utf-8"))
        if project["status"] in ACTIVE:
            update(project["id"], status="failed", error="PC 서버가 중단됐습니다. 다시 시도해 주세요.", message="이전 작업이 중단되었습니다.")
    sync_thread = Thread(target=sync_loop, daemon=True, name='shortory-firestore')
    sync_thread.start()
    sync_wake.set()
    yield
    sync_stop.set()
    sync_wake.set()
    with lock:
        for event in events.values():
            event.set()
    executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="Shortory local AI", version="2.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    lock_path = BASE / "models.lock.json"
    models = json.loads(lock_path.read_text("utf-8")) if lock_path.exists() else {}
    return {"status": "ok", "name": "쇼토리 로컬 AI", "models_ready": all(k in models for k in ("llm", "image", "tts")),
            "models": models, "ffmpeg": bool(shutil.which("ffmpeg")), "active_jobs": len(events),
            "privacy": "local-ai-firebase-records", "api_version": 2,
            "auth_required": True, "firebase": public_settings()}


@app.get("/projects")
def list_projects(uid: str = Depends(current_user)):
    with lock:
        projects = [json.loads(f.read_text("utf-8")) for f in DATA.glob("*/project.json")]
    return sorted([public(p) for p in projects if p.get('owner_uid') == uid], key=lambda p: p["created_at"], reverse=True)


@app.post("/projects", status_code=201)
def create_project(body: CreateProject, uid: str = Depends(current_user)):
    now = time.time()
    project = body.model_dump()
    project.update(id=uuid.uuid4().hex, title=body.title.strip() or "새로운 이야기", source=body.source.strip() or "직접 작성한 글",
                   created_at=now, updated_at=now, status="new", progress=0, message="준비 중",
                   paragraphs=paragraphs(body.text), scenes=[], warnings=[], error=None, result=None,
                   owner_uid=uid, storage_mode='local_pc')
    save(project)
    enqueue(project["id"], "draft")
    return public(read(project["id"]))


@app.get("/projects/{project_id}")
def get_project(project_id: str, uid: str = Depends(current_user)):
    return public(owned(project_id, uid))


@app.put("/projects/{project_id}/scenes")
def edit_scenes(project_id: str, body: EditScenes, uid: str = Depends(current_user)):
    with lock:
        project = owned(project_id, uid)
        if project["status"] in ACTIVE or project_id in events:
            raise HTTPException(409, "진행 중인 작업은 수정할 수 없습니다.")
        valid = {p["id"] for p in project["paragraphs"]}
        if any(not set(s.source_ids).issubset(valid) for s in body.scenes):
            raise HTTPException(422, "원문 근거 문단이 올바르지 않습니다.")
        scenes = [s.model_dump() for s in body.scenes]
        update(project_id, scenes=scenes, status="draft_ready", result=None, error=None,
               warnings=factual_warnings(scenes, project["text"]), message="수정한 대본을 저장했습니다.")
    return public(read(project_id))


@app.post("/projects/{project_id}/draft")
def retry_draft(project_id: str, uid: str = Depends(current_user)):
    owned(project_id, uid)
    enqueue(project_id, "draft")
    return public(read(project_id))


@app.post("/projects/{project_id}/render")
def render(project_id: str, uid: str = Depends(current_user)):
    with lock:
        project = owned(project_id, uid)
        if not project["scenes"]:
            raise HTTPException(409, "먼저 대본을 생성해 주세요.")
        enqueue(project_id, "render")
    return public(read(project_id))


@app.post("/projects/{project_id}/cancel")
def cancel(project_id: str, uid: str = Depends(current_user)):
    with lock:
        owned(project_id, uid)
        if project_id in events:
            events[project_id].set()
            update(project_id, status="cancel_requested", message="현재 단계를 안전하게 종료하는 중")
    return public(read(project_id))


@app.post('/projects/{project_id}/sync')
def retry_sync(project_id: str, uid: str = Depends(current_user)):
    with lock:
        project = owned(project_id, uid)
        save(project)
    return public(project)


@app.get("/files/{project_id}/{name}")
def file(project_id: str, name: str, uid: str = Depends(current_user)):
    project = owned(project_id, uid)
    if name in ("shorts.mp4", "subtitles.srt"):
        if project["status"] != "completed":
            raise HTTPException(409, "현재 대본의 영상 생성이 완료되지 않았습니다.")
    elif not re.fullmatch(r"scene_\d{2}\.png", name):
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    target = folder_for(project_id) / name
    if not target.is_file():
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    media_type = {".mp4": "video/mp4", ".srt": "application/x-subrip", ".png": "image/png"}[target.suffix]
    return FileResponse(target, media_type=media_type)

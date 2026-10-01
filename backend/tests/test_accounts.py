from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import server
import firebase_service


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DATA', tmp_path)
    server.sync_stop.clear()
    return TestClient(server.app)


def project(pid='a' * 32, owner='alice'):
    return dict(id=pid, owner_uid=owner, status='completed', scenes=[], paragraphs=[],
                text='test source', title='Owned short', source='fixture', target_seconds=30,
                created_at=1, updated_at=1, progress=100, result={}, warnings=[])


def test_missing_and_invalid_token_cannot_access_files(local, monkeypatch):
    p = project()
    server.save(p)
    (server.DATA / p['id'] / 'shorts.mp4').write_bytes(b'private-video')
    assert local.get('/projects').status_code == 401
    assert local.get(f"/files/{p['id']}/shorts.mp4").status_code == 401
    monkeypatch.setattr(firebase_service, 'firebase_app', lambda: object())
    def invalid(*args, **kwargs):
        raise ValueError('bad signature')
    monkeypatch.setattr(firebase_service.auth, 'verify_id_token', invalid)
    assert local.get('/projects', headers={'Authorization': 'Bearer forged-token'}).status_code == 401


def test_other_owner_cannot_read_edit_render_cancel_or_download(local, monkeypatch):
    p = project()
    server.save(p)
    server.save(project('b' * 32, 'bob'))
    monkeypatch.setitem(server.app.dependency_overrides, server.current_user, lambda: 'bob')
    assert [x['id'] for x in local.get('/projects').json()] == ['b' * 32]
    assert local.get('/projects/' + p['id']).status_code == 404
    for action in ['draft', 'render', 'cancel', 'sync']:
        assert local.post(f"/projects/{p['id']}/{action}").status_code == 404
    for name in ['shorts.mp4', 'subtitles.srt', 'scene_01.png']:
        assert local.get(f"/files/{p['id']}/{name}").status_code == 404
    scenes = [{'id': i, 'narration': 'safe text', 'image_prompt_en': 'a cup', 'source_ids': ['P1']} for i in [1, 2]]
    assert local.put(f"/projects/{p['id']}/scenes", json={'scenes': scenes}).status_code == 404


def test_owner_bound_from_token_not_body_and_legacy_hidden(local, monkeypatch):
    monkeypatch.setitem(server.app.dependency_overrides, server.current_user, lambda: 'alice')
    monkeypatch.setattr(server, 'enqueue', lambda *_: None)
    legacy = project('c' * 32)
    del legacy['owner_uid']
    server.save(legacy)
    response = local.post('/projects', json={'text': 'A fictional article for account isolation. ' * 3, 'owner_uid': 'bob'})
    assert response.status_code == 201
    assert response.json()['owner_uid'] == 'alice'
    assert '_sync_version' not in response.json()
    assert len(local.get('/projects').json()) == 1
    assert local.get('/projects/' + legacy['id']).status_code == 404


def test_outbox_survives_failure_and_retries_latest(local, monkeypatch):
    p = project()
    server.save(p)
    writes = []
    def offline(_):
        raise ConnectionError('offline')
    monkeypatch.setattr(server, 'write_project', offline)
    server.sync_once()
    assert server.read(p['id'])['_sync_pending'] is True
    assert server.read(p['id'])['status'] == 'completed'
    monkeypatch.setattr(server, 'write_project', lambda value: writes.append(value))
    server.sync_once()
    assert server.read(p['id'])['db_sync'] == 'synced'
    assert writes[0]['owner_uid'] == 'alice'
    server.sync_once()
    assert len(writes) == 1


def test_sync_cannot_acknowledge_a_newer_unsaved_revision(local, monkeypatch):
    p = project()
    server.save(p)
    def concurrent_edit(_):
        server.update(p['id'], title='newer revision')
    monkeypatch.setattr(server, 'write_project', concurrent_edit)
    server.sync_once()
    latest = server.read(p['id'])
    assert latest['_sync_pending'] is True
    assert latest['title'] == 'newer revision'


def test_production_rejects_emulator_environment(monkeypatch):
    monkeypatch.setattr(firebase_service, 'settings', lambda: {'project_id': 'production-project', 'emulators': False})
    monkeypatch.setenv('FIREBASE_AUTH_EMULATOR_HOST', '127.0.0.1:9199')
    with pytest.raises(RuntimeError, match='에뮬레이터'):
        firebase_service.firebase_app.__wrapped__()

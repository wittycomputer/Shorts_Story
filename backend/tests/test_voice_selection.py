import pytest
from fastapi.testclient import TestClient
import server


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DATA', tmp_path)
    monkeypatch.setitem(server.app.dependency_overrides, server.current_user, lambda: 'voice-user')
    monkeypatch.setattr(server, 'enqueue', lambda *_: None)
    return TestClient(server.app)


@pytest.mark.parametrize('voice', ['M1', 'F1'])
def test_choice_persists_and_legacy_edit_retains_it(api, voice, monkeypatch):
    response = api.post('/projects', json={'text': '새로운 목소리 선택 기능을 확인하는 가상의 기사입니다. ' * 3, 'voice': voice})
    assert response.status_code == 201
    project = response.json()
    assert project['voice'] == voice
    scenes = [{'id': i, 'narration': '한국어 내레이션입니다.', 'image_prompt_en': 'a cup on desk', 'source_ids': ['P1']} for i in [1, 2]]
    url = f"/projects/{project['id']}/scenes"
    saved = api.put(url, json={'scenes': scenes})
    assert saved.status_code == 200 and saved.json()['voice'] == voice
    other = 'F1' if voice == 'M1' else 'M1'
    changed = api.put(url, json={'scenes': scenes, 'voice': other})
    assert changed.status_code == 200 and changed.json()['voice'] == other
    assert api.get(f"/projects/{project['id']}").json()['voice'] == other
    writes = []
    monkeypatch.setattr(server, 'write_project', lambda p: writes.append(p))
    server.sync_stop.clear()
    server.sync_once()
    assert writes[-1]['voice'] == other


def test_unsupported_voice_rejected_and_missing_voice_defaults(api):
    body = {'text': '이 기사에는 목소리 선택을 검증하기 위한 가상의 내용이 담겨 있습니다. ' * 2}
    assert api.post('/projects', json={**body, 'voice': 'unknown'}).status_code == 422
    assert api.post('/projects', json=body).json()['voice'] == 'M1'

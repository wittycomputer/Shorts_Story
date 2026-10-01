"""Firebase identity verification and owner-scoped Firestore records.

Passwords never reach this server. Production never accepts emulator tokens.
Admin credentials belong on the PC only, never inside the Android app.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

import firebase_admin
from firebase_admin import auth, credentials, firestore
from fastapi import Header, HTTPException
from google.auth.credentials import AnonymousCredentials

BASE = Path(__file__).resolve().parent


def settings() -> dict:
    path = BASE / 'firebase.local.json'
    config = json.loads(path.read_text('utf-8')) if path.exists() else {}
    config['project_id'] = os.environ.get('SHORTORY_FIREBASE_PROJECT', config.get('project_id', ''))
    config['emulators'] = os.environ.get('SHORTORY_FIREBASE_EMULATORS') == '1'
    return config


class EmulatorCredential(credentials.Base):
    def get_credential(self):
        return AnonymousCredentials()


@lru_cache(maxsize=1)
def firebase_app():
    config = settings()
    project_id = config['project_id']
    if not project_id:
        raise RuntimeError('Firebase 프로젝트 설정이 필요합니다.')
    if config['emulators']:
        if not project_id.startswith('demo-shortory'):
            raise RuntimeError('에뮬레이터는 demo-shortory 프로젝트에서만 실행할 수 있습니다.')
        os.environ.setdefault('FIREBASE_AUTH_EMULATOR_HOST', '127.0.0.1:9199')
        os.environ.setdefault('FIRESTORE_EMULATOR_HOST', '127.0.0.1:8180')
        cred = EmulatorCredential()
    else:
        if os.environ.get('FIREBASE_AUTH_EMULATOR_HOST') or os.environ.get('FIRESTORE_EMULATOR_HOST'):
            raise RuntimeError('운영 서버에는 Firebase 에뮬레이터 환경 변수를 사용할 수 없습니다.')
        credential_path = config.get('credential_path') or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        cred = credentials.Certificate(str((BASE / credential_path).resolve())) if credential_path else credentials.ApplicationDefault()
    return firebase_admin.initialize_app(cred, {'projectId': project_id}, name='shortory')


def current_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, '로그인이 필요합니다.', headers={'WWW-Authenticate': 'Bearer'})
    token = authorization[7:].strip()
    if not token or len(token) > 16384:
        raise HTTPException(401, '로그인 정보가 올바르지 않습니다.')
    try:
        app = firebase_app()
    except Exception:
        raise HTTPException(503, 'PC 서버의 Firebase 설정을 확인해 주세요.') from None
    try:
        identity = auth.verify_id_token(token, app=app, check_revoked=True)
        uid = identity.get('uid', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', uid):
            raise ValueError('Invalid user identifier')
        return uid
    except Exception:
        # Never include tokens or credential/provider exception text in responses.
        raise HTTPException(401, '로그인이 만료됐습니다. 다시 로그인해 주세요.', headers={'WWW-Authenticate': 'Bearer'}) from None


def write_project(project: dict):
    uid = project['owner_uid']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', uid):
        raise ValueError('Invalid project owner')
    data = {k: v for k, v in project.items() if not k.startswith('_')}
    data.update(db_sync='synced', storage_mode='local_pc', db_synced_at=firestore.SERVER_TIMESTAMP)
    # Paths and ownership come from the verified server record, never request JSON.
    db = firestore.client(app=firebase_app())
    db.collection('users').document(uid).collection('shorts').document(project['id']).set(data, timeout=15)


def public_settings() -> dict:
    config = settings()
    return {'project_id': config['project_id'], 'configured': bool(config['project_id']),
            'mode': 'emulator' if config['emulators'] else 'cloud', 'storage_mode': 'local_pc'}

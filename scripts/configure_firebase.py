"""Configure a checkout from the owner's Firebase files; no network or billing calls."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'com.shortory.shortory'


def load_json(path: Path) -> dict:
    try:
        result = json.loads(path.read_text('utf-8-sig'))
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (OSError, ValueError):
        raise ValueError(f'Cannot read JSON configuration: {path.name}') from None


def configure(root: Path, google_file: Path, admin_file: Path, *, overwrite=False) -> str:
    google, admin = load_json(google_file), load_json(admin_file)
    info = google.get('project_info', {})
    project = info.get('project_id')
    clients = [c for c in google.get('client', [])
               if c.get('client_info', {}).get('android_client_info', {}).get('package_name') == PACKAGE]
    if not project or not info.get('project_number') or len(clients) != 1:
        raise ValueError(f'google-services.json must contain one Android app with package {PACKAGE}.')
    client = clients[0]
    keys = client.get('api_key', [])
    if not client.get('client_info', {}).get('mobilesdk_app_id') or not keys or not keys[0].get('current_key'):
        raise ValueError('Firebase Android app ID or public API key is missing.')
    if admin.get('type') != 'service_account' or admin.get('project_id') != project:
        raise ValueError('The Android app and service-account key must belong to the same Firebase project.')
    if (not admin.get('client_email', '').endswith('.iam.gserviceaccount.com')
            or not admin.get('private_key', '').strip().startswith('-----BEGIN PRIVATE KEY-----')):
        raise ValueError('Use a Firebase service-account private-key JSON file for the PC server.')
    app = {'apiKey': keys[0]['current_key'],
           'appId': client['client_info']['mobilesdk_app_id'],
           'messagingSenderId': str(info['project_number']), 'projectId': project}
    outputs = {
        root / 'config/firebase.json': json.dumps(app, indent=2).encode(),
        root / 'android/app/google-services.json': json.dumps(google, indent=2).encode(),
        root / '.secrets/firebase-admin.json': json.dumps(admin, indent=2).encode(),
        root / 'backend/firebase.local.json': json.dumps({'project_id': project, 'credential_path': '../.secrets/firebase-admin.json'}, indent=2).encode(),
        root / '.firebaserc': json.dumps({'projects': {'default': project}}, indent=2).encode(),
    }
    existing = [p for p in outputs if p.exists()]
    # setup.bat's blank public placeholder may be replaced on first configuration.
    placeholder = root / 'config/firebase.json'
    if placeholder in existing and not load_json(placeholder).get('projectId'):
        existing.remove(placeholder)
    if existing and not overwrite:
        raise ValueError('Firebase settings already exist. Use --overwrite only to intentionally replace this checkout configuration.')
    for target, data in outputs.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        staged = target.with_name(target.name + '.new')
        staged.write_bytes(data)
        if target.parent.name == '.secrets':
            os.chmod(staged, 0o600)
        os.replace(staged, target)
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--google-services', required=True, type=Path)
    parser.add_argument('--service-account', required=True, type=Path)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        project = configure(args.root.resolve(), args.google_services.resolve(), args.service_account.resolve(), overwrite=args.overwrite)
    except ValueError as exc:
        parser.exit(1, f'Setup error: {exc}\n')
    print(f'Configured project: {project}. Private key remains in this checkout .secrets directory.')
    print('No external project creation, IAM change, billing change, or deployment was performed.')


if __name__ == '__main__':
    main()

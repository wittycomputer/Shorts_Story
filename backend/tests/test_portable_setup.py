"""Fresh-user configuration and publication safety checks, using synthetic files only."""
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup = script('configure_firebase')
packager = script('package_source')


@pytest.fixture
def firebase_files(tmp_path):
    google = tmp_path / 'google-services.json'
    admin = tmp_path / 'admin.json'
    google.write_text(json.dumps({'project_info': {'project_id': 'other-person-project', 'project_number': '123'},
        'client': [{'client_info': {'mobilesdk_app_id': '1:123:android:abc',
            'android_client_info': {'package_name': 'com.shortory.shortory'}},
            'api_key': [{'current_key': 'public-demo-key'}]}]}), encoding='utf-8')
    admin.write_text(json.dumps({'type': 'service_account', 'project_id': 'other-person-project',
        'client_email': 'server@other-person-project.iam.gserviceaccount.com',
        'private_key': '-----BEGIN PRIVATE KEY-----\nSYNTHETIC_TEST_ONLY\n-----END PRIVATE KEY-----\n'}), encoding='utf-8')
    return google, admin


def test_new_user_configuration_and_private_key_separation(tmp_path, firebase_files):
    checkout = tmp_path / 'fresh-checkout'
    (checkout / 'config').mkdir(parents=True)
    (checkout / 'config/firebase.json').write_text('{"projectId":""}', encoding='utf-8')
    assert setup.configure(checkout, *firebase_files) == 'other-person-project'
    public = json.loads((checkout / 'config/firebase.json').read_text())
    assert public['projectId'] == 'other-person-project'
    assert public['apiKey'] == 'public-demo-key'
    assert 'private_key' not in public
    backend = json.loads((checkout / 'backend/firebase.local.json').read_text())
    assert backend['project_id'] == public['projectId']
    assert (checkout / 'backend' / backend['credential_path']).is_file()
    assert json.loads((checkout / '.firebaserc').read_text())['projects']['default'] == public['projectId']
    assert json.loads((checkout / 'android/app/google-services.json').read_text())['project_info']['project_id'] == public['projectId']


def test_mixed_project_keys_rejected_without_writing(tmp_path, firebase_files):
    google, admin = firebase_files
    key = json.loads(admin.read_text())
    key['project_id'] = 'somebody-elses-project'
    admin.write_text(json.dumps(key))
    checkout = tmp_path / 'rejected-checkout'
    with pytest.raises(ValueError, match='same Firebase project'):
        setup.configure(checkout, google, admin)
    assert not checkout.exists()


def test_existing_configuration_requires_explicit_overwrite(tmp_path, firebase_files):
    checkout = tmp_path / 'configured-checkout'
    setup.configure(checkout, *firebase_files)
    private = checkout / '.secrets/firebase-admin.json'
    before = private.read_bytes()
    with pytest.raises(ValueError, match='already exist'):
        setup.configure(checkout, *firebase_files)
    assert private.read_bytes() == before


def test_source_zip_excludes_credentials_machine_paths_and_generated_files(tmp_path):
    root = tmp_path / 'source'
    allowed = ['README.md', '.gitignore', 'android/.gitignore', 'config/firebase.example.json', 'backend/server.py',
               'backend/requirements.txt', 'backend/requirements.lock.txt',
               'scripts/setup.ps1', 'android/gradlew', 'android/gradle/wrapper/gradle-wrapper.jar',
               'android/app/src/main/kotlin/com/shortory/shortory/MainActivity.kt']
    excluded = ['.secrets/firebase-admin.json', 'config/firebase.json', 'backend/firebase.local.json',
                'android/app/google-services.json', 'android/local.properties', 'android/key.properties',
                'android/app/.cxx/generated.json', '.firebaserc',
                'backend/data/user/project.json', 'backend/.venv/private.py', 'build/app.apk',
                'scripts/provision-firebase.cjs', 'scripts/verify-firebase-cloud.py']
    for name in allowed + excluded:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{}' if target.suffix == '.json' else 'fixture', encoding='utf-8')
    output = tmp_path / 'source.zip'
    packager.export(root, output)
    with ZipFile(output) as archive:
        assert set(archive.namelist()) == {'shortory/' + name for name in allowed}


def test_source_zip_refuses_private_key_in_unexpected_source_json(tmp_path):
    root = tmp_path / 'source'
    (root / 'config').mkdir(parents=True)
    (root / 'config/accidental-key.json').write_text('{"private_key":"do-not-publish"}', encoding='utf-8')
    output = tmp_path / 'refused.zip'
    with pytest.raises(ValueError, match='Private-key content'):
        packager.export(root, output)
    assert not output.exists()

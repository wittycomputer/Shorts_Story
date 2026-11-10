import json
import download_models


def test_changing_model_repo_does_not_reuse_old_repository_revision(tmp_path, monkeypatch):
    lock = tmp_path / 'models.lock.json'
    lock.write_text(json.dumps({'tts': {'repo': 'facebook/mms-tts-kor', 'revision': 'old-mms-revision'}}))
    calls = []
    class Api:
        def model_info(self, repo):
            assert repo == 'supertone-oss-archive/supertonic-3'
            return type('Info', (), {'sha': 'new-supertonic-revision'})()
    monkeypatch.setattr(download_models, 'BASE', tmp_path)
    monkeypatch.setattr(download_models, 'MODELS', {'tts': download_models.MODELS['tts']})
    monkeypatch.setattr(download_models, 'HfApi', Api)
    monkeypatch.setattr(download_models, 'snapshot_download', lambda repo, **kwargs: calls.append((repo, kwargs)))
    download_models.main()
    assert calls[0][1]['revision'] == 'new-supertonic-revision'
    assert json.loads(lock.read_text())['tts']['repo'] == 'supertone-oss-archive/supertonic-3'
    download_models.main()
    assert calls[1][1]['revision'] == 'new-supertonic-revision'

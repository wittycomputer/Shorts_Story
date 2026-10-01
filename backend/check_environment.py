"""Offline preflight for a fresh checkout. Does not download or modify Firebase."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent


def read_json(path: Path) -> dict:
    return json.loads(path.read_text('utf-8-sig'))


def check_gpu() -> str:
    import torch
    if not torch.cuda.is_available():
        raise ValueError('CUDA GPU unavailable. Use a supported NVIDIA GPU/driver and run setup.bat (CUDA PyTorch).')
    gpu = torch.cuda.get_device_properties(0)
    return f'{gpu.name}, {gpu.total_memory / 1024**3:.1f} GB VRAM; torch {torch.__version__}'


def check_ffmpeg() -> str:
    exe = shutil.which('ffmpeg')
    if not exe or not shutil.which('ffprobe'):
        raise ValueError('Add ffmpeg and ffprobe to PATH, then reopen the terminal.')
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    result = subprocess.run([exe, '-hide_banner', '-filters'], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=15, **flags)
    if result.returncode or not any(' ass ' in line for line in result.stdout.splitlines()):
        raise ValueError('Install a full FFmpeg build with the libass subtitle filter.')
    encoders = subprocess.run([exe, '-hide_banner', '-encoders'], capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=15, **flags)
    if encoders.returncode or not all(any(f' {name} ' in line for line in encoders.stdout.splitlines()) for name in ('libx264', 'aac')):
        raise ValueError('Install a full FFmpeg build with libx264 and AAC encoders.')
    fonts = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
    if not (fonts / 'malgun.ttf').is_file():
        raise ValueError('Install the Windows Korean font Malgun Gothic for Korean subtitles.')
    return 'ffmpeg + ffprobe + libass + H.264/AAC + Malgun Gothic'


def check_models() -> str:
    from huggingface_hub import snapshot_download
    lock = read_json(BASE / 'models.lock.json')
    for role in ('llm', 'image', 'tts'):
        entry = lock[role]
        location = Path(snapshot_download(entry['repo'], revision=entry['revision'], local_files_only=True))
        if role == 'image':
            required = ['model_index.json', 'scheduler/scheduler_config.json',
                        'tokenizer/tokenizer_config.json', 'tokenizer/vocab.json', 'tokenizer/merges.txt',
                        'tokenizer_2/tokenizer_config.json', 'tokenizer_2/vocab.json', 'tokenizer_2/merges.txt',
                        'text_encoder/config.json', 'text_encoder/model.fp16.safetensors',
                        'text_encoder_2/config.json', 'text_encoder_2/model.fp16.safetensors',
                        'unet/config.json', 'unet/diffusion_pytorch_model.fp16.safetensors',
                        'vae/config.json', 'vae/diffusion_pytorch_model.fp16.safetensors']
        else:
            required = ['config.json', 'tokenizer_config.json']
            required += ['tokenizer.json', 'vocab.json', 'merges.txt'] if role == 'llm' else ['vocab.json']
            index = location / 'model.safetensors.index.json'
            if index.is_file():
                required += sorted(set(read_json(index)['weight_map'].values()))
            else:
                required += ['model.safetensors']
        if any(not (location / name).is_file() for name in required):
            raise ValueError(f'{role} cache is incomplete. Run setup.bat again to resume downloads.')
    return 'Qwen3-4B, SDXL-Turbo, MMS-TTS Korean (locked revisions, local cache)'


def check_firebase() -> str:
    from firebase_admin import credentials
    from firebase_service import settings
    app = read_json(ROOT / 'config/firebase.json')
    config = settings()
    project = config.get('project_id')
    if not project or app.get('projectId') != project or any(not app.get(k) for k in ('apiKey', 'appId', 'messagingSenderId')):
        raise ValueError('App and server Firebase settings are missing or differ. Run setup_firebase.bat.')
    if config['emulators']:
        raise ValueError('Normal startup expects your own Firebase project. Remove Firebase emulator environment variables.')
    if os.environ.get('FIREBASE_AUTH_EMULATOR_HOST') or os.environ.get('FIRESTORE_EMULATOR_HOST'):
        raise ValueError('Remove Firebase emulator environment variables before normal startup.')
    key_path = config.get('credential_path') or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not key_path:
        raise ValueError('PC service-account key missing. Run setup_firebase.bat.')
    key_path = (BASE / key_path).resolve()
    key = read_json(key_path)
    if key.get('type') != 'service_account' or key.get('project_id') != project:
        raise ValueError('PC service-account key and app must belong to the same Firebase project.')
    try:
        credentials.Certificate(str(key_path))
    except Exception:
        raise ValueError('Invalid PC service-account key. Download a valid key from your own project.') from None
    return f'{project}: matching app/server settings and parseable PC credential (offline check)'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-models', action='store_true')
    parser.add_argument('--skip-firebase', action='store_true')
    args = parser.parse_args()
    checks = [('NVIDIA GPU', check_gpu), ('Video tools', check_ffmpeg)]
    if not args.skip_models:
        checks.append(('Local models', check_models))
    if not args.skip_firebase:
        checks.append(('Firebase', check_firebase))
    failed = False
    for name, check in checks:
        try:
            print(f'OK   {name}: {check()}', flush=True)
        except Exception as exc:
            failed = True
            message = str(exc) if isinstance(exc, ValueError) else f'{type(exc).__name__}: run setup.bat / setup_firebase.bat and retry.'
            print(f'FAIL {name}: {message}', flush=True)
    if not failed:
        print('Checks passed. Auth provider, Firestore creation and deployed rules still require Firebase console/CLI setup.')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())

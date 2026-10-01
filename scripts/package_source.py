"""Export a standalone source ZIP without local settings, credentials or generated data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    '.gitignore', '.metadata', 'README.md', 'analysis_options.yaml', 'pubspec.yaml', 'pubspec.lock',
    'firebase.json', 'firestore.rules', 'firestore.indexes.json', 'package.json', 'package-lock.json',
    'setup.bat', 'setup_firebase.bat', 'check_setup.bat', 'start_server.bat', 'open_android_studio.bat',
}
SOURCE_DIRS = {'android', 'backend', 'config', 'docs', 'lib', 'scripts', 'test'}
SKIP_DIRS = {'.git', '.secrets', '.venv', 'data', '__pycache__', '.pytest_cache', '.gradle',
             '.idea', '.dart_tool', '.firebase', '.tools', '.cxx', 'build', 'captures', 'dist', 'node_modules'}
PRIVATE_FILES = {'config/firebase.json', 'config/local-tools.json', 'android/app/google-services.json',
                 'android/local.properties', 'backend/firebase.local.json',
                 'scripts/provision-firebase.cjs', 'scripts/verify-firebase-cloud.py'}
EXTENSIONS = {'.py', '.cjs', '.ps1', '.md', '.png', '.kt', '.kts', '.properties', '.json', '.jar', '.xml',
              '.dart', '.yaml', '.lock', '.bat', '.rules', '.txt'}


def source_files(root: Path) -> list[Path]:
    root = root.resolve()
    files = [root / name for name in ROOT_FILES if (root / name).is_file()]
    for directory in sorted(SOURCE_DIRS):
        if not (root / directory).is_dir():
            continue
        for current, directories, names in os.walk(root / directory, followlinks=False):
            directories[:] = sorted(d for d in directories if d not in SKIP_DIRS and not (Path(current) / d).is_symlink())
            for name in sorted(names):
                path = Path(current) / name
                relative = path.relative_to(root).as_posix()
                if relative in PRIVATE_FILES or name in {'local.properties', 'key.properties'}:
                    continue
                if path.suffix not in EXTENSIONS and relative != 'android/gradlew' and name != '.gitignore':
                    continue
                files.append(path)
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Refusing to package a source file outside the checkout.')
        if path.stat().st_size > 5 * 1024**2:
            raise ValueError(f'Unexpected large source file: {path.relative_to(root)}')
        if path.suffix == '.json':
            data = json.loads(path.read_text('utf-8-sig'))
            serialized = json.dumps(data)
            if '"private_key"' in serialized or '-----BEGIN PRIVATE KEY-----' in serialized:
                raise ValueError(f'Private-key content found in source JSON: {path.relative_to(root)}')
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def export(root: Path, output: Path) -> int:
    root = root.resolve()
    files = source_files(root)  # Validate every file before opening the output ZIP.
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'shortory/' + path.relative_to(root).as_posix())
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/shortory-source.zip')
    args = parser.parse_args()
    count = export(args.root, args.output)
    print(f'Exported {count} source files: {args.output.resolve()}')
    print('Local Firebase settings, private keys, model weights, videos and Python environments are excluded.')


if __name__ == '__main__':
    main()

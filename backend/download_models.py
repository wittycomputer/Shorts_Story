"""Download only files used by inference and record immutable HF revisions."""
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
from huggingface_hub import HfApi, snapshot_download
BASE = Path(__file__).resolve().parent
MODELS = {
    "llm": ("Qwen/Qwen3-4B", ["*.json", "*.safetensors", "*.txt", "*.model", "merges.txt"]),
    "image": ("stabilityai/sdxl-turbo", ["model_index.json", "scheduler/*", "tokenizer/*", "tokenizer_2/*", "text_encoder/config.json", "text_encoder/model.fp16.safetensors", "text_encoder_2/config.json", "text_encoder_2/model.fp16.safetensors", "unet/config.json", "unet/diffusion_pytorch_model.fp16.safetensors", "vae/config.json", "vae/diffusion_pytorch_model.fp16.safetensors"]),
    "tts": ("facebook/mms-tts-kor", ["*.json", "*.safetensors", "*.txt"]),
}


def main():
    lock_file = BASE / "models.lock.json"
    lock = json.loads(lock_file.read_text("utf-8")) if lock_file.exists() else {}
    api = HfApi()
    for role, (repo, patterns) in MODELS.items():
        revision = lock.get(role, {}).get("revision") or api.model_info(repo).sha
        print(f"Downloading {role}: {repo} @ {revision}", flush=True)
        snapshot_download(repo, revision=revision, allow_patterns=patterns, max_workers=3)
        lock[role] = {"repo": repo, "revision": revision}
        lock_file.write_text(json.dumps(lock, indent=2), "utf-8")
        print(f"Ready: {role}", flush=True)


if __name__ == "__main__":
    main()

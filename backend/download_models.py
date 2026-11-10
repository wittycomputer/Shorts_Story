"""Download only files used by inference and record immutable HF revisions."""
import json
import os
from pathlib import Path
import runtime_paths  # Configure the local cache before importing HF libraries.

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
from huggingface_hub import HfApi, snapshot_download
BASE = Path(__file__).resolve().parent
MODELS = {
    "llm": ("Qwen/Qwen3-4B", ["*.json", "*.safetensors", "*.txt", "*.model", "merges.txt"]),
    "image": ("stabilityai/sdxl-turbo", ["model_index.json", "scheduler/*", "tokenizer/*", "tokenizer_2/*", "text_encoder/config.json", "text_encoder/model.fp16.safetensors", "text_encoder_2/config.json", "text_encoder_2/model.fp16.safetensors", "unet/config.json", "unet/diffusion_pytorch_model.fp16.safetensors", "vae/config.json", "vae/diffusion_pytorch_model.fp16.safetensors"]),
    "tts": ("supertone-oss-archive/supertonic-3", ["onnx/*", "voice_styles/*.json", "config.json", "LICENSE"]),
}


def main():
    lock_file = BASE / "models.lock.json"
    lock = json.loads(lock_file.read_text("utf-8")) if lock_file.exists() else {}
    api = HfApi()
    for role, (repo, patterns) in MODELS.items():
        entry = lock.get(role, {})
        # A revision belongs to its repository: an old MMS lock must not be
        # reused as a revision of the replacement Korean speech model.
        revision = entry.get("revision") if entry.get("repo") == repo else None
        revision = revision or api.model_info(repo).sha
        print(f"Downloading {role}: {repo} @ {revision}", flush=True)
        snapshot_download(repo, revision=revision, allow_patterns=patterns, max_workers=3)
        lock[role] = {"repo": repo, "revision": revision}
        lock_file.write_text(json.dumps(lock, indent=2), "utf-8")
        print(f"Ready: {role}", flush=True)


if __name__ == "__main__":
    main()

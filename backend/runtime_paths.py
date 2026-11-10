"""Use the assignment's relocated model cache when it is present."""
import os
from pathlib import Path

assignment_cache = Path(__file__).resolve().parents[2] / '.models' / 'huggingface' / 'hub'
if assignment_cache.is_dir():
    os.environ.setdefault('HF_HUB_CACHE', str(assignment_cache))

"""
env_bootstrap.py

Shared helper so first-time setup doesn't require a manual ``cp .env.example
.env`` step. If ``TASK_DIR/.env`` is missing but ``TASK_DIR/.env.example`` is
present, the example file is copied to ``.env``. Existing ``.env`` files are
never overwritten.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def ensure_env_file(task_dir: Path) -> Path:
    """
    Copy .env.example to .env in task_dir if .env does not already exist.

    Returns the path to the .env file (whether it already existed, was just
    created, or still does not exist because no .env.example was found).
    """

    env_file = task_dir / ".env"
    env_example = task_dir / ".env.example"

    if not env_file.exists() and env_example.exists():
        shutil.copyfile(env_example, env_file)

    return env_file

from __future__ import annotations

import os
from pathlib import Path


def load_backend_env() -> None:
    """
    Load key-value pairs from backend/.env into process environment if not
    already set by the shell.
    """
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        cleaned = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, cleaned)

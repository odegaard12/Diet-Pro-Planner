"""Single source of truth for version, runtime paths and tunables.

Every module reads paths from here so the app never depends on the current
working directory. All values can be overridden with environment variables,
which also lets tests run against a throwaway data directory.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Diet Pro Planner"
VERSION = "v0.3.2"

BASE_DIR = Path(__file__).resolve().parent


def _env_path(name: str, default: Path) -> Path:
    raw = str(os.environ.get(name) or "").strip()
    return Path(raw).expanduser() if raw else default


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name) or default).strip())
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


DATA_DIR = _env_path("DPP_DATA_DIR", BASE_DIR / "data")
DB_PATH = _env_path("DPP_DB", _env_path("DPP_DB_PATH", DATA_DIR / "dieta.db"))
PANTRY_PATH = _env_path("DPP_PANTRY", DATA_DIR / "pantry.json")
UPLOADS_DIR = DATA_DIR / "uploads"
BACKUPS_DIR = _env_path("DPP_BACKUP_DIR", DATA_DIR / "backups")

# Uploads: label photos from a phone camera are typically 2-6 MB.
MAX_UPLOAD_MB = _env_int("DPP_MAX_UPLOAD_MB", 15, 1, 100)
# Automatic daily SQLite snapshots kept in BACKUPS_DIR (0 disables them).
BACKUP_KEEP = _env_int("DPP_BACKUP_KEEP", 14, 0, 365)


def ensure_dirs() -> None:
    for path in (DATA_DIR, UPLOADS_DIR):
        path.mkdir(parents=True, exist_ok=True)

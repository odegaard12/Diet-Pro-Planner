"""Test environment: import this first in every test module.

Runs the app against a throwaway data directory so tests never touch the
real data/dieta.db or data/pantry.json (they used to overwrite the pantry).
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "DPP_TEST_DATA_DIR" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="dpp-tests-")
    atexit.register(shutil.rmtree, _tmp, ignore_errors=True)
    os.environ["DPP_TEST_DATA_DIR"] = _tmp
    os.environ["DPP_DATA_DIR"] = _tmp
    for key in ("DPP_DB", "DPP_DB_PATH", "DPP_PANTRY", "DPP_BACKUP_DIR", "DPP_TRUSTED_PROXIES",
                "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "DPP_AI_PROVIDER", "DPP_AI_BASE_URL", "DPP_AI_MODEL"):
        os.environ.pop(key, None)
    os.environ["DPP_AUTH_TOKEN"] = "test-token"
    os.environ["DPP_DISABLE_BACKGROUND_JOBS"] = "1"
    os.environ["DPP_OFF_ENABLED"] = "1"

DATA_DIR = Path(os.environ["DPP_TEST_DATA_DIR"])
AUTH = {"Authorization": "Bearer test-token"}

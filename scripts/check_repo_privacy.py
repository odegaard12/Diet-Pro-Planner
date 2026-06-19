#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath


EXACT_FORBIDDEN = {
    ".env",
    "data/dieta.db",
    "data/pantry.json",
    "data/strava_tokens.json",
    "data/strava_activity_cache.json",
    "data/strava_auto_sync.json",
    "data/integrations.json",
    "data/strava_ignored_ids.json",
}

FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".zip",
}

FORBIDDEN_PARTS = {
    "uploads",
    "backups",
    "__pycache__",
    ".pytest_cache",
}

ALLOWED_EXACT = {
    ".env.example",
    "data/pantry.example.json",
}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def is_forbidden(path_text: str) -> bool:
    if path_text in ALLOWED_EXACT:
        return False
    if path_text in EXACT_FORBIDDEN:
        return True

    path = PurePosixPath(path_text)
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return True
    if any(part in FORBIDDEN_PARTS for part in path.parts):
        return True
    if path.name.startswith(".env.") and path.name != ".env.example":
        return True
    if ".bak-" in path.name or path.name.endswith(".bak"):
        return True
    if path.parts and path.parts[0] == "data":
        name = path.name.lower()
        if "token" in name or "secret" in name or "cache" in name:
            return True
    return False


def main() -> int:
    forbidden = sorted(path for path in tracked_files() if is_forbidden(path))
    if forbidden:
        print("ERROR: private/local files are tracked by Git", file=sys.stderr)
        for path in forbidden:
            print(f"  - {path}", file=sys.stderr)
        return 1

    print("OK: no private runtime files are tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import re
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
    ".db-wal",
    ".db-shm",
    ".db-journal",
    ".zip",
}

FORBIDDEN_PARTS = {
    "uploads",
    "backups",
    "__pycache__",
    ".pytest_cache",
}

FORBIDDEN_NAME_PARTS = ("private_", "food_intel_audit")

ALLOWED_EXACT = {
    ".env.example",
    "data/pantry.example.json",
}

# Details that would identify the owner's network, machine or Strava activities.
CONTENT_RULES = {
    "private IPv4 address": re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
    "home directory path": re.compile(r"/home/[a-z_][\w.-]*/"),
    "Strava-like activity id": re.compile(r"(?<![\w.])1\d{10}(?![\w.])"),
}
ALLOWED_MATCHES = {"192.168.1.10"}  # documented LAN example in .env.example


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
    lowered = path.name.lower()
    if path.suffix.lower() in FORBIDDEN_SUFFIXES or any(lowered.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
        return True
    if any(part in FORBIDDEN_PARTS for part in path.parts):
        return True
    if any(part in lowered for part in FORBIDDEN_NAME_PARTS):
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


def content_problems(path_text: str, text: str) -> list[str]:
    """Return 'path:line: rule' entries; the matched value is never printed (CI logs are public)."""
    problems = []
    for label, pattern in CONTENT_RULES.items():
        for match in pattern.finditer(text):
            if match.group(0) not in ALLOWED_MATCHES:
                problems.append(f"{path_text}:{text.count(chr(10), 0, match.start()) + 1}: {label}")
    return problems


def main() -> int:
    files = tracked_files()
    forbidden = sorted(path for path in files if is_forbidden(path))
    problems = []
    for path_text in files:
        try:
            with open(path_text, encoding="utf-8") as handle:
                problems += content_problems(path_text, handle.read())
        except (OSError, UnicodeDecodeError):
            continue

    if forbidden:
        print("ERROR: private/local files are tracked by Git", file=sys.stderr)
        for path in forbidden:
            print(f"  - {path}", file=sys.stderr)
    if problems:
        print("ERROR: personal or network details in tracked files", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
    if forbidden or problems:
        return 1

    print("OK: no private runtime files or personal details are tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

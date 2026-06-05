#!/usr/bin/env python3
"""
Frontend monolith guard for Diet Pro Planner.

Goal:
- Prevent v0.0.15 from adding new huge JS/CSS files.
- Keep the existing legacy static/app.js visible as technical debt, not as a place for new features.
- Allow current legacy files temporarily while encouraging modular migration.

Policy:
- Existing legacy files may exceed the limit only if explicitly allowlisted.
- New files under static/js should stay small and focused.
"""

from __future__ import annotations

from pathlib import Path
import sys


MAX_NEW_JS_LINES = 260
MAX_NEW_CSS_LINES = 260

LEGACY_ALLOWLIST = {
    Path("static/app.js"),
    Path("static/styles.css"),
}

ROOTS = [
    Path("static/js"),
]

def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())

def main() -> int:
    errors: list[str] = []

    for root in ROOTS:
        if not root.exists():
            continue

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue

            if path.suffix not in {".js", ".css"}:
                continue

            lines = count_lines(path)
            limit = MAX_NEW_JS_LINES if path.suffix == ".js" else MAX_NEW_CSS_LINES

            if path in LEGACY_ALLOWLIST:
                continue

            if lines > limit:
                errors.append(f"{path}: {lines} lines > {limit} line limit")

    legacy_notes = []
    for path in sorted(LEGACY_ALLOWLIST):
        if path.exists():
            legacy_notes.append(f"{path}: {count_lines(path)} lines legacy allowlisted")

    if legacy_notes:
        print("Legacy allowlist:")
        for note in legacy_notes:
            print("  -", note)

    if errors:
        print("\nERROR: frontend monolith guard failed", file=sys.stderr)
        for error in errors:
            print("  -", error, file=sys.stderr)
        return 1

    print("OK: frontend monolith guard passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

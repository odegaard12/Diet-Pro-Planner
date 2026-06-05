#!/usr/bin/env python3
"""
Frontend monolith guard for Diet Pro Planner.

Goal:
- Prevent v0.0.15 from adding new huge JS/CSS files.
- Keep the existing legacy static/app.js visible as technical debt, not as a place for new features.
- Allow current legacy files temporarily, but stop them from growing further.

Policy:
- New files under static/js should stay small and focused.
- Existing legacy files are allowlisted only up to a hard line budget.
- If static/app.js needs more code, create or extend a small module instead.
"""

from __future__ import annotations

from pathlib import Path
import sys


MAX_NEW_JS_LINES = 260
MAX_NEW_CSS_LINES = 260

LEGACY_LINE_BUDGETS = {
    Path("static/app.js"): 2250,
    Path("static/styles.css"): 1800,
}

ROOTS = [
    Path("static/js"),
]


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def check_legacy_budgets() -> list[str]:
    errors: list[str] = []

    print("Legacy line budgets:")
    for path, budget in sorted(LEGACY_LINE_BUDGETS.items(), key=lambda item: str(item[0])):
        if not path.exists():
            errors.append(f"{path}: missing legacy file")
            continue

        lines = count_lines(path)
        print(f"  - {path}: {lines}/{budget} lines")

        if lines > budget:
            errors.append(
                f"{path}: {lines} lines > {budget} budget. "
                "Move code into a small module instead of growing the monolith."
            )

    return errors


def check_new_modules() -> list[str]:
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

            if lines > limit:
                errors.append(f"{path}: {lines} lines > {limit} line limit")

    return errors


def main() -> int:
    errors = []
    errors.extend(check_legacy_budgets())
    errors.extend(check_new_modules())

    if errors:
        print("\nERROR: frontend monolith guard failed", file=sys.stderr)
        for error in errors:
            print("  -", error, file=sys.stderr)
        return 1

    print("OK: frontend monolith guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

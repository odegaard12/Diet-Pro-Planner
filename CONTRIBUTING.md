# Contributing to Diet Pro Planner

Diet Pro Planner is a personal, local-first application. Contributions are welcome when they preserve privacy, keep the interface practical and avoid unnecessary architectural growth.

## Before starting

- Open or reference an issue for changes that affect data models, integrations or user-visible behavior.
- Keep pull requests small and focused.
- Do not combine unrelated refactors with a feature or bug fix.
- Prefer a new focused module over adding more code to `app.py`, `static/app.js` or `static/styles.css`.

## Privacy rules

Never commit real personal or runtime data, including:

- `.env` files or API keys;
- SQLite databases;
- Strava tokens, caches or activity exports;
- `data/pantry.json`;
- OCR uploads or product-label photos;
- backups, ZIP exports or screenshots containing personal data.

Use `.env.example`, `data/pantry.example.json` and synthetic fixtures when an example is needed.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python dpp_entrypoint.py
```

The default local URL is `http://localhost:8099`.

Docker is the recommended runtime:

```bash
docker compose up -d --build
```

## Required checks

Run the checks that apply to your branch before opening a pull request:

```bash
python -m compileall -q app.py dpp_*.py scripts tests
python scripts/check_frontend_monoliths.py
python scripts/check_repo_privacy.py
python -m unittest discover -s tests -v
```

Check JavaScript syntax:

```bash
find static -type f -name '*.js' -print0 \
  | while IFS= read -r -d '' file; do node --check "$file"; done
```

When present, also run feature-specific regression checks:

```bash
python scripts/check_v019_pantry.py
python scripts/check_v020_activity_plan.py
```

The private known-days regression script is a deployment check for the maintainer's local database. It is not expected to run in public CI.

## Pull requests

A pull request should explain:

- what problem it solves;
- what changed;
- how it was tested;
- whether it changes local data or migrations;
- any privacy or security impact;
- screenshots for meaningful UI changes, using synthetic or redacted data.

All CI checks should pass before merge.

## Product principles

- Local-first by default.
- No shared central API keys.
- External AI integrations must use BYOK and remain optional.
- Smart-scale and nutrition outputs must not be presented as medical diagnosis.
- Strava imports must remain idempotent and rate-limit aware.
- Existing private data must be preserved during upgrades.

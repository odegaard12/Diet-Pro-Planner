# Diet Pro Planner

[![CI](https://github.com/odegaard12/Diet-Pro-Planner/actions/workflows/ci.yml/badge.svg)](https://github.com/odegaard12/Diet-Pro-Planner/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Local-first](https://img.shields.io/badge/privacy-local--first-167D62)](#local-first-privacy)

**Current version:** v0.0.20  
**Latest release:** v0.0.20 — Planned versus real activity  
**License:** MIT  
**Stack:** Python · Flask · Vanilla JS · Docker · Local-first

Diet Pro Planner is a self-hosted cockpit for nutrition, body composition, sport and daily diet decisions.

It is built for private daily use on a Raspberry Pi with Docker. Public application code stays in GitHub; food logs, SQLite databases, Strava tokens, uploads, pantry contents and body-composition records stay local.

## v0.0.20 — Planned versus real activity

- Adds a dedicated **Plan deporte** weekly view.
- Plans activities by date, time, type, duration, distance, target kcal, intensity and notes.
- Matches planned sessions automatically with Strava or manual workouts.
- Shows completed, changed, pending, upcoming, missed, skipped and cancelled states.
- Shows unplanned workouts as **Extra real**.
- Adds weekly adherence, planned minutes, real minutes and real kcal summaries.
- Supports editing, skipping, reactivating and deleting activity plans.
- Stores activity plans privately in the local SQLite database.
- Prevents known duplicate Strava sessions from being imported again.
- Includes CI, Docker smoke tests, privacy guardrails and security documentation.

## v0.0.19 — Editable pantry and practical Coach actions

- Adds a professional editable pantry screen.
- Adds quick activation and manual food creation.
- Tracks availability, low stock, categories, priorities and notes.
- Adds **No tengo esto** to mark missing ingredients and recalculate the suggestion.
- Adds **Dame otra comida** with complete pantry-aware alternatives.
- Prefers solid protein for main meals when available.
- Keeps protein drinks and dairy as secondary or fallback choices.
- Stores the real pantry privately in `data/pantry.json`.
- Keeps the implementation modular without growing `app.py` or `static/app.js`.

## Core features

### Nutrition and Food Intelligence

- Meal logging by grams.
- Reusable food catalog, purchased products and meal templates.
- Weekly plan, meal history and oil tracking.
- Dry-weight pasta and rice guidance.
- Daily score, confidence labels and estimated/composite food detection.
- Local heuristic meal suggestions and next-action guidance.

### Smart Coach and pantry

- Daily Smart Coach endpoint and dashboard integration.
- Pantry-aware suggestions using only currently available foods.
- Editable availability, stock, category, priority and notes.
- **No tengo esto**, **Dame otra comida** and direct pantry access from the Coach.
- Local fallback mode without external AI.
- Future OpenAI/Gemini support follows a BYOK policy: each installation uses its own key.

### Weight and body composition

- Official and reference weight.
- Weight trend and goal progress.
- Smart-scale snapshots and trend cards.
- Fat, water, muscle, visceral fat, BMR and BioCharge / Hybrid Charge.
- Bioimpedance treated as weekly trend context, not absolute daily truth.

### Sport and Strava

- Manual workout logging.
- Strava OAuth and private web configuration.
- Manual activity import by date range.
- Protected background auto-sync.
- Duplicate protection by Strava activity ID.
- Local activity-detail cache.
- API rate-limit diagnostics and controlled HTTP 429 handling.

### OCR and food catalog

- Local Tesseract OCR.
- OCR3 label parser.
- Known-label correction and plausibility validation.
- OCR cache and local label-photo support.

## Local-first privacy

The repository contains only public application code.

Private/local files are excluded from Git, including:

- `data/`
- `uploads/`
- `*.db`
- `*.sqlite`
- `.env`
- tokens and API secrets
- backups and ZIP files
- local label photos and OCR cache files

Public CI includes a tracked-file privacy guard so these runtime files cannot be added accidentally.

## Development and security

Pull requests run Python and JavaScript checks, public route tests, the frontend anti-monolith guard, the privacy guard and a real Docker `/health` smoke test.

- Contribution workflow: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Vulnerability reporting: [`SECURITY.md`](SECURITY.md)
- CI workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- Dependency policy: [`.github/dependabot.yml`](.github/dependabot.yml)

## Docker

Build and start:

```bash
docker compose up -d --build
```

Default local URL:

```text
http://localhost:8099
```

LAN example:

```text
http://192.168.68.103:8099
```

## API summary

### Core

- `GET /health`
- `GET /api/state`
- `GET /api/insights/today`

### Food Intelligence and Smart Coach

- `GET /api/food-intel/day`
- `POST /api/food-intel/meal-plan`
- `GET /api/food-intel/health`
- `GET /api/smart-coach/day`
- `POST /api/smart-coach/alternative`
- `POST /api/smart-coach/unavailable`

### Pantry

- `GET /api/pantry`
- `POST /api/pantry`
- `GET /api/pantry/v2`
- `POST /api/pantry/v2`

### Activity planning

- `GET /api/activity-plan`
- `POST /api/activity-plan`
- `PUT /api/activity-plan/<id>`
- `DELETE /api/activity-plan/<id>`

### Body composition

- `GET /api/body-snapshot/latest`
- `GET /api/body-trends?days=45`

### Strava

- `GET /api/strava/status`
- `POST /api/strava/preview`
- `POST /api/strava/import`
- `GET /api/strava/auto-status`
- `POST /api/strava/auto-config`
- `POST /api/strava/auto-run`
- `GET /api/integrations/strava/config`
- `POST /api/integrations/strava/config`
- `GET /api/integrations/strava/diagnostics`
- `POST /api/integrations/strava/test`
- `POST /api/integrations/strava/disconnect`

## Releases

### v0.0.20 — Planned versus real activity

- Weekly planned-versus-real activity view.
- Automatic matching with Strava and manual workouts.
- Activity status, adherence and weekly volume summaries.
- Duplicate Strava-session suppression.
- CI, Docker smoke tests and privacy guardrails.

### v0.0.19 — Editable pantry and practical Coach actions

- Editable pantry from the web.
- Availability, stock, categories, priorities and notes.
- **No tengo esto** and **Dame otra comida**.
- Complete pantry-aware alternatives with solid-protein preference.

### v0.0.18 — Strava stability and web settings

- Private Strava configuration from the web.
- Stable preview/import flow with fewer API requests.
- Local detail cache, concurrency protection and rate-limit diagnostics.
- Protected recent-window auto-sync.

### v0.0.17 — Smart Coach + Pantry foundation

- Smart Coach endpoint and dashboard integration.
- Local pantry foundation.
- BYOK policy for future AI providers.
- Local fallback mode without external AI.

### v0.0.16 — Weight and Body Composition 2.0

- Standalone `/weight-2` page.
- `/api/body-trends` endpoint.
- Weight, composition and recovery trend cards.

### v0.0.15.1 — Mobile dashboard rescue and Food Intelligence truth

- Mobile dashboard rescue and fixed navigation.
- Food Intelligence truth normalization.
- BioCharge / Hybrid Charge aliases.

### Previous releases

v0.0.15, v0.0.14.2, v0.0.14.1, v0.0.14, v0.0.13, v0.0.12, v0.0.11, v0.0.10, v0.0.9, v0.0.8, v0.0.7, v0.0.6, v0.0.5, v0.0.4, v0.0.3, v0.0.2 and v0.0.1.

## Roadmap

- Automatic day closing when nutrition goals are reached.
- OpenAI/Gemini BYOK settings.
- AI response cache and daily limits.
- Strava cleanup tools for duplicates, estimates and planned activities.
- Richer weight and body-composition charts.
- Planned-versus-real meal workflow.
- OCR4 product detection and duplicate handling.
- Premium dashboard polish.
- Improved iPhone/PWA standalone installation.

## Disclaimer

This is a personal local-first project. It is not a medical device and does not provide medical diagnosis.

Smart-scale body-composition values are estimates and should be used for trends, not as absolute daily truth.

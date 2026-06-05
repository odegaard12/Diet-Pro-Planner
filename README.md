# Diet Pro Planner

**Current version:** `v0.0.15`

Diet Pro Planner is a private, local-first nutrition, weight, sport and body-composition web app designed to run on a Raspberry Pi with Docker.

The goal is to build a premium personal cockpit for daily diet decisions, closer to Apple Health + Gentler Streak + a local nutrition assistant than to a spreadsheet.

## What it helps with

- Track meals by grams.
- Track official and reference weight.
- Follow a target weight goal.
- Analyze protein, calories, oil, training and data confidence.
- Understand whether a day is good, caution or excess.
- Detect when a weight spike is probably water, food volume or training inflammation.
- Use smart-scale body-composition data as trend context.
- Suggest practical next meals with local heuristics.

## Latest release: `v0.0.15` — Dashboard refactor guardrails

`v0.0.15` starts the safe dashboard refactor phase.

### New in v0.0.15

- Adds known-day regression checks for validated real days:
  - 2026-06-03
  - 2026-06-04
  - 2026-06-05
- Adds frontend anti-monolith guardrails.
- Locks legacy frontend growth:
  - `static/app.js <= 2250` lines
  - `static/styles.css <= 1800` lines
- Adds modular frontend scaffolding under `static/js/`.
- Extracts compact meal card rendering to `static/js/dashboard/meal-card.global.js`.
- Extracts compact workout card rendering to `static/js/dashboard/workout-card.global.js`.
- Reduces the old UI cleanup patch.
- Documents v0.0.15 dashboard refactor rules.

### Previous release: `v0.0.14.2` — Dashboard meal totals and UI cleanup

`v0.0.14.2` is a stabilization hotfix for the daily dashboard after the Food Intelligence and Body Snapshot releases.

#### New in v0.0.14.2

- Meal cards now use Food Intelligence totals as the source of truth.
- Registered meals show consistent kcal and protein values.
- Technical `REAL_...` and `PLAN_...` markers are hidden from normal dashboard notes.
- False chocolate warnings from protein chocolate/cacao products are avoided.
- Private local data remains excluded from the repository.

## Food Intelligence

Introduced in `v0.0.13`.

### Endpoints

- `GET /api/food-intel/day`
- `POST /api/food-intel/meal-plan`
- `GET /api/food-intel/health`

### Capabilities

- Daily nutrition analysis.
- Confidence labels for food data:
  - exacta
  - alta
  - media
  - baja
- Detection of estimated and composite foods.
- More realistic scoring instead of false precision.
- Local heuristic meal suggestions.
- Unified dashboard with score, confidence, weight progress, protein, energy, oil, training and next-action panel.

## Core features

### Nutrition

- Meal logging by saved foods and grams.
- Reusable food catalog.
- Purchased products.
- Meal templates.
- Weekly meal plan.
- Meal history.
- Oil tracking.
- Dry-weight pasta/rice guidance.
- Protein-focused daily targets.

### Food catalog

- Brand, kcal, protein, carbs, fat, sugar, salt and typical portion.
- Product notes and source notes.
- Purchased flag.
- Local label photo support.
- Clean canonical foods for repeated products.

### OCR

- Local Tesseract OCR.
- OCR3 parser.
- Known-label correction.
- Plausibility validation.
- OCR cache.
- Photos stay local.

### Weight

- Official weight.
- Reference weight.
- Weight chart.
- Trend interpretation.
- Goal weight progress.
- Current personal target: 80 kg.

### Body Snapshot

- Optional smart-scale body-composition storage.
- Latest snapshot API.
- Dashboard summary card.
- Bioimpedance warning built into the UI.
- Designed for weekly trend interpretation.

### Sport

- Manual workout logging.
- Strava OAuth through localhost.
- Manual Strava import by date range.
- Optional Strava background auto-sync.
- Duplicate protection by Strava activity ID.
- Detailed Strava calories when available.
- Sport dashboard with 7-day summary.

### Dashboard

- Food Intelligence daily dashboard.
- Daily score.
- Semaphore state.
- Confidence label.
- Weight progress.
- Protein, energy, oil and training cards.
- Optional Body Snapshot card.
- Daily meals and activity summary.

## Local-first privacy

The repository contains only public application code.

Private/local files are excluded from Git:

- `data/`
- `uploads/`
- `*.db`
- `*.sqlite`
- `.env`
- tokens
- backups
- ZIP files
- local label photos
- OCR cache files

SQLite databases, Strava tokens, OCR uploads, body-composition records and private food logs stay on the Raspberry Pi.

## Docker

Build and start:

    docker compose up -d --build

Default local URL:

    http://localhost:8099

LAN example:

    http://192.168.68.103:8099

## Strava setup

Diet Pro Planner can connect to Strava without exposing the Raspberry Pi to the internet.

Recommended local OAuth flow:

1. Create a Strava API application.
2. Set website to `http://localhost:8099`.
3. Set authorization callback domain to `localhost`.
4. Store `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` and `STRAVA_REDIRECT_URI` in local `.env`.
5. Open an SSH tunnel:

       ssh -N -L 8099:127.0.0.1:8099 user@raspberry-ip

6. Open `http://localhost:8099`.
7. Go to Integrations → Strava → Connect Strava.

Tokens stay local under `data/`.

## API summary

Core:

- `GET /health`
- `GET /api/state`

Daily intelligence:

- `GET /api/insights/today`
- `GET /api/food-intel/day`
- `POST /api/food-intel/meal-plan`
- `GET /api/food-intel/health`

Body composition:

- `GET /api/body-snapshot/latest`

## Releases

### `v0.0.15` — Dashboard refactor guardrails

- Adds known-day regression checks for 2026-06-03, 2026-06-04 and 2026-06-05.
- Adds frontend anti-monolith guardrails.
- Locks legacy growth for `static/app.js` and `static/styles.css`.
- Adds modular dashboard scaffolding under `static/js/`.
- Extracts compact meal and workout card renderers into small dashboard modules.
- Reduces legacy dashboard cleanup code while preserving current UI behavior.


### `v0.0.14.2` — Dashboard meal totals and UI cleanup

- Fixes meal cards using Food Intelligence totals as the source of truth.
- Keeps kcal/protein visible and consistent in registered meals.
- Cleans technical `REAL_...` / `PLAN_...` markers from normal dashboard notes.
- Avoids false chocolate warnings from protein chocolate/cacao products.
- Keeps private local data out of the repository.

### `v0.0.14.1` — Dashboard and catalog cleanup

- Cleans legacy food catalog aliases in `/api/state`.
- Adds backend safety net for duplicated foods such as `Huevos`, `Chocolate`, stale Alpro names and stale coffee values.
- Adds safe local catalog cleanup script.
- Fixes visible version consistency after `v0.0.14`.
- Improves dashboard/form cleanup without changing private user data.
- Verifies that Food Intelligence no longer reports false chocolate extras from Alpro.

### `v0.0.14` — Body Snapshot

- Optional Body Snapshot module.
- `/api/body-snapshot/latest`.
- Smart-scale composition dashboard card.
- Fat, water, muscle, visceral fat and BioCharge.
- Bioimpedance treated as trend context.
- Foundation for Weight 2.0.

### `v0.0.13` — Food Intelligence dashboard

- Food Intelligence backend.
- `/api/food-intel/day`.
- `/api/food-intel/meal-plan`.
- `/api/food-intel/health`.
- Confidence-aware daily analysis.
- Local heuristic meal suggestions.
- Unified Food Intelligence home dashboard.

### `v0.0.12` — Intelligent score dashboard

- Daily insights endpoint.
- Score and semaphore.
- Compact premium home.
- Weight-goal progress.
- UTF-8 dashboard cleanup.

### Previous releases

- `v0.0.11`: UI5 redesign, OCR3 label parser, sport dashboard and editable weekly plan.
- `v0.0.10`: improved weight system and compact food-label helper.
- `v0.0.9`: curated products, practical templates and improved assistant.
- `v0.0.8`: sidebar daily-rule visibility fix.
- `v0.0.7`: UTF-8 cleanup and Strava detailed-activity calorie import.
- `v0.0.6`: stable Spanish UI after removing broken translation layer.
- `v0.0.5`: safe UI translation cleanup.
- `v0.0.4`: background Strava auto-sync and last-sync status.
- `v0.0.3`: branding, ES/EN toggle and Strava auto-preview.
- `v0.0.2`: manual Strava import.
- `v0.0.1`: first clean public release.

## Roadmap

- Weight 2.0 with composition graphs.
- Weekly trend interpretation.
- Apple Health import/export path.
- Planned vs real meal workflow.
- More automatic meal suggestions from available foods.
- OCR4 product detection and duplicate handling.
- Premium dashboard polish.

## Disclaimer

This is a personal local-first project. It is not a medical device and does not provide medical diagnosis.

Smart-scale body-composition values are estimates and should be used for trends, not as absolute daily truth.

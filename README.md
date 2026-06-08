# Diet Pro Planner

**Self-hosted, local-first cockpit for nutrition, body composition, sport and daily diet decisions.**

[![release](https://img.shields.io/github/v/release/odegaard12/Diet-Pro-Planner?label=release)](https://github.com/odegaard12/Diet-Pro-Planner/releases)
[![license: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![backend](https://img.shields.io/badge/backend-Python%20%2B%20Flask-blue)
![frontend](https://img.shields.io/badge/frontend-Vanilla%20JS%20%2B%20CSS-yellow)
![docker](https://img.shields.io/badge/runtime-Docker-2496ED)
![local-first](https://img.shields.io/badge/privacy-local--first%20%2F%20offline--friendly-111827)

**Current version:** `v0.0.16`

Diet Pro Planner is a private Raspberry Pi web app for tracking real meals, weight trend, training load and smart-scale body-composition context without sending private diet data to external services.

The goal is to build a premium personal cockpit for daily diet decisions, closer to Apple Health + Gentler Streak + a local nutrition assistant than to a spreadsheet.

## Latest release: `v0.0.16` — Weight and Body Composition 2.0

`v0.0.16` adds the first full Weight & Body Composition 2.0 module.

### New in v0.0.16

- Adds `/weight-2`, a standalone dashboard for weight, smart-scale composition and recovery context.
- Adds `/api/body-trends?days=...`, a trend endpoint for local body and weight data.
- Shows official/reference weight series.
- Shows body fat %, fat mass kg, water %, muscle kg, visceral fat, BMR and BioCharge / Hybrid Charge.
- Adds trend insights:
  - official weight direction;
  - body-fat trend as weekly context;
  - BioCharge / recovery context.
- Treats bioimpedance as trend context, not daily absolute truth.
- Keeps the main dashboard safe: the broken experimental `weight-2-link` injection was removed.
- Keeps private body-composition and weight data local in `data/dieta.db`.

### Validation

- Docker build and local deploy passed.
- Smoke OK for `/`, `/weight-2` and `/api/body-trends?days=45`.
- Known-days regression passed.
- Frontend anti-monolith guard passed.
- `static/app.js` and `static/styles.css` remain under budget.

## Previous release: `v0.0.15.1` — Mobile dashboard rescue and Food Intelligence truth


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

### `v0.0.16` — Weight and Body Composition 2.0

- Adds standalone `/weight-2` page.
- Adds `/api/body-trends?days=...`.
- Adds weight/composition/recovery trend cards.
- Tracks body fat %, fat mass kg, water %, muscle kg, visceral fat, BMR and BioCharge / Hybrid Charge.
- Adds simple trend insights for weight, composition and recovery.
- Keeps bioimpedance framed as weekly trend context.
- Keeps the broken experimental dashboard `weight-2-link` removed.
- Keeps private body-composition data out of the repository.

### `v0.0.15.1` — Mobile dashboard rescue and Food Intelligence truth

- Adds mobile-only dashboard rescue CSS.
- Adds fixed bottom navigation for mobile.
- Hides the always-expanded top menu on mobile.
- Polishes mobile header and top section cards.
- Keeps `static/app.js` and `static/styles.css` within anti-monolith budgets.
- Normalizes Food Intelligence truth for oil, protein and extras.
- Exposes BioCharge and Hybrid Charge aliases in the latest body snapshot.
- Keeps private local data out of the repository.

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

- Weight 2.0 with composition trends: shipped in v0.0.16. Next: richer charts.
- Weekly trend interpretation.
- Apple Health import/export path.
- Planned vs real meal workflow.
- More automatic meal suggestions from available foods.
- OCR4 product detection and duplicate handling.
- Premium dashboard polish.
- PWA básica para iPhone / standalone install.

## Disclaimer

This is a personal local-first project. It is not a medical device and does not provide medical diagnosis.

Smart-scale body-composition values are estimates and should be used for trends, not as absolute daily truth.

## About

Self-hosted, local-first dashboard for practical diet control: meal logging by grams, weight trend, sport activity, Food Intelligence, smart-scale body composition and recovery context.

Built for private daily use on a Raspberry Pi with Docker. Public code stays in GitHub; private food logs, SQLite databases, tokens, uploads and body-composition records stay local.

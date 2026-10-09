# Diet Pro Planner

[![CI](https://github.com/odegaard12/Diet-Pro-Planner/actions/workflows/ci.yml/badge.svg)](https://github.com/odegaard12/Diet-Pro-Planner/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Local-first](https://img.shields.io/badge/privacy-local--first-167D62)](#local-first-privacy)

**Current version:** v0.3.0  
**Latest release:** v0.3.0 — Sporty dark redesign  
**License:** MIT  
**Stack:** Python · Flask · Waitress · SQLite · Vanilla JS · Docker · Local-first

Diet Pro Planner is a self-hosted cockpit for nutrition, body composition, sport and daily diet decisions.

It is built for private daily use on a Raspberry Pi with Docker. Public application code stays in GitHub; food logs, SQLite databases, Strava tokens, uploads, pantry contents and body-composition records stay local.

## Access protection

- **User + password login (recommended).** Generate a scrypt hash and put it in `.env`:

  ```bash
  docker compose exec diet-pro-planner python -m dpp_security hash-password   # or: python -m dpp_security hash-password
  ```

  ```dotenv
  DPP_ADMIN_USER=admin
  DPP_ADMIN_PASSWORD_HASH=scrypt:32768:8:1:...   # output of the command above (no $ signs, safe for compose)
  ```

  Then `docker compose up -d`. The password itself is never stored; only the salted scrypt hash.
- **Token login (legacy fallback).** If no user/password is configured, the login screen asks for `DPP_AUTH_TOKEN`
  as before, so upgrading never locks an existing install out. Keep `DPP_AUTH_TOKEN` set even with a password:
  automation can keep using the `Authorization: Bearer <DPP_AUTH_TOKEN>` header (or `X-DPP-Auth`).
- Sessions are server-side (`data/auth_sessions.db`, only SHA-256 of the session id is stored): logout really
  invalidates the cookie, every login issues a new session id, and sessions expire after `DPP_SESSION_DAYS`
  (default 30) or `DPP_SESSION_IDLE_HOURS` without use (default 168). Changing the password, user or token logs
  every session out; `python -m dpp_security revoke-sessions` does it on demand. The cookie signing key is
  generated once in `data/.session_secret` (mode 600) unless `FLASK_SECRET_KEY` is set.
- Login attempts and wrong bearer tokens are rate limited per client address (8 per 15 min); sessions use an
  HttpOnly, SameSite=Lax cookie (`DPP_COOKIE_SECURE=1` behind HTTPS, which also enables HSTS).
- CSRF: cookie-authenticated writes must come from the same origin (`Origin`/`Referer` = this host,
  `Sec-Fetch-Site: same-origin` when sent) with a JSON or multipart body; HTML forms from other sites are rejected.
- Behind a reverse proxy, set `DPP_TRUSTED_PROXIES` so the limiter sees real client addresses (otherwise every client shares the proxy's address).
- `/health` stays public for Docker and uptime checks.
- Strava `client_secret` is read from `STRAVA_CLIENT_SECRET` only and is never stored in `data/integrations.json`.

## v0.1.0 — Pro core

**Progress you can trust**
- New **Progreso** page: trend weight (exponential moving average), real loss rate in kg/week, goal date, daily energy vs target, protein adherence, macro split, weekly table, top foods and a full daily data table.
- **Adaptive energy expenditure (real TDEE)** measured from what you eat and how your trend weight moves (needs 14 logged days and 6 weigh-ins in 4 weeks).
- Pattern insights: weekend vs weekday intake, logging streak, protein adherence.

**Your goals, not hard-coded values**
- New **Objetivos** page. Weight goal, start weight, protein and oil limits, sport bonus and calorie mode: manual, automatic (Mifflin-St Jeor) or adaptive (measured TDEE).
- Coach, score, insights, Food Intelligence and Strava kcal estimates now use your profile and current weight (the old 90.0 kg / 80 kg / 1900 kcal constants are only defaults).

**Database safety**
- Versioned migrations with an automatic snapshot before upgrading (`data/backups/`).
- Daily rotating backups, one-click SQLite download and CSV exports (meals, weights, workouts).
- Indexed date lookups, connections that are always closed; dangling references from old scripts are repaired instead of blocking the upgrade.
- Fixes silent data loss: two identical meals at the same minute were merged and the second meal's foods discarded.

**Food database and AI (optional)**
- Barcode / name search in **Open Food Facts** (camera scanning on supported browsers), with local cache; scanned products remember their barcode.
- Optional **AI coach** and **AI label reading** with your own key: Claude (`ANTHROPIC_API_KEY`) or any OpenAI-compatible endpoint, including a local Ollama. Daily limit, response cache and a privacy-minimised context. The rule-based coach keeps working without AI.

**Fixes and UX**
- Food search in *Registrar comida* works again (the suggestion list was never rendered).
- Smart Coach now proposes meals from your real pantry.
- Repeat a meal with one tap (↻), edit and delete catalog foods, edit meals via API.
- Mobile coach card no longer hides the main recommendation; destructive buttons look destructive.
- `static/app.js` reduced from 2,205 to ~390 lines: no more DOM polling every 1–3 s, no `fetch()` monkeypatch, user data escaped everywhere.
- Installable as a PWA (manifest + icons). Production server: Waitress.

**Security**
- Open-redirect and reflected-XSS fixes in the login flow, login brute-force protection.
- Security headers + Content-Security-Policy, `no-store` on private data.
- Strava OAuth `state` is mandatory, single-use and expires.
- Uploads are size-limited and verified as real images.
- Tests run against a temporary data directory (they used to overwrite `data/pantry.json`).

See [`reports/v010-release-notes.md`](reports/v010-release-notes.md) for the full list and upgrade notes.

## v0.0.21 — Security hardening for private self-hosting

- Adds required authentication for private API and upload access.
- Stops trusting spoofed `X-Forwarded-For` headers unless the proxy is explicitly trusted.
- Keeps the Strava `client_secret` in environment configuration instead of `data/integrations.json`.
- Hardens upload serving against traversal-style paths.
- Keeps `/health` public for Docker and uptime checks while private data stays protected.

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
- Optional AI coach (Claude or an OpenAI-compatible endpoint such as a local Ollama) follows a BYOK policy: each installation uses its own key, with daily limits and caching.

### Progress and goals

- Trend weight, real loss rate and estimated goal date.
- Adaptive energy expenditure measured from intake and weight trend.
- Editable goals: weight, protein, oil, sport bonus and calorie mode (manual, formula or adaptive).

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

### OCR, barcodes and food catalog

- Barcode and name search in Open Food Facts, with camera scanning where supported.
- Optional AI label reading (BYOK) when OCR confidence is low.
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

Pull requests run Python and JavaScript checks, unit tests (migrations, API, analytics, security, AI and food lookup with mocks), the frontend anti-monolith guard, the privacy guard and a real Docker `/health` smoke test.

- Contribution workflow: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Vulnerability reporting: [`SECURITY.md`](SECURITY.md)
- CI workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- Dependency policy: [`.github/dependabot.yml`](.github/dependabot.yml)

## Docker

Build and start:

```bash
docker compose up -d --build
```

The container starts as root only long enough to give `./data` to uid/gid `10001` (older installs have root-owned
files there), then drops every privilege and runs as that user. The root filesystem is read-only (only `./data` and
a `/tmp` tmpfs are writable), `no-new-privileges` is set and capabilities are limited to the ones the entrypoint
needs. To read `./data` from the host afterwards use `sudo` (files are private, mode 600/700).

Default local URL:

```text
http://localhost:8099
```

LAN example:

```text
http://raspberrypi.local:8099
```

## API summary

All `/api/*` routes require authentication except `/api/auth/login`, `/api/auth/logout`, `/api/auth/status`
(`{mode, authenticated}`) and the Strava OAuth callback.

### Core

- `GET /health`
- `GET /api/state`
- `GET /api/insights/today`
- `POST /api/meals` · `PUT /api/meals/<id>` · `POST /api/meals/<id>/duplicate` · `DELETE /api/meals/<id>`
- `POST /api/foods` · `DELETE /api/foods/<id>`
- `POST /api/weights` · `PUT /api/weights/<id>` · `DELETE /api/weights/<id>`
- `POST /api/workouts` · `DELETE /api/workouts/<id>`

### Goals and progress

- `GET /api/profile` · `PUT /api/profile`
- `GET /api/analytics/overview?days=60`
- `GET /api/analytics/tdee`

### Data

- `GET /api/backup` · `POST /api/backup` · `GET /api/backup/download`
- `GET /api/export/meals.csv` · `weights.csv` · `workouts.csv`
- `GET /api/export` *(JSON)*

### Food database and AI

- `GET /api/foods/barcode/<code>`
- `GET /api/foods/search-online?q=...`
- `GET /api/ai/status` · `POST /api/ai/coach` · `POST /api/ai/label`

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

## Configuration

All settings live in `.env` (see [`.env.example`](.env.example)):

| Variable | Purpose |
| --- | --- |
| `DPP_ADMIN_USER`, `DPP_ADMIN_PASSWORD_HASH` | User + password login (hash from `python -m dpp_security hash-password`) |
| `DPP_AUTH_TOKEN` | Bearer token for automation; login token when no user/password is set |
| `DPP_SESSION_DAYS`, `DPP_SESSION_IDLE_HOURS` | Session absolute / idle lifetime (30 days / 168 h) |
| `DPP_MAX_JSON_KB` | Max JSON request body (2048 KB; photo uploads use `DPP_MAX_UPLOAD_MB`) |
| `FLASK_SECRET_KEY` | Optional cookie signing key (default: generated in `data/.session_secret`) |
| `DPP_COOKIE_SECURE` / `DPP_TRUSTED_PROXIES` | HTTPS cookie flag / trusted reverse proxies |
| `STRAVA_*` | Optional Strava OAuth app |
| `ANTHROPIC_API_KEY`, `DPP_AI_*` | Optional AI (BYOK); `DPP_AI_DAILY_LIMIT` caps calls per day |
| `DPP_OFF_ENABLED`, `DPP_OFF_COUNTRY` | Open Food Facts lookups |
| `DPP_BACKUP_KEEP` | Daily backups kept (0 disables) |
| `DPP_DATA_DIR`, `DPP_DB`, `DPP_PANTRY` | Override data paths |
| `TZ` | Local time zone (set in `docker-compose.yml`) |

## Releases

### v0.3.0 — Sporty dark redesign

- One dark theme with an orange accent across the whole app (chosen from three mockups).
- New Resumen: week strip with a dot per logged day, big daily balance (kcal left, intake split by meal, workout), four tiles with mini charts (protein 7 days, weight trend, sport 7 days, weekly rate) and the day as a timeline ending with the Coach.
- Line icons in the bottom bar; login restyled to match.

### v0.2.1 — Bottom bar docked on iPhone

- The mobile bottom navigation sits on the screen edge, with the home-indicator area inside the bar instead of floating ~40 px above it.

### v0.2.0 — New design system and real login

- One design system (`static/css/base.css` + `pages.css`) replaces nine stylesheet layers; automatic dark mode; consistent desktop and mobile layouts.
- New Resumen: today's calories, protein, workout and weight with progress, Coach in its own card, empty states that say what to do.
- Phone-first layout: compact sticky app bar, day switcher, bottom navigation with Ayuda / Exportar / Salir in "Más", short forms (weight in one row), paginated long lists, no input auto-zoom on iOS and pinch-zoom everywhere; restyled login.
- Optional username + password login (scrypt), server-side sessions with real logout and expiry, CSRF checks on cookie writes; the token keeps working.
- Docker: no secrets or data in the image (`.dockerignore`), runs as an unprivileged user on a read-only filesystem.
- Stricter input validation (400 instead of 500), request size limit, real image type check on uploads, CSV formula escaping, no internal errors or paths in API responses.

### v0.1.1 — Privacy and repository hygiene

- Clean public history: one commit, tag and release per version, without personal data.
- `scripts/check_repo_privacy.py` (CI) now also blocks private IP addresses, home-directory paths and Strava activity ids in tracked files.
- The Food Intelligence audit writes to `data/reports/` (git-ignored) instead of `reports/`.
- Removed one-off deployment and inspection scripts.

### v0.1.0 — Pro core

- Progreso page with trend weight, real rate, adaptive TDEE, adherence and patterns.
- Objetivos page: editable goals replace hard-coded personal values.
- Versioned migrations, automatic and daily backups, SQLite download and CSV exports.
- Open Food Facts barcode/name search; optional AI coach and AI label reading (BYOK).
- Food search restored, pantry-aware Smart Coach, repeat meals, lighter and safer frontend.
- Login, OAuth, upload and header hardening; isolated tests.

### Security hardening for private self-hosting (shipped in v0.1.0)

- Auth-required access for `/api/*` and `/uploads/*`.
- Local login screen for the browser UI plus bearer-token support for API clients.
- Safer local-network checks that ignore forged forwarding headers by default.
- Strava `client_secret` removed from disk-backed integration storage.
- Upload path validation tightened without exposing local files.

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

- Planned-versus-real meal workflow (weekly meal plan linked to logged meals).
- Meal editing UI (the API already supports it) and quick "copy yesterday".
- Dark mode and a consolidated design system (replacing the layered legacy CSS).
- Body-composition charts in Progreso (merge Peso 2.0).
- Strava cleanup tools for duplicates, estimates and planned activities.
- Offline support (service worker) and push reminders.
- Non-root Docker user and multi-arch image publishing.

Ready-to-use prompts for continuing the work with Claude Code are in [`docs/CLAUDE_CODE_PROMPTS.md`](docs/CLAUDE_CODE_PROMPTS.md).

## Disclaimer

This is a personal local-first project. It is not a medical device and does not provide medical diagnosis.

Smart-scale body-composition values are estimates and should be used for trends, not as absolute daily truth.

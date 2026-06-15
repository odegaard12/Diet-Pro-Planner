# Diet Pro Planner

**Current version:** v0.0.19  
**Latest release:** v0.0.19 — Editable pantry and practical Coach actions  
**License:** MIT  
**Stack:** Python · Flask · Vanilla JS · Docker · Local-first

Self-hosted, local-first cockpit for nutrition, body composition, sport and daily diet decisions.

Built for private daily use on a Raspberry Pi with Docker. Public code stays in GitHub; private food logs, SQLite databases, Strava tokens, uploads and body-composition records stay local.

## v0.0.19 — Editable pantry and practical Coach actions

- Adds a professional editable pantry screen.
- Adds quick activation and manual food creation.
- Tracks availability, low stock, categories, priorities and notes.
- Adds “No tengo esto” to mark missing ingredients and recalculate the suggestion.
- Adds “Dame otra comida” with complete pantry-aware alternatives.
- Prefers solid protein for main meals when available.
- Keeps drinks and dairy as secondary or fallback options.
- Stores the real pantry privately in `data/pantry.json`.
- Keeps the implementation modular without growing `app.py` or `static/app.js`.

## v0.0.18 — Strava stability and web settings

- Adds private Strava configuration from the web.
- Removes the daily dependency on `.env` editing and PowerShell tunnels.
- Adds connection testing, OAuth renewal and diagnostics.
- Shows API rate-limit consumption and handles HTTP 429 cleanly.
- Lists activities with one request and fetches detail only when importing new activities.
- Adds local detail cache and duplicate protection.
- Adds protected auto-sync with recent windows and concurrency locking.
- Adds a compact professional Strava integration screen.
- Keeps credentials, tokens, cache and diagnostics private under `data/`.

## v0.0.17 — Smart Coach + Pantry foundation

- Adds `/api/smart-coach/day`.
- Adds Smart Coach integration in the main dashboard.
- Adds local private pantry support through `data/pantry.json`.
- Adds public `data/pantry.example.json`.
- Keeps external AI as future BYOK option.
- Keeps local fallback mode without external AI.
- Keeps frontend anti-monolith guardrails passing.

## Core features

- Nutrition logging by grams, catalog foods, products, templates, weekly plan, oil tracking and protein-focused targets.
- Food Intelligence daily analysis, confidence labels, estimated/composite food detection and local heuristic suggestions.
- Smart Coach daily endpoint, dashboard integration, pantry-aware foundation and local-first fallback.
- Weight and body-composition trends: official/reference weight, goal progress, fat, water, muscle, visceral fat, BMR and BioCharge / Hybrid Charge.
- Sport logging, Strava localhost OAuth, manual import, optional auto-sync and duplicate protection.
- Local OCR with Tesseract, OCR3 parser, known-label correction, plausibility validation and cache.

## Local-first privacy

Private/local files are excluded from Git: `data/`, `uploads/`, `*.db`, `*.sqlite`, `.env`, tokens, backups, ZIP files, local label photos and OCR cache files.

## Docker

Build and start: `docker compose up -d --build`

Default local URL: `http://localhost:8099`

LAN example: `http://192.168.68.103:8099`

## API summary

- `GET /health`
- `GET /api/state`
- `GET /api/insights/today`
- `GET /api/food-intel/day`
- `POST /api/food-intel/meal-plan`
- `GET /api/food-intel/health`
- `GET /api/smart-coach/day`
- `GET /api/body-snapshot/latest`
- `GET /api/body-trends?days=45`
- `GET /api/pantry`
- `POST /api/pantry`

## Releases

### v0.0.17 — Smart Coach + Pantry foundation

- Smart Coach endpoint and dashboard integration.
- Local pantry foundation.
- BYOK policy for future AI providers.
- Local fallback mode without external AI.

### v0.0.16 — Weight and Body Composition 2.0

- Standalone `/weight-2` page.
- `/api/body-trends`.
- Weight, composition and recovery trend cards.

### v0.0.15.1 — Mobile dashboard rescue and Food Intelligence truth

- Mobile dashboard rescue.
- Fixed mobile navigation.
- Food Intelligence truth normalization.
- BioCharge / Hybrid Charge aliases.

### Previous releases

v0.0.15, v0.0.14.2, v0.0.14.1, v0.0.14, v0.0.13, v0.0.12, v0.0.11, v0.0.10, v0.0.9, v0.0.8, v0.0.7, v0.0.6, v0.0.5, v0.0.4, v0.0.3, v0.0.2, v0.0.1.

## Roadmap

- Editable pantry screen.
- “No tengo esto / cambiar comida”.
- Planned activity input.
- OpenAI/Gemini BYOK settings.
- AI cache and daily limits.
- Strava cleanup tools.
- Richer weight and body-composition charts.
- Planned vs real meal workflow.
- OCR4 product detection.
- Premium dashboard polish.
- iPhone/PWA standalone install improvements.

## Disclaimer

This is a personal local-first project. It is not a medical device and does not provide medical diagnosis.

Smart-scale body-composition values are estimates and should be used for trends, not as absolute daily truth.

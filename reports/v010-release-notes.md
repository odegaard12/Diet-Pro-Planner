# v0.1.0 — Pro core

## Upgrade notes (Raspberry Pi / Docker)

```bash
git pull
docker compose up -d --build
docker compose logs -f   # expect: [DPP] database migrated: [1, 2, 3, 4, 5]
```

- **Automatic snapshot first.** Before migrating, the app copies the database to
  `data/backups/dieta-<fecha>-pre-migration-v0-to-v5.db`. Keep it until you have
  checked that everything looks right.
- Migrations (SQLite `PRAGMA user_version`):
  1. `meals` rebuilt without `UNIQUE(date,time,name,notes)` (ids preserved, items untouched).
  2. Indexes on dates/meal items; `workouts.source` + `workouts.external_id` (Strava ids backfilled from notes).
  3. `app_settings`, `ai_cache`, `ai_usage` tables.
  4. `foods.barcode`.
  5. Meal items stored with grams but no macros are filled from the catalog.
- New dependencies: `waitress` (production server) and `anthropic` (only used if AI is configured).
- `docker-compose.yml` now sets `TZ=Europe/Madrid`; change it if you live elsewhere.
- Profile defaults reproduce the previous behaviour (90.0 kg start, 80 kg goal, 1900 kcal, 135 g protein).
  Open **Objetivos** to set your real data and, if you want, the automatic or adaptive calorie mode.
- The journal mode stays the classic single file (no WAL), so existing `cp data/dieta.db …` habits keep working;
  for a consistent copy while the app runs, prefer **Objetivos → Descargar copia** or `/api/backup/download`.
- Before migrating, meal items pointing at foods deleted by old scripts get `food_id = NULL` (their name, grams
  and macros are kept). Pre-existing foreign-key problems never block the upgrade, and a failed start does not
  create a new snapshot on every restart.
- The seed catalog is applied only to a brand-new database: foods, templates or exercises you edit or delete are
  no longer restored on restart.
- The session cookie is now `dpp_session` (SameSite=Lax): every device has to log in once after upgrading.

## Bugs fixed

| Area | Problem | Fix |
| --- | --- | --- |
| Registrar comida | `renderSuggestions is not defined`: food search never showed results | Suggestion list restored (accent-insensitive, Enter adds the first hit) |
| Meals | Two identical meals at the same minute were merged and the second meal's foods discarded silently | Constraint removed by migration; every save creates its own meal |
| Frontend | A `fetch()` patch overwrote meal-item macros with per-100 g catalog values for some foods | Patch removed (the backend already sanitises `/api/state`) |
| Smart Coach | Always proposed the same hard-coded meal; the pantry builder was never called | Uses the pantry (solid protein first, avoids `avoid` items) |
| Seed data | Restarting the app overwrote catalog foods, templates and exercises edited by the user | Seed only inserts missing rows |
| Tests | The test suite wrote `data/pantry.json` and `data/dieta.db` (would wipe the real pantry on the Pi) | Tests run in a temporary data directory |
| Database | Connections were never closed (`with sqlite3.connect()` only commits) | Closing connection factory |
| Paths | Smart Coach, body trends and the body snapshot used CWD-relative `data/…` paths | Single `dpp_config` source of truth |
| Insights | Garbled advice text (`Mantún… m?s`, `sartún… 0?5 g`) patched with regexes in the UI | Fixed at the source |
| `/health` | Version overwritten by three modules (`v0.0.14.1` → `v0.0.18` → `v0.0.19` → `v0.0.21`) | `dpp_config.VERSION` |
| `/api/state` | Response sanitizer replaced the response object, dropping headers | Modified in place |
| `/api/state` | Legacy alias foods ("Huevos", "Chocolate") were shown without database id, so they could not be added or edited | Entries keep their real id; the real canonical row wins over the alias |
| Mobile | Coach card stacked both blocks in the same grid cell, hiding the main recommendation | Blocks stack correctly |
| Mobile | "Añadir producto" (food search), the activity-plan form and the Strava auto-sync card were `<aside>` elements collapsed by sidebar rules: invisible on phones | Rendered as sections |
| Performance | `setInterval` loops (1–3 s) and whole-document `MutationObserver`s scanning `innerText` of every `div` | Removed; modules render on explicit hooks/events |

## Security

- Login `next` parameter: blocks `//evil.example` open redirects and is HTML-escaped in the login page.
- Rate limit for logins and wrong bearer tokens (8 failures / 15 min per client address → HTTP 429).
- Headers: CSP (`default-src 'self'`, no framing, no plugins), `X-Frame-Options`, `nosniff`,
  `Referrer-Policy`, `Permissions-Policy`; `Cache-Control: no-store` on `/api/*` and `/uploads/*`.
- Strava OAuth `state`: mandatory, constant-time compare, single use, 30 min expiry.
- Uploads: max size (`DPP_MAX_UPLOAD_MB`, default 15), Pillow verification, decompression-bomb limit.
- Unified JSON errors for the API (400/404/405/413/500) instead of HTML tracebacks.
- Optional `DPP_COOKIE_SECURE` for HTTPS deployments.

## New features

- **Progreso**: trend weight, real kg/week, goal date, adaptive TDEE, energy and protein charts with
  tooltips, macro split, weekly table, top foods and protein sources, daily data table.
- **Objetivos**: profile and targets, computed BMR/TDEE, AI status, backups and exports.
- **Alimentos**: Open Food Facts barcode/name search with camera scanning (BarcodeDetector), edit and delete foods,
  optional AI label reading.
- **Resumen**: repeat any meal (↻), optional AI coach card, profile-driven weight progress.
- **Datos**: daily backups (`DPP_BACKUP_KEEP`), manual snapshot, SQLite download, CSV exports.
- **PWA** manifest and icons; Waitress production server; Docker `HEALTHCHECK`.

## Architecture

New focused modules (no new code in the legacy monolith beyond fixes):

| Module | Responsibility |
| --- | --- |
| `dpp_config.py` | Version, paths, tunables (env overrides) |
| `dpp_db.py` | Connections, migrations, backups |
| `dpp_validate.py` | Input validation + JSON error handlers |
| `dpp_profile.py` | Profile, targets, BMR/TDEE |
| `dpp_analytics.py` | Trend, rate, adaptive TDEE, adherence |
| `dpp_data_api.py` | Backups and CSV exports |
| `dpp_food_lookup.py` | Open Food Facts + local barcode lookup |
| `dpp_ai.py`, `dpp_ai_claude.py`, `dpp_ai_openai_compat.py` | Optional AI (BYOK) |
| `static/js/core/shell.js` | Page registry, version, profile, logout |
| `static/js/features/*.js` | Home, Progreso, Objetivos, plan editor, charts, food lookup, AI |

## Validation

- 50+ unit tests (`python -m unittest discover -s tests`), including a migration test on a legacy-schema database.
- Ruff, `compileall`, `node --check`, monolith guard, privacy guard, pantry and activity-plan regression scripts.
- Manual browser run (desktop 1440 px and mobile 390 px) with synthetic data: register via search, repeat meal,
  save goals, Progreso ranges and tooltips, every page without console errors.
- Not verified here: Open Food Facts against the live API (blocked in the build sandbox; covered by mocked tests),
  real AI calls (no key; covered by mocked tests), Docker build on ARM.

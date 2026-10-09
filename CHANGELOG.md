# Changelog

## v0.3.5 — Offline queue

- Meals, weights and workouts saved without connection wait on the phone and are sent in order as soon as the Raspberry is reachable (on reconnect or next app start). The Resumen shows how many are pending.

## v0.3.4 — README with screenshots

- New README: logo, phone screenshots (demo data), features, quick start, configuration, privacy and security in short.
- API reference moved to docs/API.md, release history to CHANGELOG.md, security details to docs/security.md.

## v0.3.3 — Simpler app icon

- New app icon: one symbol (a leaf inside an orange progress ring) in the dark theme colours, readable at home-screen size. The old one packed a letter, scale, bike, salad, chart and pulse line.
- Removed the unused 1.4 MB `static/app-icon.png`.

## v0.3.2 — Works offline

- Service worker (network first): online you always get the latest version; without connection the app opens with the last data seen on the device (read-only). Writes are never cached. Logging out clears the offline copy.
- Every form control has an accessible name.

## v0.3.1 — Web app polish and motion

- Installed app: dark splash and theme colours, portrait, home-screen shortcuts (Registrar comida, Registrar peso, Progreso).
- Short animations (cards rise in, balance and chart bars grow, weight line draws, count-up on the daily balance, press feedback); all off with reduced motion.
- Form labels linked to their fields (tap the label to focus; better VoiceOver); small text fixes.

## v0.3.0 — Sporty dark redesign

- One dark theme with an orange accent across the whole app (chosen from three mockups).
- New Resumen: week strip with a dot per logged day, big daily balance (kcal left, intake split by meal, workout), four tiles with mini charts (protein 7 days, weight trend, sport 7 days, weekly rate) and the day as a timeline ending with the Coach.
- Line icons in the bottom bar; login restyled to match.

## v0.2.1 — Bottom bar docked on iPhone

- The mobile bottom navigation sits on the screen edge, with the home-indicator area inside the bar instead of floating ~40 px above it.

## v0.2.0 — New design system and real login

- One design system (`static/css/base.css` + `pages.css`) replaces nine stylesheet layers; automatic dark mode; consistent desktop and mobile layouts.
- New Resumen: today's calories, protein, workout and weight with progress, Coach in its own card, empty states that say what to do.
- Phone-first layout: compact sticky app bar, day switcher, bottom navigation with Ayuda / Exportar / Salir in "Más", short forms (weight in one row), paginated long lists, no input auto-zoom on iOS and pinch-zoom everywhere; restyled login.
- Optional username + password login (scrypt), server-side sessions with real logout and expiry, CSRF checks on cookie writes; the token keeps working.
- Docker: no secrets or data in the image (`.dockerignore`), runs as an unprivileged user on a read-only filesystem.
- Stricter input validation (400 instead of 500), request size limit, real image type check on uploads, CSV formula escaping, no internal errors or paths in API responses.

## v0.1.1 — Privacy and repository hygiene

- Clean public history: one commit, tag and release per version, without personal data.
- `scripts/check_repo_privacy.py` (CI) now also blocks private IP addresses, home-directory paths and Strava activity ids in tracked files.
- The Food Intelligence audit writes to `data/reports/` (git-ignored) instead of `reports/`.
- Removed one-off deployment and inspection scripts.

## v0.1.0 — Pro core

- Progreso page with trend weight, real rate, adaptive TDEE, adherence and patterns.
- Objetivos page: editable goals replace hard-coded personal values.
- Versioned migrations, automatic and daily backups, SQLite download and CSV exports.
- Open Food Facts barcode/name search; optional AI coach and AI label reading (BYOK).
- Food search restored, pantry-aware Smart Coach, repeat meals, lighter and safer frontend.
- Login, OAuth, upload and header hardening; isolated tests.

## Security hardening for private self-hosting (shipped in v0.1.0)

- Auth-required access for `/api/*` and `/uploads/*`.
- Local login screen for the browser UI plus bearer-token support for API clients.
- Safer local-network checks that ignore forged forwarding headers by default.
- Strava `client_secret` removed from disk-backed integration storage.
- Upload path validation tightened without exposing local files.

## v0.0.20 — Planned versus real activity

- Weekly planned-versus-real activity view.
- Automatic matching with Strava and manual workouts.
- Activity status, adherence and weekly volume summaries.
- Duplicate Strava-session suppression.
- CI, Docker smoke tests and privacy guardrails.

## v0.0.19 — Editable pantry and practical Coach actions

- Editable pantry from the web.
- Availability, stock, categories, priorities and notes.
- **No tengo esto** and **Dame otra comida**.
- Complete pantry-aware alternatives with solid-protein preference.

## v0.0.18 — Strava stability and web settings

- Private Strava configuration from the web.
- Stable preview/import flow with fewer API requests.
- Local detail cache, concurrency protection and rate-limit diagnostics.
- Protected recent-window auto-sync.

## v0.0.17 — Smart Coach + Pantry foundation

- Smart Coach endpoint and dashboard integration.
- Local pantry foundation.
- BYOK policy for future AI providers.
- Local fallback mode without external AI.

## v0.0.16 — Weight and Body Composition 2.0

- Standalone `/weight-2` page.
- `/api/body-trends` endpoint.
- Weight, composition and recovery trend cards.

## v0.0.15.1 — Mobile dashboard rescue and Food Intelligence truth

- Mobile dashboard rescue and fixed navigation.
- Food Intelligence truth normalization.
- BioCharge / Hybrid Charge aliases.

## Previous releases

v0.0.15, v0.0.14.2, v0.0.14.1, v0.0.14, v0.0.13, v0.0.12, v0.0.11, v0.0.10, v0.0.9, v0.0.8, v0.0.7, v0.0.6, v0.0.5, v0.0.4, v0.0.3, v0.0.2 and v0.0.1.

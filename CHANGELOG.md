# Changelog

## v0.5.3 — Image and deployment hardening

- OCR preprocessing no longer scales a very narrow image to billions of pixels (out-of-memory): upscaling is capped at 4x and the result at 16 megapixels; the file is closed after reading.
- Photo uploads are validated before anything is written to disk (a fake image never reaches `uploads/`).
- `docker-compose.yml`: the published port can be bound to one address with `DPP_BIND` (default unchanged), and the container has a 768 MB memory cap.
- Dependencies are pinned with hashes: edit `requirements.in`, compile `requirements.txt` with `pip-compile --generate-hashes`, and the Docker build installs it with `--require-hashes`.
- Dependabot also watches the GitHub Actions versions.
- New tests for the image limits.

## v0.5.2 — Offline queue hardening

- The offline queue lives in its own `apiQueued()` and accepts only meals, weights and workouts (anything else is rejected); the general `api()` never touches `localStorage`. Fixes the CodeQL alert `js/clear-text-storage-of-sensitive-data` (the Strava client secret could never reach the queue, now the code shows it).
- Signing out now warns when records are still unsent and clears the queue (before, they stayed on the device).
- The 10 `py/stack-trace-exposure` alerts are dismissed as false positives: those responses already go through `public_error()`, which hides library and internal errors (covered by `test_public_error_hides_library_details`).
- Reviewed the Bandit-style findings (`ruff --select S`): SQL identifiers are quoted or allow-listed and values are parametrized; nothing to change.

## v0.5.1 — Barcode in Registrar

- Registrar adds a product by barcode: type or paste the digits (8 to 14) in the search box and tap 'Añadir producto con el código…'. It looks in your catalog first and then in Open Food Facts, saves the product and adds it to the meal. Works on any phone.
- 'Escanear código' (camera) shows up only where the browser allows it (BarcodeDetector over https or localhost).
- A product from Open Food Facts never overwrites one of yours: if the name is taken by a food with another barcode, the brand is appended to the name. Incomplete data opens the Alimentos form to review first.
- Ajustes: removed the long headline box, one line of context instead.

## v0.5.0 — History by day

- Historial is one timeline grouped by day ('Hoy', 'Ayer', 'lun 19 oct') with the day's kcal, protein and workout burn; meals and workouts interleaved by time; older days load on demand.
- Friendly dates everywhere instead of ISO (workout cards, weight history, progress table, weekly activity plan range).
- 'Tu día' has an inline '+ Comida' shortcut (no floating button).
- Ajustes actions (Ayuda, Exportar datos, Salir) are real buttons instead of tab-like links.
- Removed the old meal/workout history cards and the duplicated renderer.

## v0.4.0 — Calmer screens, cleaner catalog

- Deporte opens on your history (week totals, then workouts); adding a workout or exercise type is folded under '+ Entreno'. Dates read 'lun, 19 oct' and empty metrics (0 km) are hidden.
- Plan semanal: one short header with the day counts, two main actions (save, add day) and the rest under 'Más opciones'; JSON import is folded away.
- One icon style: card titles no longer start with emoji (status icons stay).
- Supermarket catalog cleanup (migration 8): readable names, no foreign-language rows (about 167 products); products you already use in meals, templates or plans are never renamed or removed. Brand suffix is hidden in the list where the brand is already shown.
- README: navigation table and fresh screenshots (Hoy, Tu día, Alimentos, Deporte, Progreso).

## v0.3.9 — Spanish supermarket products, simpler food list

- 200 own-brand products from Mercadona (Hacendado), Eroski, Consum and Lidl (Milbona), with barcode and label values from Open Food Facts (ODbL). Added by migration 7 only when the barcode or name is new.
- Alimentos is search-first like the big apps: search box and '+ Nuevo' on top, filters Todos / Míos / Supermercado / Genéricos, compact rows (kcal and protein); tap a row to edit.
- The create/edit form is folded away until needed; removed the static 'Tres formas de añadir' box.

## v0.3.8 — Five sections with tabs

- Navigation reduced to five sections, identical on desktop and phone: Hoy, Comidas, Deporte, Progreso, Ajustes.
- Pages inside a section are tabs at the top of the view (Comidas: Registrar, Plantillas, Alimentos, Despensa, Plan semanal; Deporte: Entrenos, Plan, Strava; Progreso: Tendencias, Peso, Historial).
- Removed the phone 'Más' sheet and duplicate header buttons; Ayuda, Exportar datos and Salir now live in Ajustes.

## v0.3.7 — Clearer menus

- One menu structure for the desktop sidebar and the phone 'Más' sheet, grouped into Comida, Deporte, Datos and App.
- Clearer names: Hoy, Comidas, Entrenos, Plan de comidas, Strava, Objetivos y ajustes; page titles match the menu.
- Removed menu subtitles and the static 'Regla de hoy' box; the day heading shows the date instead of repeating 'Hoy'.

## v0.3.6 — Generic food catalog

- 60 generic foods (meat, fish, dairy, cereals, legumes, vegetables, fruit, nuts) with approximate per-100 g values, added by migration 6 only where the name does not exist yet; your own foods are never touched.
- Activity plan validation errors return a fixed message (CodeQL).

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

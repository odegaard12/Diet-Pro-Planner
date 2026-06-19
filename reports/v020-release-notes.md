# Diet Pro Planner v0.0.20 — Planned versus real activity

v0.0.20 adds a complete weekly planned-versus-real activity workflow while keeping personal training data local.

## Highlights

- New **Plan deporte** weekly view.
- Planning by date, time, activity type, duration, distance, target kcal, intensity and notes.
- Automatic matching with Strava and manually registered workouts.
- Completed, changed, pending, upcoming, missed, skipped and cancelled states.
- Unplanned activities shown as **Extra real**.
- Weekly adherence, planned minutes, real minutes and real kcal summaries.
- Editing, skipping, reactivating and deleting activity plans.
- Private local `activity_plans` storage.

## Strava stability

- Keeps the valid Amazfit Balance strength session from 16 June.
- Removes and blocks the duplicate Hevy session.
- Prevents known ignored Strava IDs from being imported again.
- Keeps synchronization idempotent and rate-limit aware.

## Repository quality

- GitHub Actions CI for Python, JavaScript and feature regressions.
- Public Flask route smoke tests.
- Real Docker build and `/health` validation.
- Privacy guard for databases, tokens, caches, backups and other private files.
- `SECURITY.md`, `CONTRIBUTING.md`, Dependabot policy and pull-request template.

## Privacy

Food logs, activity plans, SQLite data, Strava credentials, ignored IDs, pantry contents and uploads remain private and local.

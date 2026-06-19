# Diet Pro Planner v0.0.20 — CI validation scope

The v0.0.20 planned-versus-real activity branch is validated against the repository guardrails introduced on `main`:

- Python fatal-error lint and compilation;
- JavaScript syntax checks;
- frontend anti-monolith budget;
- tracked private-file guard;
- pantry regression checks;
- activity-plan matching and summary regression checks;
- public Flask route smoke tests;
- Docker build, startup, index and `/health` smoke.

Private known-day checks remain local because they depend on the maintainer's private `data/dieta.db` dataset.

No private food logs, Strava tokens, pantry contents, activity caches or SQLite databases are included in CI.

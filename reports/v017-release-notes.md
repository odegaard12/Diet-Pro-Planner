# Diet Pro Planner v0.0.17 — Smart Coach + Pantry foundation

## Highlights

v0.0.17 introduces the first Smart Coach foundation for local daily nutrition decisions.

It adds a new backend endpoint, dashboard integration, local pantry support and the privacy model for future optional AI providers.

## New

- Added `/api/smart-coach/day`.
- Added Smart Coach dashboard integration.
- Added external `static/dashboard-coach-v17.js`.
- Added external `static/dashboard-coach-v17.css`.
- Added local private pantry support through `data/pantry.json`.
- Added public `data/pantry.example.json`.

## Privacy and AI policy

This release intentionally does **not** ship a central AI key.

Diet Pro Planner remains local-first:

- no central OpenAI/Gemini key;
- no shared API usage;
- no author-managed external AI service;
- each deployment can later configure its own provider/key if desired;
- local fallback mode remains available without external AI.

## Validation

- Docker build passed.
- Local deploy passed.
- `/` smoke passed.
- `/api/pantry` returned local pantry items.
- `/api/smart-coach/day` returned Smart Coach data.
- Frontend anti-monolith guard passed:
  - `static/app.js` remains under budget;
  - `static/styles.css` remains under budget.

## Known limitations

- The Coach can still recommend another meal late in the day; closed-day logic is deferred to v0.0.18.
- Pantry editing UI is not included yet.
- “No tengo esto / cambiar comida” is not included yet.
- OpenAI/Gemini settings are not included yet.
- Strava cleanup tools are not included yet.

## Next

Planned v0.0.18 work:

- editable pantry screen;
- “no tengo esto / cambiar comida” action;
- planned activity input;
- OpenAI/Gemini BYOK settings;
- AI cache and daily limit;
- Strava cleanup: hide/delete duplicates, estimated activities and planned activities.

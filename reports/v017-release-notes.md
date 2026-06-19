# Diet Pro Planner v0.0.17 — Smart Coach + Pantry foundation

v0.0.17 introduces the first Smart Coach foundation for local daily nutrition decisions.

## New

- Added `/api/smart-coach/day`.
- Added Smart Coach dashboard integration.
- Added external `static/dashboard-coach-v17.js`.
- Added external `static/dashboard-coach-v17.css`.
- Added local private pantry support through `data/pantry.json`.
- Added public `data/pantry.example.json`.
- Kept frontend anti-monolith guardrails passing.

## Privacy and AI policy

No central AI key is shipped. Each deployment remains local-first and may later configure its own OpenAI/Gemini key if desired.

## Known limitations

- Closed-day logic is deferred to v0.0.18.
- Pantry editing UI is not included yet.
- “No tengo esto / cambiar comida” is not included yet.
- OpenAI/Gemini settings are not included yet.
- Strava cleanup tools are not included yet.

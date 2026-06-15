# Diet Pro Planner v0.0.19 — Editable pantry and practical Coach actions

## Highlights

- Adds a professional pantry editor to the main navigation.
- Adds quick activation for common foods and manual food creation.
- Edits availability, stock, category, priority and notes from the web.
- Adds filters for available, low-stock, unavailable and avoid foods.
- Adds “No tengo esto” inside Smart Coach.
- Marks missing ingredients as unavailable and immediately proposes another meal.
- Adds “Dame otra comida” using only currently available pantry foods.
- Prefers solid protein for complete main meals when available.
- Keeps protein drinks and dairy as secondary or fallback choices.
- Adds direct access to pantry editing from Smart Coach.
- Keeps raw technical Coach signals hidden from the daily interface.
- Keeps private pantry data outside Git in `data/pantry.json`.

## Privacy

Pantry contents, notes and availability remain local on the Raspberry Pi. Pantry writes are restricted to the private network or loopback.

## Validation

- Pantry normalization, statistics and alternative-generation smoke tests passed.
- Solid-protein policy test passed.
- “Dame otra comida” tested successfully.
- “No tengo esto” tested successfully and persisted the unavailable item.
- Docker build and health smoke passed.
- Desktop pantry and dashboard views validated.

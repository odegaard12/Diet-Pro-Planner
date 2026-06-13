# Diet Pro Planner v0.0.17 — Smart Coach + Pantry foundation

## Resumen

v0.0.17 introduce la primera base del Coach inteligente del día, con recomendaciones contextuales usando comidas registradas, peso, BioCharge, señales del día anterior, actividad y despensa local.

## Cambios principales

- Añadido endpoint `/api/smart-coach/day`.
- Smart Coach calcula totales desde `meal_items`.
- Coach visible en el dashboard sin añadir una tarjeta suelta.
- Diseño visual externo en `static/dashboard-coach-v17.css`.
- Guard de monolito respetado: no se aumenta `static/app.js` ni `static/styles.css`.
- Añadida despensa local privada `data/pantry.json`.
- Añadido ejemplo público `data/pantry.example.json`.
- Añadida política BYOK para IA futura:
  - sin claves centrales;
  - cada instancia usa su propia clave OpenAI/Gemini si quiere;
  - modo local funciona siempre sin IA externa.
- Preparado camino para:
  - editar despensa;
  - botón “no tengo esto”;
  - actividades previstas;
  - integración OpenAI/Gemini opcional;
  - mejoras Strava.

## Privacidad

No se commitean:

- base de datos privada;
- `data/pantry.json`;
- claves API;
- secretos locales.

## Pendiente para v0.0.18

- Pantalla de despensa editable.
- Botón para cambiar recomendación si no hay un alimento.
- Ajustes IA OpenAI/Gemini.
- Caché y límite diario de IA.
- Mejoras Strava: borrar, ocultar duplicados, estimadas y actividades previstas.

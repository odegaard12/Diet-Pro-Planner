# Integraciones

## Strava

La app incluye soporte para conectar Strava con OAuth y sincronizar actividades manualmente, solo cuando el usuario pulse el botón de sincronizar.

Variables locales en `.env`:

```env
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_REDIRECT_URI=http://TU_HOST:8099/api/strava/callback
```

Los tokens se guardan en `data/strava_tokens.json` y no se suben al repositorio.

## Zepp / Amazfit

La ruta práctica es sincronizar Zepp con Strava y que Dieta Pro importe desde Strava. No se guarda ninguna credencial de Zepp en esta app.

## Open Food Facts (base de datos de alimentos)

En **Alimentos → Buscar producto** puedes escribir un código de barras (o escanearlo con la cámara en navegadores
compatibles) o un nombre. La app consulta [Open Food Facts](https://world.openfoodfacts.org) (base abierta, sin
clave) y rellena el formulario por 100 g. Solo sale de la Raspberry el código o el texto buscado; los resultados se
guardan en `data/off_cache.json`. Variables: `DPP_OFF_ENABLED=0` para desactivarlo, `DPP_OFF_COUNTRY=es`.

## IA opcional (BYOK)

Desactivada por defecto. El Coach por reglas funciona siempre sin IA.

- **Claude**: añade `ANTHROPIC_API_KEY` a `.env` (modelo por defecto `claude-opus-5-5`, cambiable con `DPP_AI_MODEL`).
- **Local / compatible OpenAI** (Ollama, LM Studio, OpenAI, Gemini compat):
  `DPP_AI_PROVIDER=openai_compat`, `DPP_AI_BASE_URL=http://IP:11434/v1`, `DPP_AI_MODEL=llama3.1`.
- `DPP_AI_DAILY_LIMIT` limita las llamadas diarias (30 por defecto). Las respuestas se cachean.

Qué se envía: objetivos, alimentos y gramos de hoy, medias de los últimos 7 días y nombres de la despensa
(Coach IA), o la foto de la etiqueta (lectura con IA). Nunca tokens, notas personales ni datos de Strava.
La clave no se guarda en la base de datos.

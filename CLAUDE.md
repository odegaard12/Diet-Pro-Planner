# CLAUDE.md — guía para trabajar en Diet Pro Planner

App personal local-first (Raspberry Pi + Docker) de nutrición, peso y deporte. Interfaz en español.
Los datos reales viven en `data/` (ignorado por git) en la Raspberry: **nunca** se suben, ni se crean fixtures con datos personales.

## Comandos

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt ruff
DPP_AUTH_TOKEN=dev python dpp_entrypoint.py          # http://localhost:8099 (token: dev)
python -m unittest discover -s tests                  # tests (usan un data dir temporal, ver tests/_env.py)
ruff check . --select E9,F63,F7 --exclude data
python -m compileall -q app.py dpp_*.py scripts tests
find static -name '*.js' -exec node --check {} \;
python scripts/check_frontend_monoliths.py && python scripts/check_repo_privacy.py
python scripts/check_v019_pantry.py && python scripts/check_v020_activity_plan.py
```

Ejecuta todo lo anterior antes de hacer push (es lo mismo que la CI en `.github/workflows/ci.yml`).

## Arquitectura

- Punto de entrada: `dpp_entrypoint.py` importa `app.py` (núcleo legado: esquema, CRUD, OCR, insights v0.0.12,
  Food Intelligence) y registra los módulos `dpp_*.py`. Servidor de producción: Waitress.
- Rutas y configuración: **siempre** desde `dpp_config.py` (`DATA_DIR`, `DB_PATH`, `PANTRY_PATH`, `VERSION`).
  Nunca rutas relativas `data/...` ni versiones hardcodeadas.
- Base de datos: `dpp_db.connect()` (cierra al salir del `with`). Cambios de esquema = nueva migración en
  `dpp_db.MIGRATIONS` (versionada con `PRAGMA user_version`, con backup previo automático) + test en
  `tests/test_db_migrations.py`. No uses `ALTER`/`CREATE` sueltos en otros módulos.
- Objetivos personales: `dpp_profile.legacy_targets()` / `compute()`. Nada de constantes personales
  (peso, kcal, proteína) en el código.
- Validación de entrada: `dpp_validate` (`number`, `iso_date`, `hhmm`, `text`, `ApiError`) → errores JSON 400.
- Seguridad: `dpp_security.py` protege `/`, `/weight-2`, `/api/*` y `/uploads/*`. Escrituras sensibles
  (despensa, plan deporte, config Strava, backups) además exigen red local (`is_private_request`).
- IA opcional (BYOK): `dpp_ai.py` orquesta (contexto mínimo, caché, límite diario); proveedores en
  `dpp_ai_claude.py` (SDK oficial `anthropic`, modelo por defecto `claude-opus-5-5`, salida estructurada por
  JSON Schema, fallback de seguridad en servidor) y `dpp_ai_openai_compat.py` (Ollama/compatibles).
  Las claves solo en `.env`. El Coach por reglas debe seguir funcionando sin IA.

## Frontend

- Scripts clásicos (sin bundler) cargados en orden desde `static/index.html`.
- `static/app.js` = núcleo y globals compartidos (`state`, `page`, `go`, `render`, `api`, `esc`, `fmt`, `toast`, `busy`...).
  **No añadas funcionalidades ahí** (guard de líneas en CI). Las nuevas van en `static/js/features/*.js`
  (máx. 260 líneas por archivo) y se registran con `window.DPP.registerPage({...})` (ver `static/js/core/shell.js`).
- Escapa siempre datos de usuario con `esc()` en plantillas `innerHTML`; en tooltips usa `textContent`.
- Nada de `setInterval`/`MutationObserver` para "parchear" el DOM: usa hooks explícitos o eventos
  (`dpp:profile`, `dpp:coach-rendered`).
- Estilos (v0.2.0): solo `static/css/base.css` (tokens de color/espaciado, modo oscuro, shell y componentes:
  `.card`, `.btn`, `.field`, `.row/.span-N`, `.chip/.pill`, `.empty`...) y `static/css/pages.css` (maquetación por
  página). Usa siempre las variables (`var(--surface)`, `var(--text-2)`, `var(--primary)`...), nunca colores fijos,
  para que el modo oscuro funcione. Sin `!important`. Tonos de estado con las clases `good` / `warn` / `bad` / `info`.
- Estados vacíos: di qué hacer ("Registra la primera comida…"), nunca muestres `--` o `0` como si fuera un dato.
- Gráficos: `static/js/features/charts.js` (SVG propio, paleta validada azul/naranja/aqua, un solo eje Y, tooltip).
- Verifica la UI en navegador (escritorio y 390 px de ancho) antes de dar un cambio visual por bueno.

## Reglas de producto

- Local-first; integraciones externas opcionales y explícitas (Open Food Facts envía solo código/búsqueda).
- No presentar nada como diagnóstico médico; la bioimpedancia es tendencia, no verdad diaria.
- Importaciones de Strava idempotentes y respetuosas con el rate limit.
- Preservar siempre los datos existentes en las actualizaciones.

Prompts para continuar el trabajo: `docs/CLAUDE_CODE_PROMPTS.md`.

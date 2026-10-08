# Prompts para continuar con Claude Code

Cada prompt es autocontenido: cópialo tal cual en una sesión nueva de Claude Code abierta en este repo.
Todos asumen las reglas de [`CLAUDE.md`](../CLAUDE.md) (léelo primero; Claude Code lo carga solo).
Orden recomendado: 1 → 2 → 3, y después el que más te apetezca.

---

## 1. Verificar la actualización v0.1.0 en la Raspberry

```text
Acabo de desplegar la v0.1.0 de Diet Pro Planner en mi Raspberry (docker compose up -d --build).
Ayúdame a verificarla sin tocar mis datos:
1) Revisa `docker compose logs` y confirma que aparece "[DPP] database migrated: [1, 2, 3, 4, 5]" y que existe
   data/backups/dieta-*-pre-migration-*.db.
2) Comprueba con sqlite3 (en solo lectura) que el número de filas de meals, meal_items, workouts y weights es el
   mismo en la copia pre-migración y en data/dieta.db, que PRAGMA user_version = 5 y PRAGMA foreign_key_check está vacío.
3) Llama a /health, /api/profile y /api/analytics/overview con mi token (te lo paso por variable, no lo escribas en archivos).
4) Si algo no cuadra, explica la causa antes de proponer cambios. No borres ni reescribas nada en data/.
Al final dame un resumen corto: qué está bien, qué no y qué recomiendas.
```

## 2. Editar comidas desde la interfaz + "copiar ayer"

```text
En Diet Pro Planner la API ya permite editar comidas (PUT /api/meals/<id>, con items y gramos) y duplicarlas
(POST /api/meals/<id>/duplicate), pero la UI solo permite borrar o repetir.
Implementa:
- Botón "Editar" en las tarjetas de comida (Resumen e Historial) que abra la pantalla Registrar precargada con la
  comida (fecha, hora, tipo, notas, alimentos y gramos) y que al guardar haga PUT en vez de POST.
- Botón "Copiar ayer" en Resumen que duplique todas las comidas del día anterior al día seleccionado (pide
  confirmación y muestra cuántas copia).
Reglas: código nuevo en static/js/features/ (máx. 260 líneas por archivo), sin crecer static/app.js; escapa datos
con esc(). Añade tests de API si tocas backend. Verifica en navegador a 1440 px y 390 px y ejecuta toda la CI local.
```

## 3. Plan de comidas previsto vs. real

```text
Diet Pro Planner tiene un plan semanal de comidas en texto libre (Plan, POST /api/plans) y comidas reales
registradas (meals/meal_items), pero no están conectados. Quiero el mismo concepto que ya existe para deporte
("Plan deporte": dpp_activity_plan_v020.py + static/activity-plan-v020.js):
- Plan semanal estructurado: por día y franja (desayuno, comida, merienda, cena) con una plantilla o lista de
  alimentos+gramos y kcal/proteína objetivo. Nueva tabla vía migración en dpp_db.MIGRATIONS (con test).
- Vista semanal que compare previsto vs real (cumplida / cambiada / pendiente / saltada) y adherencia semanal.
- Desde una franja prevista, botón "Registrar como comido" que crea la comida real en un clic.
- Mantén compatible el plan antiguo (JSON en tabla plans): muéstralo como notas si existe.
Diseña primero el modelo de datos y enséñamelo antes de implementarlo.
```

## 4. Modo oscuro y design system consolidado

```text
El CSS de Diet Pro Planner son varias capas históricas (static/styles.css con muchos !important, mobile-*.css,
dashboard-coach-v17.css, etc.) más static/css/v010.css. Quiero:
1) Un design system pequeño con tokens CSS (colores, superficies, texto, radios, sombras, espaciado) en
   static/css/tokens.css, con modo claro y oscuro (prefers-color-scheme + interruptor manual guardado en localStorage).
2) Migrar progresivamente los componentes principales (shell, tarjetas, botones, formularios, Resumen, Progreso,
   Objetivos) a esos tokens, eliminando reglas muertas y !important donde sea posible sin romper nada.
3) Los gráficos de static/js/features/charts.js deben tomar sus colores de los tokens y tener variante oscura
   validada (contraste ≥ 3:1 con la superficie).
Trabaja por pasos pequeños; tras cada paso, capturas con Playwright a 1440 px y 390 px en claro y oscuro y
compara con el estado anterior. El guard de styles.css no debe crecer.
```

## 5. Composición corporal dentro de Progreso

```text
La página /weight-2 (static/weight-2.html, dpp_body_trends.py) muestra composición corporal de la báscula, y la
nueva página Progreso (static/js/features/progress.js, dpp_analytics.py) muestra peso, energía y proteína.
Unifícalas: añade a Progreso una sección de composición (grasa %, masa magra estimada, músculo, agua, visceral,
BioCharge) con el mismo kit de gráficos (charts.js), tendencias semanales y avisos de que la bioimpedancia es
orientativa. Calcula masa grasa y magra en kg cuando haya peso y % grasa. Mantén /weight-2 funcionando como
enlace secundario. Tests para el cálculo en backend; verificación visual en navegador.
```

## 6. PWA offline y recordatorios

```text
Diet Pro Planner ya tiene manifest e iconos (static/manifest.webmanifest). Añade un service worker conservador:
- Cachea solo /static/* con estrategia stale-while-revalidate y versión de caché ligada a dpp_config.VERSION.
- Nunca cachees /, /api/* ni /uploads/* (datos privados y página de login).
- Página offline sencilla cuando no hay red.
- Opcional: recordatorio local para pesarse por la mañana (Notification API) configurable desde Objetivos.
Ten en cuenta la CSP de dpp_security.py (worker-src) y que la app se usa desde iPhone (Safari) y Android.
Verifica que tras desplegar una versión nueva el usuario recibe los ficheros nuevos.
```

## 7. Docker endurecido e imagen multi-arquitectura

```text
Mejora el despliegue de Diet Pro Planner:
- Dockerfile con usuario no root (uid/gid configurables) sin romper instalaciones existentes cuyo ./data es de
  root: documenta el chown necesario y haz que el contenedor avise claramente si no puede escribir en /app/data.
- Workflow de GitHub Actions que construya y publique una imagen multi-arch (linux/arm64 y amd64) en GHCR al
  crear un tag vX.Y.Z, usando buildx y caché.
- docker-compose.yml de ejemplo que use la imagen publicada.
No subas secretos; usa GITHUB_TOKEN. Mantén el job de smoke test actual.
```

## 8. Partir app.py en módulos con tests

```text
app.py de Diet Pro Planner sigue siendo un monolito (~2.700 líneas): esquema/CRUD, Strava legado, OCR3, insights
v0.0.12, Food Intelligence (día, score, meal-plan) y un sanitizador de /api/state. Refactoriza en módulos
dpp_*.py sin cambiar el comportamiento de la API:
1) Primero escribe tests de caracterización (golden JSON) para /api/state, /api/insights/today,
   /api/food-intel/day y /api/food-intel/meal-plan con una BD sintética en tests/.
2) Mueve cada bloque a su módulo (p. ej. dpp_food_intel.py, dpp_ocr.py, dpp_insights.py), dejando en app.py solo
   la creación de la app y el registro.
3) Elimina código muerto (p. ej. /api/strava/sync legado si ninguna UI lo usa; confírmalo con grep).
Cada paso en un commit separado con la CI en verde.
```

## 9. IA: plan semanal y chat con contexto

```text
Diet Pro Planner tiene IA opcional (dpp_ai.py; Claude vía SDK oficial en dpp_ai_claude.py con salida
estructurada por JSON Schema; límite diario y caché). Añade:
- "Generar plan semanal con IA": usa objetivos (dpp_profile), despensa disponible, entrenos planificados
  (activity_plans) y preferencias para proponer 7 días con alimentos del catálogo y gramos; el usuario revisa y
  guarda como plan (no se registra nada automáticamente).
- Chat multi-turno en el Coach IA con historial corto en la sesión (no persistente) y el mismo contexto mínimo.
Mantén la política de privacidad (sin notas personales ni datos de Strava en crudo), el límite diario y el
fallback al Coach por reglas. Tests con el proveedor simulado (ver tests/test_ai_and_lookup.py).
```

## 10. Limpieza de Strava y duplicados

```text
En Diet Pro Planner los entrenos de Strava ahora tienen workouts.source='strava' y workouts.external_id.
Crea una herramienta en Integraciones para:
- Detectar duplicados (mismo external_id, o misma fecha/hora/tipo/duración ±2 min entre manual y Strava).
- Ver y fusionar/borrar duplicados con confirmación, y marcar ids ignorados (data/strava_ignored_ids.json).
- Recalcular kcal estimadas con el peso actual (dpp_profile.estimate_met_kcal) solo para entrenos marcados como
  estimados.
Haz backup (dpp_db.snapshot) antes de cualquier operación masiva. Tests para la detección.
```

## 11. Importar datos de la báscula / salud (CSV)

```text
Quiero importar en Diet Pro Planner exportaciones CSV de Zepp/Amazfit (peso y composición) y, si es viable,
de Health Connect / Apple Health (peso). Implementa un importador con previsualización:
- Subes el CSV, la app detecta columnas, muestra las filas nuevas vs ya existentes y solo importa al confirmar.
- Pesos a la tabla weights (official según hora configurable) y métricas a body_composition.
- Idempotente (no duplica si reimportas el mismo archivo).
Sin dependencias pesadas; tests con CSV sintéticos en tests/fixtures/.
```

## 12. Tests E2E con Playwright en CI

```text
Añade a Diet Pro Planner tests end-to-end con Playwright (Python) que levanten la app con un DPP_DATA_DIR
temporal y datos sintéticos, y comprueben: login, registrar comida buscando alimentos, repetir comida, guardar
objetivos, Progreso con gráficos y tooltip, Alimentos (búsqueda Open Food Facts simulada), sin errores de consola
en ninguna página, en 1440 px y 390 px. Intégralos como job separado en .github/workflows/ci.yml.
```

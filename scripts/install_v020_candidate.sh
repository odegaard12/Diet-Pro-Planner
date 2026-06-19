set -Eeuo pipefail
cd "$HOME/Diet-Pro-Planner" || exit 1

BRANCH="feature/v020-planned-vs-real-activity"
STAMP="$(date +%Y%m%d-%H%M%S)"

echo "== SINCRONIZAR MAIN =="
git fetch origin --prune
git checkout main
git reset --hard origin/main
git branch -D "$BRANCH" 2>/dev/null || true
git checkout -b "$BRANCH"

if [ -f data/dieta.db ]; then
  cp data/dieta.db "data/dieta.db.bak-v020-$STAMP"
  echo "Backup DB: data/dieta.db.bak-v020-$STAMP"
fi

echo "== DESCARGAR ARCHIVOS V0.0.20 =="
BASE="https://raw.githubusercontent.com/odegaard12/Diet-Pro-Planner/$BRANCH"
curl -fsSL "$BASE/dpp_activity_plan_v020.py" -o dpp_activity_plan_v020.py
curl -fsSL "$BASE/static/activity-plan-v020.js" -o static/activity-plan-v020.js
curl -fsSL "$BASE/static/activity-plan-v020.css" -o static/activity-plan-v020.css
curl -fsSL "$BASE/scripts/check_v020_activity_plan.py" -o scripts/check_v020_activity_plan.py
chmod +x scripts/check_v020_activity_plan.py

python3 - <<'PY'
from pathlib import Path

entry = Path("dpp_entrypoint.py")
text = entry.read_text(encoding="utf-8")
if "import dpp_activity_plan_v020 as activity_plan_v020" not in text:
    text = text.replace(
        "import app as legacy\n",
        "import app as legacy\nimport dpp_activity_plan_v020 as activity_plan_v020\n",
        1,
    )
if "activity_plan_v020.register_activity_plan_v020(legacy.app, legacy)" not in text:
    marker = "pantry_v019.register_pantry_v019(legacy.app, legacy)\n"
    if marker not in text:
        raise SystemExit("No se encontró pantry v0.0.19 en dpp_entrypoint.py")
    text = text.replace(
        marker,
        marker + "activity_plan_v020.register_activity_plan_v020(legacy.app, legacy)\n",
        1,
    )
entry.write_text(text, encoding="utf-8")

index = Path("static/index.html")
text = index.read_text(encoding="utf-8")
css = '  <link rel="stylesheet" href="/static/activity-plan-v020.css?v=020a">\n'
js = '  <script src="/static/activity-plan-v020.js?v=020a"></script>\n'
if "/static/activity-plan-v020.css" not in text:
    text = text.replace("</head>", css + "</head>", 1)
if "/static/activity-plan-v020.js" not in text:
    text = text.replace("</body>", js + "</body>", 1)
index.write_text(text, encoding="utf-8")
PY

echo "== VALIDAR =="
python3 -m py_compile app.py dpp_entrypoint.py dpp_activity_plan_v020.py dpp_pantry_v019.py dpp_pantry_v019_policy.py dpp_strava_v018.py
node --check static/activity-plan-v020.js
python3 scripts/check_v020_activity_plan.py

echo "== COMMIT Y PUSH =="
git add dpp_activity_plan_v020.py dpp_entrypoint.py static/index.html static/activity-plan-v020.js static/activity-plan-v020.css scripts/check_v020_activity_plan.py
git commit -m "feat: add planned versus real activity v0.0.20"
git push -u origin "$BRANCH"

cat > /tmp/dpp-v020-pr.md <<'MD'
## Objetivo

Añadir actividad planificada frente a actividad real sin modificar el flujo estable de Strava.

## Incluye

- Nueva vista **Plan deporte**.
- Planificación semanal por fecha, hora, tipo, duración, distancia, kcal objetivo e intensidad.
- Tabla local privada `activity_plans`.
- Emparejamiento automático con entrenos de Strava o manuales.
- Estados: cumplida, cambiada, pendiente, próxima, no realizada, omitida y cancelada.
- Actividades reales no planificadas mostradas como extras.
- Cumplimiento semanal y minutos planificados frente a reales.
- Edición, omisión, reactivación y eliminación.
- Implementación modular sin crecer `app.py` ni `static/app.js`.
- `/health` en `v0.0.20-dev` durante la prueba.
MD

if ! gh pr view "$BRANCH" --repo odegaard12/Diet-Pro-Planner >/dev/null 2>&1; then
  gh pr create --draft --repo odegaard12/Diet-Pro-Planner --base main --head "$BRANCH" --title "v0.0.20: planned versus real activity" --body-file /tmp/dpp-v020-pr.md
fi

echo "== DESPLEGAR CANDIDATA =="
docker compose up -d --build --force-recreate

OK=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if curl -fsS http://127.0.0.1:8099/health >/tmp/dpp-v020-health.json 2>/dev/null; then
    OK=1
    break
  fi
  sleep 2
done
test "$OK" = "1"

echo "== HEALTH =="
cat /tmp/dpp-v020-health.json
echo

echo "== API PLAN =="
curl -fsS "http://127.0.0.1:8099/api/activity-plan?from=2026-06-15&to=2026-06-21" |
python3 -c 'import json,sys; d=json.load(sys.stdin); print("ok=",d.get("ok"),"version=",d.get("version"),"plans=",len(d.get("plans",[])),"extras=",len(d.get("extra_workouts",[])),"summary=",d.get("summary"))'

echo "== DOCKER =="
docker compose ps
echo "OK: v0.0.20-dev desplegada. Abre Plan deporte y prueba la semana."

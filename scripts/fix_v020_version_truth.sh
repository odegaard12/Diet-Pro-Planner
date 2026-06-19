#!/usr/bin/env bash
set -Eeuo pipefail

cd "$HOME/Diet-Pro-Planner" || exit 1
BRANCH="feature/v020-planned-vs-real-activity"
FAILED=1

rollback() {
  if [ "$FAILED" = "1" ]; then
    echo
    echo "ERROR: restaurando main v0.0.19..."
    git fetch origin --prune || true
    git checkout main || true
    git reset --hard origin/main || true
    docker compose up -d --build --force-recreate || true
    echo "Restauración terminada."
  fi
}
trap rollback EXIT

echo "== SINCRONIZAR CANDIDATA =="
git fetch origin --prune
git checkout -B "$BRANCH" "origin/$BRANCH"

echo "== UNIFICAR VERSIÓN VISIBLE =="
python3 - <<'PY'
from pathlib import Path

files = [
    Path('static/app.js'),
    Path('static/dashboard-coach-v17.js'),
    Path('static/pantry-v019.js'),
    Path('static/pantry-v019-polish.js'),
    Path('static/index.html'),
]

changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    new = text.replace('v0.0.19', 'v0.0.20-dev')
    if new != text:
        path.write_text(new, encoding='utf-8')
        changed.append(str(path))

index = Path('static/index.html')
text = index.read_text(encoding='utf-8')
text = text.replace('app.js?v=v019-release', 'app.js?v=v020-version-truth')
text = text.replace('dashboard-coach-v17.js?v=019-release', 'dashboard-coach-v17.js?v=020-version-truth')
text = text.replace('pantry-v019.js?v=019a', 'pantry-v019.js?v=020-version-truth')
text = text.replace('pantry-v019-polish.js?v=020-loopfix', 'pantry-v019-polish.js?v=020-version-truth')
text = text.replace('activity-plan-v020.js?v=020-loopfix', 'activity-plan-v020.js?v=020-version-truth')
index.write_text(text, encoding='utf-8')

print('Archivos actualizados:', ', '.join(changed) or 'ninguno')
PY

echo "== VALIDAR CÓDIGO =="
node --check static/app.js
node --check static/dashboard-coach-v17.js
node --check static/pantry-v019.js
node --check static/pantry-v019-polish.js
node --check static/activity-plan-v020.js
python3 -m py_compile app.py dpp_entrypoint.py dpp_activity_plan_v020.py
python3 scripts/check_v020_activity_plan.py

echo "== VALIDAR VERDAD DE VERSIÓN =="
if grep -RIn --include='*.js' --include='*.html' 'v0\.0\.19' static; then
  echo "ERROR: quedan etiquetas v0.0.19 en static/"
  exit 1
fi
grep -q 'v0.0.20-dev' static/app.js
grep -q 'Coach del día · v0.0.20-dev' static/dashboard-coach-v17.js
grep -q 'Foto corporal · v0.0.20-dev' static/app.js
grep -q 'activity-plan-v020.js?v=020-version-truth' static/index.html

echo "== GUARDAR EN RAMA =="
git add static/app.js static/dashboard-coach-v17.js static/pantry-v019.js static/pantry-v019-polish.js static/index.html
if ! git diff --cached --quiet; then
  git commit -m "fix: make v0.0.20 the single visible version"
  git push origin "$BRANCH"
else
  echo "Versión visible ya unificada"
fi

echo "== DESPLEGAR =="
docker compose up -d --build --force-recreate

OK=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if curl -fsS http://127.0.0.1:8099/health >/tmp/dpp-v020-version-health.json 2>/dev/null; then
    OK=1
    break
  fi
  sleep 2
done
test "$OK" = "1"

python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path('/tmp/dpp-v020-version-health.json').read_text())
assert data.get('ok') is True, data
assert data.get('version') == 'v0.0.20-dev', data
print('HEALTH OK:', data)
PY

echo "== VALIDAR ARCHIVOS SERVIDOS =="
curl -fsS http://127.0.0.1:8099/ >/tmp/dpp-v020-index-served.html
curl -fsS 'http://127.0.0.1:8099/static/app.js?v=v020-version-truth' >/tmp/dpp-v020-app-served.js
curl -fsS 'http://127.0.0.1:8099/static/dashboard-coach-v17.js?v=020-version-truth' >/tmp/dpp-v020-coach-served.js
grep -q 'v0.0.20-dev' /tmp/dpp-v020-index-served.html
grep -q 'v0.0.20-dev' /tmp/dpp-v020-app-served.js
grep -q 'Coach del día · v0.0.20-dev' /tmp/dpp-v020-coach-served.js
! grep -q 'v0.0.19' /tmp/dpp-v020-index-served.html
! grep -q 'v0.0.19' /tmp/dpp-v020-app-served.js
! grep -q 'v0.0.19' /tmp/dpp-v020-coach-served.js

echo "== API PLAN =="
curl -fsS 'http://127.0.0.1:8099/api/activity-plan?from=2026-06-15&to=2026-06-21' |
python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("API OK: version=",d.get("version"),"plans=",len(d.get("plans",[])),"extras=",len(d.get("extra_workouts",[])))'

FAILED=0
trap - EXIT
echo "OK: versión visible unificada en v0.0.20-dev. Cierra la pestaña y abre la web de nuevo."

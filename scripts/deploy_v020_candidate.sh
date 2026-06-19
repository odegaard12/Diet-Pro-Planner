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

echo "== VALIDAR CÓDIGO =="
python3 -m py_compile \
  app.py \
  dpp_entrypoint.py \
  dpp_activity_plan_v020.py \
  dpp_pantry_v019.py \
  dpp_pantry_v019_policy.py \
  dpp_strava_v018.py
node --check static/activity-plan-v020.js
node --check static/pantry-v019-polish.js
python3 scripts/check_v020_activity_plan.py

echo "== VALIDAR BLOQUEO ELIMINADO =="
! grep -q 'MutationObserver(syncVersion)' static/activity-plan-v020.js
! grep -q 'setInterval(syncVersion' static/activity-plan-v020.js
! grep -q 'MutationObserver(syncVersion)' static/pantry-v019-polish.js
! grep -q 'setInterval(syncVersion' static/pantry-v019-polish.js
grep -q '__DPP_ACTIVITY_PLAN_V020__' static/activity-plan-v020.js
grep -q 'Plan deporte' static/activity-plan-v020.js
grep -q 'activity-plan-v020.js?v=020-loopfix' static/index.html

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

python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path('/tmp/dpp-v020-health.json').read_text())
assert data.get('ok') is True, data
assert data.get('version') == 'v0.0.20', data
print('HEALTH OK:', data)
PY

echo "== VALIDAR ARCHIVOS SERVIDOS =="
curl -fsS http://127.0.0.1:8099/ >/tmp/dpp-v020-index.html
grep -q 'activity-plan-v020.js?v=020-loopfix' /tmp/dpp-v020-index.html
curl -fsS http://127.0.0.1:8099/static/activity-plan-v020.js?v=020-loopfix >/tmp/dpp-v020-activity.js
grep -q '__DPP_ACTIVITY_PLAN_V020__' /tmp/dpp-v020-activity.js
! grep -q 'MutationObserver(syncVersion)' /tmp/dpp-v020-activity.js
! grep -q 'setInterval(syncVersion' /tmp/dpp-v020-activity.js

echo "== VALIDAR API =="
curl -fsS "http://127.0.0.1:8099/api/activity-plan?from=2026-06-15&to=2026-06-21" |
python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; assert d.get("version")=="v0.0.20"; print("API OK: plans=",len(d.get("plans",[])),"extras=",len(d.get("extra_workouts",[])),"summary=",d.get("summary"))'

echo "== DOCKER =="
docker compose ps

FAILED=0
trap - EXIT
echo "OK: v0.0.20 desplegada sin bucles. Cierra la pestaña vieja y abre de nuevo la web."

#!/usr/bin/env bash
set -Eeuo pipefail

cd "$HOME/Diet-Pro-Planner" || exit 1
BRANCH="feature/v021-full-modern-ui"

fail(){ echo "ERROR: $*" >&2; exit 1; }

echo "== SINCRONIZAR CANDIDATA V0.0.21 =="
git fetch origin --prune

git diff --quiet || fail "Hay cambios locales trackeados sin guardar"
git diff --cached --quiet || fail "Hay cambios preparados sin guardar"

git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
git reset --hard "origin/$BRANCH"

if [ -f data/dieta.db ]; then
  cp data/dieta.db "data/dieta.db.bak-v021-$(date +%Y%m%d-%H%M%S)"
fi

echo "== VALIDAR CÓDIGO =="
python3 -m py_compile \
  app.py \
  dpp_entrypoint.py \
  dpp_activity_plan_v020.py \
  dpp_pantry_v019.py \
  dpp_pantry_v019_policy.py \
  dpp_strava_v018.py

node --check static/app.js
node --check static/v021/runtime.js
node --check static/dashboard-coach-v17.js
node --check static/pantry-v019.js
node --check static/activity-plan-v020.js

python3 scripts/check_v021_ui.py
python3 scripts/check_frontend_monoliths.py
python3 scripts/check_repo_privacy.py
python3 scripts/check_v019_pantry.py
python3 scripts/check_v020_activity_plan.py

echo "== DESPLEGAR CANDIDATA =="
docker compose up -d --build --force-recreate

OK=0
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8099/health >/tmp/dpp-v021-health.json 2>/dev/null; then
    OK=1
    break
  fi
  sleep 2
done
test "$OK" = "1"

curl -fsS http://127.0.0.1:8099/ >/tmp/dpp-v021-index.html
curl -fsS 'http://127.0.0.1:8099/static/v021/core.css?v=021a' >/tmp/dpp-v021-core.css
curl -fsS 'http://127.0.0.1:8099/static/v021/runtime.js?v=021a' >/tmp/dpp-v021-runtime.js
curl -fsS http://127.0.0.1:8099/api/state >/tmp/dpp-v021-state.json
curl -fsS http://127.0.0.1:8099/api/pantry/v2 >/tmp/dpp-v021-pantry.json
curl -fsS 'http://127.0.0.1:8099/api/activity-plan?from=2026-06-15&to=2026-06-21' >/tmp/dpp-v021-activity.json

echo "== VERIFICACIÓN FUNCIONAL =="
python3 - <<'PY'
import json
from pathlib import Path

health = json.loads(Path('/tmp/dpp-v021-health.json').read_text())
state = json.loads(Path('/tmp/dpp-v021-state.json').read_text())
pantry = json.loads(Path('/tmp/dpp-v021-pantry.json').read_text())
activity = json.loads(Path('/tmp/dpp-v021-activity.json').read_text())
index = Path('/tmp/dpp-v021-index.html').read_text(encoding='utf-8')
core = Path('/tmp/dpp-v021-core.css').read_text(encoding='utf-8')
runtime = Path('/tmp/dpp-v021-runtime.js').read_text(encoding='utf-8')

assert health == {'app': 'Diet Pro Planner', 'ok': True, 'version': 'v0.0.21-dev'}, health
assert isinstance(state, dict) and 'today' in state, state.keys()
assert pantry.get('ok') is True, pantry
assert activity.get('ok') is True, activity
assert 'static/v021/core.css?v=021a' in index
assert 'static/v021/runtime.js?v=021a' in index
assert '--v21-primary:#365bd8' in core
assert '__DPP_V021_RUNTIME__' in runtime

print('HEALTH:', health)
print('STATE: ok · today=', state.get('today'))
print('PANTRY: ok · items=', len((pantry.get('pantry') or {}).get('items') or []))
print('ACTIVITY: ok · plans=', len(activity.get('plans') or []))
print('UI: assets v0.0.21 servidos')
PY

echo "== ESTADO =="
git log -1 --oneline
docker compose ps

echo "== PR =="
gh pr view 30 --repo odegaard12/Diet-Pro-Planner --json number,title,state,isDraft,mergeable,url || true

echo
echo "OK: v0.0.21-dev desplegada para probar en todas las páginas."
echo "ABRIR: http://192.168.68.103:8099/?v=021a"

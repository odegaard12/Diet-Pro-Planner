#!/usr/bin/env bash
set -Eeuo pipefail

cd "$HOME/Diet-Pro-Planner" || exit 1
BRANCH="feature/v020-planned-vs-real-activity"
KEEP_ID="18953941023"
DROP_ID="18948229153"

echo "== PREPARAR CANDIDATA =="
git fetch origin --prune
git checkout -B "$BRANCH" "origin/$BRANCH"

echo "== UNIFICAR VERSIÓN Y DESPLEGAR =="
bash scripts/fix_v020_version_truth.sh

echo "== SINCRONIZACIÓN STRAVA DE PRUEBA =="
curl -fsS -X POST http://127.0.0.1:8099/api/strava/auto-run \
  -H 'Content-Type: application/json' \
  -d '{}' >/tmp/dpp-v020-strava-sync.json
cat /tmp/dpp-v020-strava-sync.json
echo

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path('/tmp/dpp-v020-strava-sync.json').read_text())
assert payload.get('ok') is True, payload
print(
    'SYNC OK:',
    'received=', payload.get('received'),
    'imported=', payload.get('imported'),
    'updated=', payload.get('updated'),
    'skipped=', payload.get('skipped'),
    'details=', payload.get('details_requested'),
)
PY

echo "== VERIFICAR QUE HEVY NO REAPARECIÓ =="
docker exec -i dieta-tracker-oscar python - <<PY
import json
import sqlite3
from pathlib import Path

KEEP_ID = '$KEEP_ID'
DROP_ID = '$DROP_ID'

con = sqlite3.connect('/app/data/dieta.db')
con.row_factory = sqlite3.Row

keep = con.execute(
    "SELECT id,date,time,name,minutes,kcal,notes FROM workouts WHERE notes LIKE ?",
    (f'%id={KEEP_ID}%',),
).fetchall()

drop = con.execute(
    "SELECT id,date,time,name,minutes,kcal,notes FROM workouts WHERE notes LIKE ?",
    (f'%id={DROP_ID}%',),
).fetchall()

same_day = con.execute(
    "SELECT id,date,time,name,minutes,kcal,notes FROM workouts WHERE date='2026-06-16' AND name='WeightTraining' ORDER BY id"
).fetchall()

assert len(keep) == 1, [dict(row) for row in keep]
assert len(drop) == 0, [dict(row) for row in drop]
assert len(same_day) == 1, [dict(row) for row in same_day]
assert KEEP_ID in str(same_day[0]['notes']), dict(same_day[0])

ignored_path = Path('/app/data/strava_ignored_ids.json')
ignored = json.loads(ignored_path.read_text(encoding='utf-8'))
ids = ignored.get('ids', []) if isinstance(ignored, dict) else ignored
assert DROP_ID in [str(value) for value in ids], ignored

print('Actividad válida:', dict(same_day[0]))
print('Hevy ausente tras sincronizar:', DROP_ID)
print('Hevy continúa bloqueado:', DROP_ID)

summary = con.execute(
    "SELECT COUNT(*) activities, ROUND(SUM(minutes),1) minutes, ROUND(SUM(kcal),1) kcal FROM workouts WHERE date BETWEEN '2026-06-13' AND '2026-06-19'"
).fetchone()
print('Resumen 13-19 junio:', dict(summary))
con.close()
PY

echo "== VERIFICAR VERSIÓN Y PLAN DEPORTE =="
curl -fsS http://127.0.0.1:8099/health >/tmp/dpp-v020-final-health.json
curl -fsS http://127.0.0.1:8099/ >/tmp/dpp-v020-final-index.html
curl -fsS 'http://127.0.0.1:8099/static/app.js?v=v020-version-truth' >/tmp/dpp-v020-final-app.js
curl -fsS 'http://127.0.0.1:8099/static/activity-plan-v020.js?v=020-version-truth' >/tmp/dpp-v020-final-plan.js

python3 - <<'PY'
import json
from pathlib import Path

health = json.loads(Path('/tmp/dpp-v020-final-health.json').read_text())
assert health.get('ok') is True, health
assert health.get('version') == 'v0.0.20', health

index = Path('/tmp/dpp-v020-final-index.html').read_text(encoding='utf-8')
app = Path('/tmp/dpp-v020-final-app.js').read_text(encoding='utf-8')
plan = Path('/tmp/dpp-v020-final-plan.js').read_text(encoding='utf-8')

assert 'v0.0.20' in index
assert 'v0.0.19' not in index
assert 'v0.0.19' not in app
assert 'Plan deporte' in plan
assert '__DPP_ACTIVITY_PLAN_V020__' in plan

print('HEALTH OK:', health)
print('HTML/JS OK: versión única v0.0.20 y Plan deporte servido')
PY

echo "== ESTADO PR =="
gh pr view 23 --repo odegaard12/Diet-Pro-Planner \
  --json number,title,state,isDraft,headRefName,url

echo "OK FINAL: Strava estable, Hevy no reapareció, versión v0.0.20 unificada y Plan deporte listo para probar."

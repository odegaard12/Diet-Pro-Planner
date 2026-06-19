#!/usr/bin/env bash
set -Eeuo pipefail

cd "$HOME/Diet-Pro-Planner" || exit 1
BRANCH="feature/v020-planned-vs-real-activity"
KEEP_ID="18953941023"
DROP_ID="18948229153"
STAMP="$(date +%Y%m%d-%H%M%S)"

echo "== SINCRONIZAR RAMA =="
git fetch origin --prune
git checkout -B "$BRANCH" "origin/$BRANCH"

echo "== BACKUP BASE DE DATOS =="
cp data/dieta.db "data/dieta.db.bak-strava-duplicate-$STAMP"
echo "Backup: data/dieta.db.bak-strava-duplicate-$STAMP"

echo "== LIMPIAR DUPLICADO Y REGISTRAR ID IGNORADO =="
docker exec -i dieta-tracker-oscar python - <<PY
import json
import sqlite3
from pathlib import Path

DB = Path('/app/data/dieta.db')
IGNORED = Path('/app/data/strava_ignored_ids.json')
KEEP_ID = '$KEEP_ID'
DROP_ID = '$DROP_ID'

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

rows = con.execute(
    """
    SELECT id,date,time,name,minutes,distance_km,kcal,notes
    FROM workouts
    WHERE notes LIKE ? OR notes LIKE ?
    ORDER BY id
    """,
    (f'%id={KEEP_ID}%', f'%id={DROP_ID}%'),
).fetchall()

by_strava = {}
for row in rows:
    notes = str(row['notes'] or '')
    if f'id={KEEP_ID}' in notes:
        by_strava[KEEP_ID] = dict(row)
    if f'id={DROP_ID}' in notes:
        by_strava[DROP_ID] = dict(row)

assert KEEP_ID in by_strava, f'No existe la actividad Amazfit {KEEP_ID}'
assert DROP_ID in by_strava, f'No existe la actividad Hevy {DROP_ID}'

keep = by_strava[KEEP_ID]
drop = by_strava[DROP_ID]
assert keep['date'] == drop['date'] == '2026-06-16', (keep, drop)
assert keep['name'] == drop['name'] == 'WeightTraining', (keep, drop)

con.execute('DELETE FROM workouts WHERE id=?', (drop['id'],))
con.commit()

try:
    current = json.loads(IGNORED.read_text(encoding='utf-8')) if IGNORED.exists() else []
except Exception:
    current = []

if isinstance(current, dict):
    ids = [str(value) for value in current.get('ids', [])]
else:
    ids = [str(value) for value in current]

if DROP_ID not in ids:
    ids.append(DROP_ID)

payload = {
    'ids': sorted(set(ids)),
    'updated_at': '$STAMP',
    'reasons': {
        DROP_ID: 'Duplicado Hevy de la sesión Amazfit Balance 2026-06-16 19:40'
    },
}
IGNORED.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
IGNORED.chmod(0o600)

remaining = con.execute(
    """
    SELECT id,date,time,name,minutes,kcal,notes
    FROM workouts
    WHERE date='2026-06-16' AND name='WeightTraining'
    ORDER BY time,id
    """
).fetchall()

print('Conservada:', keep)
print('Eliminada:', drop)
print('Restantes 2026-06-16:', [dict(row) for row in remaining])
print('IDs ignorados:', payload['ids'])
con.close()
PY

echo "== PARCHEAR PROTECCIÓN STRAVA =="
python3 - <<'PY'
from pathlib import Path

path = Path('dpp_strava_v018.py')
text = path.read_text(encoding='utf-8')

old = '    cache_file = data_dir / "strava_activity_cache.json"\n'
new = old + '    ignored_ids_file = data_dir / "strava_ignored_ids.json"\n'
if 'ignored_ids_file = data_dir / "strava_ignored_ids.json"' not in text:
    if old not in text:
        raise SystemExit('No se encontró cache_file en dpp_strava_v018.py')
    text = text.replace(old, new, 1)

anchor = '''    def write_cache(value: dict[str, Any]) -> None:\n        if len(value) > 1000:\n            keys = sorted(\n                value,\n                key=lambda key: str((value.get(key) or {}).get("_cached_at") or ""),\n                reverse=True,\n            )[:750]\n            value = {key: value[key] for key in keys}\n        write_private_json(cache_file, value)\n\n'''
addition = anchor + '''    def read_ignored_ids() -> set[str]:\n        value = read_json(ignored_ids_file, [])\n        if isinstance(value, dict):\n            value = value.get("ids", [])\n        if not isinstance(value, list):\n            return set()\n        return {str(item).strip() for item in value if str(item).strip()}\n\n'''
if '    def read_ignored_ids() -> set[str]:' not in text:
    if anchor not in text:
        raise SystemExit('No se encontró write_cache en dpp_strava_v018.py')
    text = text.replace(anchor, addition, 1)

old_imported = '''    def imported_ids(db) -> set[str]:\n        rows = db.execute("SELECT notes FROM workouts WHERE notes LIKE '%id=%'").fetchall()\n        output: set[str] = set()\n        for row in rows:\n            text = row["notes"] if hasattr(row, "keys") else row[0]\n            match = re.search(r"\\bid=(\\d+)", str(text or ""))\n            if match:\n                output.add(match.group(1))\n        return output\n'''
new_imported = '''    def imported_ids(db) -> set[str]:\n        rows = db.execute("SELECT notes FROM workouts WHERE notes LIKE '%id=%'").fetchall()\n        output: set[str] = set(read_ignored_ids())\n        for row in rows:\n            text = row["notes"] if hasattr(row, "keys") else row[0]\n            output.update(re.findall(r"\\bid=(\\d+)", str(text or "")))\n        return output\n'''
if old_imported in text:
    text = text.replace(old_imported, new_imported, 1)
elif 'output: set[str] = set(read_ignored_ids())' not in text:
    raise SystemExit('No se pudo parchear imported_ids')

old_upsert = '''        if not activity_id:\n            return "skipped"\n        source = "detalle Strava" if exact else "estimación local"\n'''
new_upsert = '''        if not activity_id:\n            return "skipped"\n        if activity_id in read_ignored_ids():\n            return "skipped"\n        source = "detalle Strava" if exact else "estimación local"\n'''
if old_upsert in text:
    text = text.replace(old_upsert, new_upsert, 1)
elif 'if activity_id in read_ignored_ids()' not in text:
    raise SystemExit('No se pudo parchear upsert_activity')

path.write_text(text, encoding='utf-8')
PY

echo "== VALIDAR CÓDIGO =="
python3 -m py_compile app.py dpp_entrypoint.py dpp_strava_v018.py dpp_activity_plan_v020.py
grep -q 'strava_ignored_ids.json' dpp_strava_v018.py
grep -q 'activity_id in read_ignored_ids' dpp_strava_v018.py

echo "== COMMIT Y PUSH =="
git add dpp_strava_v018.py scripts/fix_strava_hevy_duplicate.sh
if ! git diff --cached --quiet; then
  git commit -m "fix: ignore duplicate Hevy Strava sessions"
  git push origin "$BRANCH"
else
  echo "Protección ya aplicada"
fi

echo "== RECONSTRUIR CANDIDATA =="
docker compose up -d --build --force-recreate

OK=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if curl -fsS http://127.0.0.1:8099/health >/tmp/dpp-strava-dedupe-health.json 2>/dev/null; then
    OK=1
    break
  fi
  sleep 2
done
test "$OK" = "1"

echo "== VERIFICACIÓN FINAL =="
docker exec -i dieta-tracker-oscar python - <<PY
import json
import sqlite3
from pathlib import Path

con = sqlite3.connect('/app/data/dieta.db')
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT id,date,time,name,minutes,kcal,notes FROM workouts WHERE date='2026-06-16' AND name='WeightTraining' ORDER BY id"
).fetchall()
assert len(rows) == 1, [dict(row) for row in rows]
assert 'id=$KEEP_ID' in str(rows[0]['notes']), dict(rows[0])
assert 'id=$DROP_ID' not in str(rows[0]['notes']), dict(rows[0])
ignored = json.loads(Path('/app/data/strava_ignored_ids.json').read_text(encoding='utf-8'))
ids = ignored.get('ids', []) if isinstance(ignored, dict) else ignored
assert '$DROP_ID' in [str(value) for value in ids], ignored
print('Actividad conservada:', dict(rows[0]))
print('ID Hevy bloqueado:', '$DROP_ID')

totals = con.execute(
    "SELECT ROUND(SUM(minutes),1) minutes, ROUND(SUM(kcal),1) kcal FROM workouts WHERE date BETWEEN '2026-06-13' AND '2026-06-19'"
).fetchone()
print('Totales 7 días corregidos:', dict(totals))
con.close()
PY

cat /tmp/dpp-strava-dedupe-health.json
echo
echo "OK: duplicado Hevy eliminado y bloqueado para futuras sincronizaciones."

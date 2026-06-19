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

echo "== ACTUALIZAR RAMA =="
git fetch origin --prune
git checkout -B "$BRANCH" "origin/$BRANCH"

python3 - <<'PY'
from pathlib import Path

pantry = Path("static/pantry-v019-polish.js")
text = pantry.read_text(encoding="utf-8")
version_block = '''  function syncVersion() {
    const title = `Diet Pro Planner · ${VERSION}`;
    const eyebrowText = `Dieta controlada · ${VERSION}`;
    if (document.title !== title) document.title = title;

    const eyebrow = document.querySelector('.eyebrow');
    if (eyebrow && eyebrow.textContent.trim() !== eyebrowText) eyebrow.textContent = eyebrowText;

    const badge = document.querySelector('#ui5Badge');
    if (badge && badge.textContent.trim() !== VERSION) badge.textContent = VERSION;

    document.querySelectorAll('.topbar *, [class*="version"], [data-version]').forEach((node) => {
      if (node.children.length) return;
      const text = String(node.textContent || '').trim();
      if (/^v0\.0\.18(?:\b|$)/.test(text)) node.textContent = VERSION;
    });
  }

'''
version_loop = '''  const observer = new MutationObserver(syncVersion);
  observer.observe(document.documentElement, {childList: true, characterData: true, subtree: true});
  syncVersion();
  setInterval(syncVersion, 500);
'''
if version_block not in text:
    raise SystemExit("No se encontró el bloque de versión de pantry polish")
if version_loop not in text:
    raise SystemExit("No se encontró el bucle de versión de pantry polish")
text = text.replace(version_block, "", 1).replace(version_loop, "", 1)
pantry.write_text(text, encoding="utf-8")

activity = Path("static/activity-plan-v020.js")
text = activity.read_text(encoding="utf-8")
needle = "  const VERSION = 'v0.0.20-dev';\n"
if "window.DPP_RUNTIME_VERSION = VERSION;" not in text:
    if needle not in text:
        raise SystemExit("No se encontró VERSION en activity plan")
    text = text.replace(needle, needle + "  window.DPP_RUNTIME_VERSION = VERSION;\n", 1)
loop = '''  const observer = new MutationObserver(syncVersion);
  observer.observe(document.documentElement, {childList:true, characterData:true, subtree:true});
  syncVersion();
  setInterval(syncVersion, 700);
'''
if loop not in text:
    raise SystemExit("No se encontró el bucle de versión de activity plan")
text = text.replace(loop, "  syncVersion();\n", 1)
activity.write_text(text, encoding="utf-8")

index = Path("static/index.html")
text = index.read_text(encoding="utf-8")
text = text.replace("Diet Pro Planner · v0.0.19", "Diet Pro Planner · v0.0.20-dev")
text = text.replace("Dieta controlada · v0.0.19", "Dieta controlada · v0.0.20-dev")
text = text.replace("pantry-v019-polish.js?v=019c", "pantry-v019-polish.js?v=020-lockfix")
text = text.replace("activity-plan-v020.js?v=020a", "activity-plan-v020.js?v=020-lockfix")
index.write_text(text, encoding="utf-8")
PY

echo "== VALIDAR FRONTEND =="
node --check static/pantry-v019-polish.js
node --check static/activity-plan-v020.js
! grep -q 'MutationObserver(syncVersion)' static/pantry-v019-polish.js
! grep -q 'setInterval(syncVersion' static/pantry-v019-polish.js
! grep -q 'MutationObserver(syncVersion)' static/activity-plan-v020.js
! grep -q 'setInterval(syncVersion' static/activity-plan-v020.js
python3 -m py_compile app.py dpp_entrypoint.py dpp_activity_plan_v020.py
python3 scripts/check_v020_activity_plan.py

echo "== GUARDAR HOTFIX =="
git add static/index.html static/pantry-v019-polish.js static/activity-plan-v020.js
if ! git diff --cached --quiet; then
  git commit -m "fix: stop frontend version mutation loop"
  git push origin "$BRANCH"
else
  echo "Hotfix ya aplicado"
fi

echo "== RECONSTRUIR =="
docker compose up -d --build --force-recreate

OK=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if curl -fsS http://127.0.0.1:8099/health >/tmp/dpp-v020-hotfix-health.json 2>/dev/null; then
    OK=1
    break
  fi
  sleep 2
done
test "$OK" = "1"

echo "== HEALTH =="
cat /tmp/dpp-v020-hotfix-health.json
echo

echo "== API =="
curl -fsS "http://127.0.0.1:8099/api/activity-plan?from=2026-06-15&to=2026-06-21" |
python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("version=",d.get("version"),"plans=",len(d.get("plans",[])),"extras=",len(d.get("extra_workouts",[])))'

echo "== HTML CACHE =="
curl -fsS http://127.0.0.1:8099/ | grep -E '020-lockfix|v0.0.20-dev' | head -n 6

FAILED=0
trap - EXIT
echo "OK: bloqueo del navegador corregido. Haz Ctrl+F5."

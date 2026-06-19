#!/usr/bin/env python3
from pathlib import Path

index = Path("static/index.html").read_text(encoding="utf-8")
entry = Path("dpp_entrypoint.py").read_text(encoding="utf-8")
runtime = Path("static/v021/runtime.js").read_text(encoding="utf-8")
core = Path("static/v021/core.css").read_text(encoding="utf-8")
dashboard = Path("static/v021/dashboard.css").read_text(encoding="utf-8")
modules = Path("static/v021/modules.css").read_text(encoding="utf-8")

assert "v0.0.21-dev" in index
assert 'class="dpp-v021"' in index
assert "/static/v021/core.css?v=021a" in index
assert "/static/v021/dashboard.css?v=021a" in index
assert "/static/v021/modules.css?v=021a" in index
assert "/static/v021/runtime.js?v=021a" in index
assert 'DPP_VERSION = "v0.0.21-dev"' in entry

assert "--v21-primary:#365bd8" in core
assert "grid-template-columns:232px" in core
assert ".dpp12-hero" in dashboard
assert ".pantry-hero" in modules
assert ".activity-plan-hero" in modules
assert ".strava-overview" in modules

assert "MutationObserver" not in runtime
assert "setInterval" not in runtime
assert "document.body.classList.add('dpp-v021')" in runtime

print("OK v0.0.21 UI: shell, dashboard, modules, mobile and version are consistent")

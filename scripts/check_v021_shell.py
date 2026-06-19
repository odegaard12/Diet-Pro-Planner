#!/usr/bin/env python3
from pathlib import Path

css = Path("static/design-system-v021.css")
js = Path("static/app-shell-v021.js")
index = Path("static/index.html")

assert css.exists(), "Falta static/design-system-v021.css"
assert js.exists(), "Falta static/app-shell-v021.js"

css_text = css.read_text(encoding="utf-8")
js_text = js.read_text(encoding="utf-8")
index_text = index.read_text(encoding="utf-8")

assert "--dpp-primary" in css_text
assert ".app-shell" in css_text
assert "@media(max-width:980px)" in css_text
assert "__DPP_APP_SHELL_V021__" in js_text
assert "MutationObserver" not in js_text
assert "setInterval" not in js_text
assert "/static/design-system-v021.css" in index_text
assert "/static/app-shell-v021.js" in index_text

print("OK v0.0.21 shell: design tokens, responsive shell and loop-free runtime")

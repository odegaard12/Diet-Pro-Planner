from __future__ import annotations

import os

import app as legacy
from dpp_pantry_v019 import register_pantry_v019
from dpp_strava_v018 import register_strava_v018


register_strava_v018(legacy.app, legacy)
register_pantry_v019(legacy.app, legacy)

try:
    legacy.start_strava_auto_thread()
except Exception as exc:
    print(f"[DPP] Strava auto-sync thread not started: {exc}")

if __name__ == "__main__":
    legacy.app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8099")))

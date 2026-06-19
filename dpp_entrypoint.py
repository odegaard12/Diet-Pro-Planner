from __future__ import annotations

import os

from flask import jsonify

import app as legacy
import dpp_activity_plan_v020 as activity_plan_v020
import dpp_pantry_v019 as pantry_v019
from dpp_pantry_v019_policy import apply_pantry_v019_policy
from dpp_strava_v018 import register_strava_v018


DPP_VERSION = "v0.0.21-dev"


apply_pantry_v019_policy(pantry_v019)
register_strava_v018(legacy.app, legacy)
pantry_v019.register_pantry_v019(legacy.app, legacy)
activity_plan_v020.register_activity_plan_v020(legacy.app, legacy)


def expose_candidate_health_version() -> None:
    for rule in legacy.app.url_map.iter_rules():
        if rule.rule != "/health":
            continue

        endpoint = rule.endpoint

        def candidate_health():
            return jsonify(
                {
                    "app": "Diet Pro Planner",
                    "ok": True,
                    "version": DPP_VERSION,
                }
            )

        legacy.app.view_functions[endpoint] = candidate_health
        return

    raise RuntimeError("Diet Pro Planner /health route is not registered")


expose_candidate_health_version()

try:
    legacy.start_strava_auto_thread()
except Exception as exc:
    print(f"[DPP] Strava auto-sync thread not started: {exc}")

if __name__ == "__main__":
    legacy.app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8099")))

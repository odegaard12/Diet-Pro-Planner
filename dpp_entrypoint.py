from __future__ import annotations

import os

import app as legacy
import dpp_activity_plan_v020 as activity_plan_v020
import dpp_db
import dpp_pantry_v019 as pantry_v019
from dpp_ai import register_ai_routes
from dpp_analytics import register_analytics_routes
from dpp_data_api import register_data_routes
from dpp_food_lookup import register_food_lookup_routes
from dpp_pantry_v019_policy import apply_pantry_v019_policy
from dpp_profile import register_profile_routes
from dpp_security import register_security
from dpp_strava_v018 import register_strava_v018
from dpp_validate import register_error_handlers


apply_pantry_v019_policy(pantry_v019)
register_strava_v018(legacy.app, legacy)
pantry_v019.register_pantry_v019(legacy.app, legacy)
activity_plan_v020.register_activity_plan_v020(legacy.app, legacy)
register_profile_routes(legacy.app)
register_analytics_routes(legacy.app)
register_data_routes(legacy.app)
register_ai_routes(legacy.app)
register_food_lookup_routes(legacy.app)
register_error_handlers(legacy.app)
register_security(legacy.app)

app = legacy.app


@app.get("/sw.js")
def service_worker():
    """Offline shell. Served from the root so it controls "/", with the version in its cache name
    so every deploy replaces the cached UI (public on purpose: it contains no data)."""
    from flask import Response
    body = (legacy.config.BASE_DIR / "static" / "sw.js").read_text(encoding="utf-8")
    resp = Response(body.replace("__DPP_VERSION__", legacy.config.VERSION), mimetype="text/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


def start_background_jobs() -> None:
    try:
        legacy.start_strava_auto_thread()
    except Exception as exc:
        print(f"[DPP] Strava auto-sync thread not started: {exc}")
    try:
        dpp_db.start_backup_thread()
    except Exception as exc:
        print(f"[DPP] daily backup thread not started: {exc}")


if os.environ.get("DPP_DISABLE_BACKGROUND_JOBS") != "1":
    start_background_jobs()


def serve() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8099"))
    if os.environ.get("DPP_SERVER", "waitress") != "flask":
        try:
            from waitress import serve as waitress_serve
        except ImportError:
            waitress_serve = None
        if waitress_serve:
            print(f"[DPP] {legacy.config.APP_NAME} {legacy.config.VERSION} on http://{host}:{port} (waitress)")
            waitress_serve(legacy.app, host=host, port=port, threads=int(os.environ.get("DPP_THREADS", "8")))
            return
    legacy.app.run(host=host, port=port, threaded=True, debug=False)


if __name__ == "__main__":
    serve()

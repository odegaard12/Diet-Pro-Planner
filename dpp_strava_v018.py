from __future__ import annotations

import ipaddress
import json
import re
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from flask import jsonify, redirect, request


VERSION = "v0.0.18"
_SYNC_LOCK = threading.Lock()


class StravaRateLimitError(RuntimeError):
    pass


def register_strava_v018(app, legacy) -> None:
    data_dir = Path(getattr(legacy, "DATA", Path("data")))
    data_dir.mkdir(parents=True, exist_ok=True)

    config_file = data_dir / "integrations.json"
    rate_file = data_dir / "strava_rate.json"
    cache_file = data_dir / "strava_activity_cache.json"
    ignored_ids_file = data_dir / "strava_ignored_ids.json"
    token_file = Path(getattr(legacy, "STRAVA_TOKEN_FILE", data_dir / "strava_tokens.json"))
    state_file = Path(getattr(legacy, "STRAVA_STATE_FILE", data_dir / "strava_oauth_state.txt"))

    original_strava_config = legacy.strava_config
    original_refresh = legacy.refresh_strava_if_needed

    def read_json(path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default

    def write_private_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except Exception:
            pass
        tmp.replace(path)
        try:
            path.chmod(0o600)
        except Exception:
            pass

    def local_only() -> bool:
        raw = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        raw = raw.split(",", 1)[0].strip()
        try:
            address = ipaddress.ip_address(raw)
            return bool(address.is_private or address.is_loopback or address.is_link_local)
        except ValueError:
            return raw in {"localhost", "srv-web-01"}

    def load_integrations() -> dict[str, Any]:
        value = read_json(config_file, {})
        return value if isinstance(value, dict) else {}

    def effective_config() -> dict[str, str]:
        env_cfg = original_strava_config()
        root = load_integrations()
        local = root.get("strava") if isinstance(root.get("strava"), dict) else {}
        return {
            "client_id": str(local.get("client_id") or env_cfg.get("client_id") or "").strip(),
            "client_secret": str(local.get("client_secret") or env_cfg.get("client_secret") or "").strip(),
            "redirect_uri": str(local.get("redirect_uri") or env_cfg.get("redirect_uri") or "").strip(),
        }

    # Existing legacy routes look this name up dynamically.
    legacy.strava_config = effective_config

    def suggested_callback() -> str:
        return request.url_root.rstrip("/") + "/api/strava/callback"

    def callback_host(value: str) -> str:
        try:
            return urlparse(value).hostname or ""
        except Exception:
            return ""

    def next_quarter_label() -> str:
        now = datetime.now()
        minute = ((now.minute // 15) + 1) * 15
        target = now.replace(second=0, microsecond=0)
        if minute >= 60:
            target = (target + timedelta(hours=1)).replace(minute=0)
        else:
            target = target.replace(minute=minute)
        return target.strftime("%H:%M")

    def parse_pair(value: str | None) -> list[int]:
        try:
            return [int(part.strip()) for part in str(value or "").split(",")[:2]]
        except Exception:
            return []

    def record_rate(response: requests.Response) -> dict[str, Any]:
        info = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "status_code": int(response.status_code),
            "limit": parse_pair(response.headers.get("X-RateLimit-Limit")),
            "usage": parse_pair(response.headers.get("X-RateLimit-Usage")),
            "read_limit": parse_pair(response.headers.get("X-ReadRateLimit-Limit")),
            "read_usage": parse_pair(response.headers.get("X-ReadRateLimit-Usage")),
            "retry_after": response.headers.get("Retry-After", ""),
            "next_reset_local": next_quarter_label(),
        }
        write_private_json(rate_file, info)
        return info

    def rate_snapshot() -> dict[str, Any]:
        value = read_json(rate_file, {})
        return value if isinstance(value, dict) else {}

    def strava_get(url: str, access_token: str, params: dict[str, Any] | None = None) -> requests.Response:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params or {},
            timeout=25,
        )
        record_rate(response)
        if response.status_code == 429:
            raise StravaRateLimitError(
                f"Límite temporal de Strava alcanzado. Pausa automática hasta aproximadamente las {next_quarter_label()}."
            )
        response.raise_for_status()
        return response

    def read_cache() -> dict[str, Any]:
        value = read_json(cache_file, {})
        return value if isinstance(value, dict) else {}

    def write_cache(value: dict[str, Any]) -> None:
        if len(value) > 1000:
            keys = sorted(
                value,
                key=lambda key: str((value.get(key) or {}).get("_cached_at") or ""),
                reverse=True,
            )[:750]
            value = {key: value[key] for key in keys}
        write_private_json(cache_file, value)

    def read_ignored_ids() -> set[str]:
        value = read_json(ignored_ids_file, [])
        if isinstance(value, dict):
            value = value.get("ids", [])
        if not isinstance(value, list):
            return set()
        return {str(item).strip() for item in value if str(item).strip()}

    def fetch_detail(access_token: str, activity_id: str) -> dict[str, Any] | None:
        if not activity_id:
            return None
        cache = read_cache()
        cached = cache.get(str(activity_id))
        if isinstance(cached, dict):
            return dict(cached)
        response = strava_get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            access_token,
            {"include_all_efforts": "false"},
        )
        value = response.json()
        if not isinstance(value, dict):
            return None
        value["_cached_at"] = datetime.now().isoformat(timespec="seconds")
        cache[str(activity_id)] = value
        write_cache(cache)
        return dict(value)

    def list_activities(access_token: str, after_date: str, before_date: str) -> list[dict[str, Any]]:
        after = legacy._epoch_from_date(after_date, False)
        before = legacy._epoch_from_date(before_date, True) if before_date else int(time.time())
        output: list[dict[str, Any]] = []
        for page_number in range(1, 6):
            response = strava_get(
                "https://www.strava.com/api/v3/athlete/activities",
                access_token,
                {"after": after, "before": before, "page": page_number, "per_page": 100},
            )
            batch = response.json()
            if not isinstance(batch, list) or not batch:
                break
            output.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 100:
                break
        return output

    def imported_ids(db) -> set[str]:
        rows = db.execute("SELECT notes FROM workouts WHERE notes LIKE '%id=%'").fetchall()
        output: set[str] = set(read_ignored_ids())
        for row in rows:
            text = row["notes"] if hasattr(row, "keys") else row[0]
            output.update(re.findall(r"\bid=(\d+)", str(text or "")))
        return output

    def upsert_activity(db, item: dict[str, Any], exact: bool) -> str:
        card = legacy._strava_card(item)
        activity_id = str(card.get("id") or "")
        if not activity_id:
            return "skipped"
        if activity_id in read_ignored_ids():
            return "skipped"
        source = "detalle Strava" if exact else "estimación local"
        notes = f"Strava · {card['title']} · id={activity_id} · kcal desde {source}"
        existing = db.execute(
            "SELECT id FROM workouts WHERE notes LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%id={activity_id}%",),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE workouts SET date=?,time=?,name=?,minutes=?,distance_km=?,kcal=?,notes=? WHERE id=?",
                (
                    card["date"], card["time"], card["sport_type"], card["minutes"],
                    card["distance_km"], card["kcal"], notes, existing["id"],
                ),
            )
            return "updated"
        db.execute(
            "INSERT INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes) VALUES(?,?,?,?,?,?,?,?)",
            (
                card["date"], card["time"], None, card["sport_type"], card["minutes"],
                card["distance_km"], card["kcal"], notes,
            ),
        )
        return "imported"

    def get_tokens() -> dict[str, Any]:
        tokens = legacy.read_strava_tokens()
        if not tokens:
            raise RuntimeError("Strava no conectado")
        return original_refresh(tokens)

    @app.get("/api/integrations/strava/config")
    def strava_v018_get_config():
        if not local_only():
            return jsonify({"error": "Configuración disponible solo desde la red local"}), 403
        cfg = effective_config()
        tokens = legacy.read_strava_tokens() or {}
        callback = cfg["redirect_uri"] or suggested_callback()
        return jsonify({
            "ok": True,
            "client_id": cfg["client_id"],
            "client_secret_set": bool(cfg["client_secret"]),
            "redirect_uri": cfg["redirect_uri"],
            "suggested_redirect_uri": suggested_callback(),
            "callback_domain": callback_host(callback),
            "connected": bool(tokens.get("access_token")),
            "scope": tokens.get("scope") or "",
            "storage": "data/integrations.json" if config_file.exists() else "environment",
        })

    @app.post("/api/integrations/strava/config")
    def strava_v018_save_config():
        if not local_only():
            return jsonify({"error": "Configuración disponible solo desde la red local"}), 403
        body = request.get_json(silent=True) or {}
        current = effective_config()
        client_id = str(body.get("client_id") or current["client_id"]).strip()
        client_secret = str(body.get("client_secret") or current["client_secret"]).strip()
        redirect_uri = str(body.get("redirect_uri") or suggested_callback()).strip()
        if not client_id.isdigit():
            return jsonify({"error": "Client ID debe contener solo números"}), 400
        if len(client_secret) < 16:
            return jsonify({"error": "Client Secret vacío o demasiado corto"}), 400
        parsed = urlparse(redirect_uri)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return jsonify({"error": "Callback URL no válida"}), 400
        if parsed.username or parsed.password:
            return jsonify({"error": "La Callback URL no puede incluir credenciales"}), 400
        if not parsed.path.endswith("/api/strava/callback"):
            return jsonify({"error": "La Callback URL debe terminar en /api/strava/callback"}), 400
        root = load_integrations()
        root["strava"] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        write_private_json(config_file, root)
        return jsonify({
            "ok": True,
            "client_id": client_id,
            "client_secret_set": True,
            "redirect_uri": redirect_uri,
            "callback_domain": parsed.hostname,
            "message": "Configuración Strava guardada localmente",
        })

    @app.post("/api/integrations/strava/disconnect")
    def strava_v018_disconnect():
        if not local_only():
            return jsonify({"error": "Acción disponible solo desde la red local"}), 403
        if token_file.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = token_file.with_name(f"{token_file.name}.bak-{stamp}")
            backup.write_bytes(token_file.read_bytes())
            try:
                backup.chmod(0o600)
            except Exception:
                pass
            token_file.unlink()
        state_file.unlink(missing_ok=True)
        return jsonify({"ok": True, "message": "Strava desconectado; credenciales conservadas"})

    @app.get("/api/integrations/strava/diagnostics")
    def strava_v018_diagnostics():
        cfg = effective_config()
        tokens = legacy.read_strava_tokens() or {}
        auto = legacy.read_strava_auto_config()
        return jsonify({
            "ok": True,
            "configured": bool(cfg["client_id"] and cfg["client_secret"] and cfg["redirect_uri"]),
            "connected": bool(tokens.get("access_token")),
            "redirect_uri": cfg["redirect_uri"],
            "callback_domain": callback_host(cfg["redirect_uri"]),
            "scope": tokens.get("scope") or "",
            "expires_at": tokens.get("expires_at"),
            "rate": rate_snapshot(),
            "auto_sync": {
                "enabled": bool(auto.get("enabled")),
                "interval_minutes": auto.get("interval_minutes"),
                "last_success_at": auto.get("last_success_at"),
                "last_message": auto.get("last_message"),
            },
        })

    @app.post("/api/integrations/strava/test")
    def strava_v018_test():
        if not _SYNC_LOCK.acquire(blocking=False):
            return jsonify({"error": "Ya hay otra operación Strava en curso"}), 409
        try:
            tokens = get_tokens()
            response = strava_get("https://www.strava.com/api/v3/athlete", tokens["access_token"])
            athlete = response.json() if response.content else {}
            return jsonify({
                "ok": True,
                "message": "Conexión Strava correcta",
                "athlete": {
                    "id": athlete.get("id"),
                    "firstname": athlete.get("firstname"),
                    "lastname": athlete.get("lastname"),
                },
                "rate": rate_snapshot(),
            })
        except Exception as exc:
            return jsonify({"error": str(exc), "rate": rate_snapshot()}), 400
        finally:
            _SYNC_LOCK.release()

    def callback_v018():
        if not legacy.strava_configured():
            return "Strava no configurado", 400
        expected = state_file.read_text(encoding="utf-8").strip() if state_file.exists() else ""
        received = request.args.get("state", "")
        if expected and received != expected:
            return "Estado OAuth no válido", 400
        code = request.args.get("code")
        if not code:
            return "Falta code de Strava", 400
        cfg = effective_config()
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=20,
        )
        response.raise_for_status()
        legacy.write_strava_tokens(response.json())
        state_file.unlink(missing_ok=True)
        return redirect("/?strava=connected")

    def preview_v018():
        if not _SYNC_LOCK.acquire(blocking=False):
            return jsonify({"error": "Ya hay otra operación Strava en curso"}), 409
        try:
            body = request.get_json(silent=True) or {}
            after_date = str(body.get("after_date") or date.today().isoformat())
            before_date = str(body.get("before_date") or date.today().isoformat())
            tokens = get_tokens()
            summaries = list_activities(tokens["access_token"], after_date, before_date)
            with legacy.con() as db:
                done = imported_ids(db)
            cards = []
            for item in summaries:
                card = legacy._strava_card(item)
                card["already_imported"] = str(card.get("id") or "") in done
                card["kcal_is_estimate"] = True
                cards.append(card)
            return jsonify({
                "ok": True,
                "activities": cards,
                "received": len(cards),
                "details_requested": 0,
                "rate": rate_snapshot(),
            })
        except Exception as exc:
            return jsonify({"error": str(exc), "rate": rate_snapshot()}), 400
        finally:
            _SYNC_LOCK.release()

    def import_v018():
        if not _SYNC_LOCK.acquire(blocking=False):
            return jsonify({"error": "Ya hay otra operación Strava en curso"}), 409
        try:
            body = request.get_json(silent=True) or {}
            selected = {str(value) for value in body.get("ids") or [] if str(value)}
            if not selected:
                return jsonify({"error": "No seleccionaste actividades"}), 400
            after_date = str(body.get("after_date") or date.today().isoformat())
            before_date = str(body.get("before_date") or date.today().isoformat())
            tokens = get_tokens()
            summaries = list_activities(tokens["access_token"], after_date, before_date)
            selected_items = [item for item in summaries if str(item.get("id") or "") in selected]
            counts = {"imported": 0, "updated": 0, "skipped": 0}
            details_requested = 0
            with legacy.con() as db:
                done = imported_ids(db)
                for summary in selected_items:
                    activity_id = str(summary.get("id") or "")
                    if activity_id in done:
                        counts["skipped"] += 1
                        continue
                    detail = fetch_detail(tokens["access_token"], activity_id)
                    details_requested += 1
                    merged = {**summary, **(detail or {})}
                    result = upsert_activity(db, merged, bool(detail))
                    counts[result] = counts.get(result, 0) + 1
            return jsonify({
                "ok": True,
                **counts,
                "received": len(summaries),
                "selected": len(selected_items),
                "details_requested": details_requested,
                "rate": rate_snapshot(),
            })
        except Exception as exc:
            return jsonify({"error": str(exc), "rate": rate_snapshot()}), 400
        finally:
            _SYNC_LOCK.release()

    def stable_auto_sync(force: bool = False) -> dict[str, Any]:
        if not _SYNC_LOCK.acquire(blocking=False):
            return {"ok": False, "error": "Ya hay otra operación Strava en curso"}
        try:
            cfg = legacy.read_strava_auto_config()
            if not force and not cfg.get("enabled"):
                return {"ok": True, "enabled": False, "message": "Sincronización automática desactivada"}
            if not legacy.read_strava_tokens():
                cfg["last_sync_at"] = legacy._auto_now_label()
                cfg["last_message"] = "Strava no conectado"
                legacy.write_strava_auto_config(cfg)
                return {"ok": False, "error": "Strava no conectado"}

            candidates = []
            try:
                candidates.append(datetime.strptime(str(cfg.get("after_date") or ""), "%Y-%m-%d").date())
            except Exception:
                pass
            try:
                latest = datetime.strptime(str(legacy._latest_strava_import_date() or ""), "%Y-%m-%d").date()
                candidates.append(latest - timedelta(days=1))
            except Exception:
                pass
            after_day = max(candidates) if candidates else date.today() - timedelta(days=2)
            before_day = date.today()

            tokens = get_tokens()
            summaries = list_activities(tokens["access_token"], after_day.isoformat(), before_day.isoformat())
            counts = {"imported": 0, "updated": 0, "skipped": 0}
            details_requested = 0
            with legacy.con() as db:
                done = imported_ids(db)
                for summary in summaries:
                    activity_id = str(summary.get("id") or "")
                    if not activity_id or activity_id in done:
                        counts["skipped"] += 1
                        continue
                    detail = fetch_detail(tokens["access_token"], activity_id)
                    details_requested += 1
                    merged = {**summary, **(detail or {})}
                    result = upsert_activity(db, merged, bool(detail))
                    counts[result] = counts.get(result, 0) + 1

            label = legacy._auto_now_label()
            result = {
                "received": len(summaries),
                **counts,
                "details_requested": details_requested,
                "after_date": after_day.isoformat(),
                "before_date": before_day.isoformat(),
                "rate": rate_snapshot(),
            }
            cfg["last_sync_at"] = label
            cfg["last_success_at"] = label
            cfg["last_message"] = f"Sincronizado correctamente a {label}"
            cfg["last_result"] = result
            cfg["_last_run_ts"] = int(time.time())
            legacy.write_strava_auto_config(cfg)
            return {"ok": True, **result, "message": cfg["last_message"]}
        except Exception as exc:
            cfg = legacy.read_strava_auto_config()
            label = legacy._auto_now_label()
            cfg["last_sync_at"] = label
            cfg["last_message"] = str(exc)
            cfg["_last_run_ts"] = int(time.time())
            legacy.write_strava_auto_config(cfg)
            return {"ok": False, "error": str(exc), "message": cfg["last_message"], "rate": rate_snapshot()}
        finally:
            _SYNC_LOCK.release()

    legacy.run_strava_auto_sync = stable_auto_sync

    if "api_strava_callback" in app.view_functions:
        app.view_functions["api_strava_callback"] = callback_v018
    if "api_strava_preview" in app.view_functions:
        app.view_functions["api_strava_preview"] = preview_v018
    if "api_strava_import" in app.view_functions:
        app.view_functions["api_strava_import"] = import_v018

    for rule in list(app.url_map.iter_rules()):
        if rule.rule == "/health":
            app.view_functions[rule.endpoint] = lambda: jsonify({
                "app": "Diet Pro Planner", "ok": True, "version": VERSION
            })
            break

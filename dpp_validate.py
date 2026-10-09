"""Small input-validation helpers shared by API routes.

Raising ``ApiError`` from a route returns a JSON ``{"ok": false, "error": …}``
with the given status instead of an HTML 500 page.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def json_body() -> dict[str, Any]:
    """Request JSON as a dict ({} when empty); a list or scalar body is a 400, not a 500."""
    from flask import request

    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ApiError("El cuerpo debe ser un objeto JSON")
    return payload


def integer_id(value: Any, field: str = "id") -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, (dict, list)):
        raise ApiError(f"{field} no válido")
    try:
        return int(str(value).strip())
    except ValueError:
        raise ApiError(f"{field} no válido") from None


def number(value: Any, field: str, default: float | None = None,
           minimum: float = 0.0, maximum: float = 100000.0) -> float:
    if value in (None, ""):
        if default is None:
            raise ApiError(f"Falta {field}")
        return float(default)
    if isinstance(value, (dict, list, bool)):
        raise ApiError(f"{field} debe ser un número")
    try:
        parsed = float(str(value).strip().replace(",", "."))
    except ValueError:
        raise ApiError(f"{field} debe ser un número") from None
    if math.isnan(parsed) or math.isinf(parsed):
        raise ApiError(f"{field} debe ser un número")
    if parsed < minimum or parsed > maximum:
        raise ApiError(f"{field} fuera de rango ({minimum:g}–{maximum:g})")
    return parsed


def iso_date(value: Any, default: str | None = None, field: str = "fecha") -> str:
    raw = str(value or default or date.today().isoformat()).strip()
    if not _DATE_RE.match(raw):
        raise ApiError(f"{field} no válida; usa YYYY-MM-DD")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ApiError(f"{field} no válida; usa YYYY-MM-DD") from None


def hhmm(value: Any, default: str | None = None, field: str = "hora") -> str:
    raw = str(value or default or datetime.now().strftime("%H:%M")).strip()[:5]
    try:
        return datetime.strptime(raw, "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ApiError(f"{field} no válida; usa HH:MM") from None


def text(value: Any, max_len: int = 500, default: str = "") -> str:
    return str(value if value is not None else default).strip()[:max_len]


def public_error(exc: BaseException, fallback: str = "Error interno; revisa los logs del servidor") -> str:
    """Message safe to return to the client.

    Our own errors (ApiError, RuntimeError and ValueError raised with Spanish user
    messages) pass through; library errors (HTTP clients, SQLite, KeyError…) can embed
    URLs, SQL or internals, so they are logged and replaced by a generic message.
    """
    try:
        import requests

        if isinstance(exc, requests.HTTPError):
            status = getattr(getattr(exc, "response", None), "status_code", None)
            return f"El servicio externo respondió con un error (HTTP {status})" if status else "Error del servicio externo"
        if isinstance(exc, requests.RequestException):
            return "No se pudo contactar con el servicio externo"
    except ImportError:  # pragma: no cover
        pass
    if isinstance(exc, ApiError):
        return exc.message
    if type(exc) in (RuntimeError, ValueError) or (isinstance(exc, RuntimeError) and type(exc).__module__.startswith("dpp")):
        return str(exc)[:300]
    import logging

    logging.getLogger("dpp").warning("Hidden internal error: %s: %s", type(exc).__name__, exc)
    return fallback


def register_error_handlers(app) -> None:
    from flask import jsonify, request
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        return jsonify({"ok": False, "error": exc.message}), exc.status

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        if not (request.path or "").startswith("/api/"):
            return exc
        messages = {
            404: "Ruta no encontrada",
            405: "Método no permitido",
            413: "Archivo demasiado grande",
        }
        return jsonify({"ok": False, "error": messages.get(exc.code or 0, exc.description)}), exc.code

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception):
        if isinstance(exc, HTTPException):
            return _http_error(exc)
        app.logger.exception("Unhandled error on %s", request.path)
        if (request.path or "").startswith("/api/"):
            return jsonify({"ok": False, "error": "Error interno; revisa los logs del servidor"}), 500
        return "Error interno", 500

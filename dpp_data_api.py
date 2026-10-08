"""Backups and exports.

- ``GET  /api/backup``           list local snapshots + schema info
- ``POST /api/backup``           create a snapshot now (private network only)
- ``GET  /api/backup/download``  download a consistent SQLite copy
- ``GET  /api/export/<kind>.csv`` meals, weights or workouts as CSV (Excel-friendly)
"""

from __future__ import annotations

import csv
import io
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Response, after_this_request, jsonify, send_file

import dpp_config as config
import dpp_db
from dpp_security import is_private_request
from dpp_validate import ApiError

_CSV_QUERIES = {
    "meals": (
        "SELECT m.date, m.time, m.name AS meal, i.food_name AS food, i.grams, i.kcal, i.protein,"
        " i.carbs, i.fat, i.sugar, i.salt, m.notes FROM meals m JOIN meal_items i ON i.meal_id = m.id"
        " ORDER BY m.date, m.time, m.id, i.id"
    ),
    "weights": "SELECT date, time, kg, official, context FROM weights ORDER BY date, time, id",
    "workouts": "SELECT date, time, name, minutes, distance_km, kcal, notes FROM workouts ORDER BY date, time, id",
}


def register_data_routes(app) -> None:
    @app.get("/api/backup")
    def backup_list():
        return jsonify({
            "ok": True,
            "schema_version": dpp_db.user_version(),
            "keep_daily": config.BACKUP_KEEP,
            "backups": dpp_db.list_backups()[:50],
        })

    @app.post("/api/backup")
    def backup_create():
        if not is_private_request():
            raise ApiError("Las copias solo se pueden crear desde la red local", 403)
        target = dpp_db.snapshot(label="manual")
        return jsonify({"ok": True, "name": target.name, "message": "Copia creada"})

    @app.get("/api/backup/download")
    def backup_download():
        tmp_dir = Path(tempfile.mkdtemp(prefix="dpp-backup-"))
        target = dpp_db.snapshot(label="download", dest_dir=tmp_dir)

        @after_this_request
        def _cleanup(response):
            target.unlink(missing_ok=True)
            try:
                tmp_dir.rmdir()
            except OSError:
                pass
            return response

        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        response = send_file(target, as_attachment=True, download_name=f"diet-pro-planner-{stamp}.db",
                             mimetype="application/vnd.sqlite3", max_age=0)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/export/<kind>.csv")
    def export_csv(kind: str):
        query = _CSV_QUERIES.get(kind)
        if not query:
            raise ApiError("Exportación no disponible", 404)
        with dpp_db.connect() as db:
            cur = db.execute(query)
            headers = [col[0] for col in cur.description]
            rows = cur.fetchall()
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(headers)
        for row in rows:
            writer.writerow([str(value).replace(".", ",") if isinstance(value, float) else value for value in row])
        stamp = datetime.now().strftime("%Y%m%d")
        # BOM so Excel opens UTF-8 accents correctly.
        return Response(
            "﻿" + buffer.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{kind}-{stamp}.csv"',
                "Cache-Control": "no-store",
            },
        )

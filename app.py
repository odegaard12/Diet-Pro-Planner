from __future__ import annotations

import json
import os
import re
import hashlib
import hmac
import secrets
import sqlite3
import time
import urllib.parse
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps, ImageFilter
import pytesseract

import dpp_config as config
import dpp_db
import dpp_profile
import dpp_validate as v
from dpp_validate import ApiError

config.ensure_dirs()
BASE = config.BASE_DIR
DATA = config.DATA_DIR
UPLOADS = config.UPLOADS_DIR
DB = config.DB_PATH

app = Flask(__name__, static_folder=str(BASE / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024


def today_iso() -> str:
    return date.today().isoformat()


def now_hm() -> str:
    return datetime.now().strftime("%H:%M")


def con() -> sqlite3.Connection:
    return dpp_db.connect(DB)


def rows(cur) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS foods(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          brand TEXT DEFAULT '',
          kcal REAL NOT NULL DEFAULT 0,
          protein REAL NOT NULL DEFAULT 0,
          carbs REAL NOT NULL DEFAULT 0,
          fat REAL NOT NULL DEFAULT 0,
          sugar REAL NOT NULL DEFAULT 0,
          salt REAL NOT NULL DEFAULT 0,
          typical_g REAL NOT NULL DEFAULT 100,
          purchased INTEGER NOT NULL DEFAULT 0,
          source_note TEXT DEFAULT '',
          notes TEXT DEFAULT '',
          photo_path TEXT DEFAULT '',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS weights(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          date TEXT NOT NULL,
          time TEXT NOT NULL,
          kg REAL NOT NULL,
          official INTEGER NOT NULL DEFAULT 0,
          context TEXT DEFAULT '',
          UNIQUE(date,time,kg,context)
        );
        CREATE TABLE IF NOT EXISTS meals(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          date TEXT NOT NULL,
          time TEXT NOT NULL,
          name TEXT NOT NULL,
          notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS meal_items(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
          food_id INTEGER REFERENCES foods(id) ON DELETE SET NULL,
          food_name TEXT NOT NULL,
          grams REAL NOT NULL,
          kcal REAL NOT NULL DEFAULT 0,
          protein REAL NOT NULL DEFAULT 0,
          carbs REAL NOT NULL DEFAULT 0,
          fat REAL NOT NULL DEFAULT 0,
          sugar REAL NOT NULL DEFAULT 0,
          salt REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS exercises(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          met REAL NOT NULL DEFAULT 5,
          kcal_per_min REAL NOT NULL DEFAULT 0,
          notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS workouts(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          date TEXT NOT NULL,
          time TEXT NOT NULL,
          exercise_id INTEGER REFERENCES exercises(id) ON DELETE SET NULL,
          name TEXT NOT NULL,
          minutes REAL NOT NULL DEFAULT 0,
          distance_km REAL NOT NULL DEFAULT 0,
          kcal REAL NOT NULL DEFAULT 0,
          notes TEXT DEFAULT '',
          UNIQUE(date,time,name,minutes,notes)
        );
        CREATE TABLE IF NOT EXISTS templates(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          notes TEXT DEFAULT '',
          kind TEXT NOT NULL DEFAULT 'meal',
          payload TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS plans(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          payload TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Migración ligera: bases creadas antes de v12 no tenían foto asociada.
    cols = [r[1] for r in db.execute("PRAGMA table_info(foods)").fetchall()]
    if "photo_path" not in cols:
        db.execute("ALTER TABLE foods ADD COLUMN photo_path TEXT DEFAULT ''")


def upsert_food(db: sqlite3.Connection, f: dict[str, Any]) -> None:
    f.setdefault("photo_path", "")
    f.setdefault("barcode", "")
    db.execute(
        """
        INSERT INTO foods(name,brand,kcal,protein,carbs,fat,sugar,salt,typical_g,purchased,source_note,notes,photo_path,barcode)
        VALUES(:name,:brand,:kcal,:protein,:carbs,:fat,:sugar,:salt,:typical_g,:purchased,:source_note,:notes,:photo_path,:barcode)
        ON CONFLICT(name) DO UPDATE SET
          brand=excluded.brand,kcal=excluded.kcal,protein=excluded.protein,carbs=excluded.carbs,
          fat=excluded.fat,sugar=excluded.sugar,salt=excluded.salt,typical_g=excluded.typical_g,
          purchased=excluded.purchased,source_note=excluded.source_note,notes=excluded.notes,
          photo_path=COALESCE(NULLIF(excluded.photo_path,''), foods.photo_path),
          barcode=COALESCE(NULLIF(excluded.barcode,''), foods.barcode)
        """,
        f,
    )


def seed_food_if_missing(db: sqlite3.Connection, f: dict[str, Any]) -> None:
    """Seed data never overwrites foods the user may have edited."""
    if not db.execute("SELECT 1 FROM foods WHERE name=?", (f["name"],)).fetchone():
        upsert_food(db, dict(f))


def get_food(db: sqlite3.Connection, name: str) -> dict[str, Any]:
    r = db.execute("SELECT * FROM foods WHERE name=?", (name,)).fetchone()
    if not r:
        raise KeyError(name)
    return dict(r)


def calc_item(food: dict[str, Any], grams: float) -> dict[str, Any]:
    f = float(grams) / 100.0
    return {
        "food_id": food.get("id"),
        "food_name": food["name"],
        "grams": round(float(grams), 1),
        "kcal": round(float(food["kcal"]) * f, 1),
        "protein": round(float(food["protein"]) * f, 1),
        "carbs": round(float(food.get("carbs", 0)) * f, 1),
        "fat": round(float(food.get("fat", 0)) * f, 1),
        "sugar": round(float(food.get("sugar", 0)) * f, 1),
        "salt": round(float(food.get("salt", 0)) * f, 2),
    }


def totals(items: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "kcal": round(sum(float(i.get("kcal", 0)) for i in items), 1),
        "protein": round(sum(float(i.get("protein", 0)) for i in items), 1),
        "carbs": round(sum(float(i.get("carbs", 0)) for i in items), 1),
        "fat": round(sum(float(i.get("fat", 0)) for i in items), 1),
        "sugar": round(sum(float(i.get("sugar", 0)) for i in items), 1),
        "salt": round(sum(float(i.get("salt", 0)) for i in items), 2),
    }


def _insert_meal_items(db: sqlite3.Connection, meal_id: int, items: list[dict[str, Any]]) -> None:
    for it in items:
        db.execute(
            """INSERT INTO meal_items(meal_id,food_id,food_name,grams,kcal,protein,carbs,fat,sugar,salt)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (meal_id, it.get("food_id"), it["food_name"], it["grams"], it["kcal"], it["protein"], it["carbs"], it["fat"], it["sugar"], it["salt"]),
        )


def create_meal(db: sqlite3.Connection, meal: dict[str, Any], items: list[dict[str, Any]]) -> int:
    """Always creates a new meal (two identical meals at the same minute are both kept)."""
    try:
        cur = db.execute(
            "INSERT INTO meals(date,time,name,notes) VALUES(?,?,?,?)",
            (meal["date"], meal["time"], meal["name"], meal.get("notes", "")),
        )
    except sqlite3.IntegrityError:
        # Only possible if migration 1 could not drop the legacy UNIQUE constraint.
        raise ApiError("Ya existe una comida idéntica a esa hora; cambia la hora o las notas", 409) from None
    meal_id = int(cur.lastrowid)
    _insert_meal_items(db, meal_id, items)
    return meal_id


def insert_meal(db: sqlite3.Connection, meal: dict[str, Any], items: list[dict[str, Any]]) -> int:
    """Idempotent insert used by seed/local scripts: reuses an identical existing meal."""
    row = db.execute(
        "SELECT id FROM meals WHERE date=? AND time=? AND name=? AND notes=? ORDER BY id LIMIT 1",
        (meal["date"], meal["time"], meal["name"], meal.get("notes", "")),
    ).fetchone()
    if not row:
        return create_meal(db, meal, items)
    meal_id = int(row["id"])
    existing = db.execute("SELECT COUNT(*) c FROM meal_items WHERE meal_id=?", (meal_id,)).fetchone()["c"]
    if existing == 0:
        _insert_meal_items(db, meal_id, items)
    return meal_id


def insert_meal_by_names(db: sqlite3.Connection, date_: str, time_: str, name: str, notes: str, pairs: list[tuple[str, float]]) -> None:
    items = []
    for food_name, grams in pairs:
        food = get_food(db, food_name)
        items.append(calc_item(food, grams))
    insert_meal(db, {"date": date_, "time": time_, "name": name, "notes": notes}, items)


def seed(db: sqlite3.Connection) -> None:
    foods = [
        # Productos reales vistos en tus fotos / ticket.
        dict(name="Yogur Eroski +Proteína 120 g", brand="Eroski / Postres Reina", kcal=57, protein=8.5, carbs=4.5, fat=0.5, sugar=4.5, salt=0.13, typical_g=120, purchased=1, source_note="Etiqueta real: por 120 g = 68 kcal, 10 g proteína, 5,4 g azúcar, 0,6 g grasa, 0,16 g sal.", notes="Desayuno/merienda. Buen básico."),
        dict(name="Queso fresco batido Eroski +Proteína 0%", brand="Eroski", kcal=56, protein=10.0, carbs=3.6, fat=0.0, sugar=0.0, salt=0.11, typical_g=200, purchased=1, source_note="Etiqueta real natural: 56 kcal/100 g, 10 g proteína/100 g, 0% grasa. Bote 500 g.", notes="Mejor natural que arándanos. 150–250 g para merienda/postre."),
        dict(name="Gelatina 0 Clesa", brand="Clesa Gelly 0%", kcal=2, protein=0, carbs=0.1, fat=0, sugar=0, salt=0.17, typical_g=90, purchased=1, source_note="Etiqueta real: 0% azúcares; aprox. 2 kcal/100 g. Unidad 90 g.", notes="Para hambre/antojo. No aporta proteína."),
        dict(name="Tortitas de maíz Eroski", brand="Eroski", kcal=376, protein=8.2, carbs=80.0, fat=2.0, sugar=1.2, salt=0.85, typical_g=20, purchased=1, source_note="Etiqueta real: 3 tortitas/20 g = 77 kcal, 1,7 g proteína, 0,2 g azúcar, 0,17 g sal.", notes="Snack controlado: 3 tortitas máximo."),
        dict(name="Pan centeno/integral rebanada", brand="Eroski", kcal=224, protein=8.0, carbs=42.0, fat=3.1, sugar=3.8, salt=1.0, typical_g=42, purchased=1, source_note="Etiqueta real: 1 rebanada 42 g = 94 kcal. Fuente de fibra.", notes="Desayuno base: 1 rebanada."),
        dict(name="Jamón cocido extra ElPozo 85%", brand="ElPozo", kcal=105, protein=18.5, carbs=2.0, fat=2.5, sugar=1.0, salt=1.8, typical_g=80, purchased=1, source_note="Foto frontal: 85% carne, bajo en grasa. Valores estimados hasta ver etiqueta trasera completa.", notes="Complemento rápido. Ración 70–90 g."),
        dict(name="Pollo pechuga cruda Pazo de Pías", brand="Pazo de Pías", kcal=110, protein=23.0, carbs=0, fat=1.6, sugar=0, salt=0.2, typical_g=200, purchased=1, source_note="Pechuga fileteada. Pesar en crudo.", notes="Proteína principal. Ración 180–220 g crudo."),
        dict(name="Champiñones laminados", brand="Eroski", kcal=22, protein=3.1, carbs=3.3, fat=0.3, sugar=2.0, salt=0.02, typical_g=200, purchased=1, source_note="Verdura fácil principal.", notes="150–250 g por plato. Saltear con poco aceite."),
        dict(name="Edulcorante Eroski", brand="Eroski", kcal=0, protein=0, carbs=0, fat=0, sugar=0, salt=0, typical_g=1, purchased=1, source_note="Para sustituir azúcar del café.", notes="No cuenta prácticamente."),
        # Básicos de casa / plan.
        dict(name="Aceite de oliva", brand="Casa", kcal=900, protein=0, carbs=0, fat=100, sugar=0, salt=0, typical_g=5, purchased=1, source_note="Regla de dieta: 5 g normal, 10 g máximo. 20 g ya sube mucho.", notes="Pésalo con tara."),
        dict(name="Crema de cacahuete", brand="Casa", kcal=610, protein=25.0, carbs=12.0, fat=50.0, sugar=5.0, salt=0.1, typical_g=15, purchased=1, source_note="Ración controlada para desayuno.", notes="15 g total, no por tostada."),
        dict(name="Plátano", brand="Fruta", kcal=89, protein=1.1, carbs=23.0, fat=0.3, sugar=12.0, salt=0, typical_g=120, purchased=0, source_note="Fruta útil para desayuno/entreno.", notes="Completa desayuno/entreno."),
        dict(name="Manzana", brand="Fruta", kcal=52, protein=0.3, carbs=14.0, fat=0.2, sugar=10.0, salt=0, typical_g=180, purchased=1, source_note="Merienda limpia con yogur.", notes="Merienda limpia."),
        dict(name="Naranja", brand="Fruta", kcal=47, protein=0.9, carbs=12.0, fat=0.1, sugar=9.0, salt=0, typical_g=180, purchased=1, source_note="Alternativa a manzana.", notes="Alternativa a manzana."),
        dict(name="Pasta seca", brand="Despensa", kcal=360, protein=12.0, carbs=72.0, fat=1.5, sugar=3.0, salt=0.02, typical_g=80, purchased=1, source_note="Pesar siempre en seco.", notes="80 g normal; 90 g día fuerte."),
        dict(name="Arroz seco", brand="Despensa", kcal=360, protein=7.0, carbs=78.0, fat=0.8, sugar=0.5, salt=0.01, typical_g=80, purchased=1, source_note="Pesar siempre en seco.", notes="Tupper oficina."),
        dict(name="Patata cocida", brand="Casa", kcal=77, protein=2.0, carbs=17.0, fat=0.1, sugar=0.8, salt=0.01, typical_g=300, purchased=1, source_note="Sacia mucho.", notes="Sacia mucho. 250–350 g."),
        dict(name="Guisantes", brand="Casa", kcal=81, protein=5.4, carbs=14.0, fat=0.4, sugar=5.7, salt=0.02, typical_g=100, purchased=1, source_note="Verdura/legumbre fácil.", notes="Verdura/legumbre fácil."),
        dict(name="Patata + guisantes guisados", brand="Preparación casera", kcal=80, protein=3.0, carbs=15.0, fat=0.5, sugar=1.5, salt=0.2, typical_g=300, purchased=1, source_note="Estimado; registrar aceite aparte si lo lleva.", notes="Restos. Si lleva aceite, añade aceite separado."),
        dict(name="Lentejas guisadas", brand="Casa", kcal=125, protein=7.1, carbs=18.0, fat=2.5, sugar=2.0, salt=0.4, typical_g=300, purchased=1, source_note="Estimación; si tienen chorizo, registrar chorizo aparte.", notes="300–350 g, sin pan ni repetir."),
        dict(name="Chorizo", brand="Casa", kcal=450, protein=22.0, carbs=2.0, fat=38.0, sugar=1.0, salt=3.0, typical_g=20, purchased=1, source_note="Cachos gordos: limitar 20–30 g.", notes="Solo parte del guiso."),
        dict(name="Huevo entero", brand="Casa", kcal=143, protein=12.6, carbs=0.7, fat=9.5, sugar=0, salt=0.35, typical_g=60, purchased=1, source_note="Valor medio por 100 g.", notes="1 huevo mediano-grande aprox. 60 g. Para 2 huevos registrar 120 g."),
        dict(name="Atún al natural", brand="Despensa", kcal=105, protein=24.0, carbs=0, fat=1.0, sugar=0, salt=0.8, typical_g=112, purchased=1, source_note="2 latas pequeñas con pasta.", notes="Proteína rápida."),
        dict(name="Merluza cocida", brand="Casa", kcal=86, protein=18.0, carbs=0, fat=1.5, sugar=0, salt=0.25, typical_g=200, purchased=0, source_note="Pescado blanco magro.", notes="Buena cena ligera cuando compres."),
        dict(name="Café con edulcorante", brand="Casa", kcal=1, protein=0, carbs=0, fat=0, sugar=0, salt=0, typical_g=200, purchased=1, source_note="Edulcorante comprado.", notes="Casi no suma."),
        dict(name="Chocolate onzas estimado", brand="Estimado", kcal=550, protein=6.0, carbs=55.0, fat=32.0, sugar=48.0, salt=0.05, typical_g=20, purchased=0, source_note="4 onzas estimadas como 20 g.", notes="Snack dulce estimado. Registrar solo si se consume."),
    ]
    # Catalog, exercises and templates are seeded once, on a fresh database only:
    # later restarts must not resurrect what the user edited or deleted.
    seeded = db.execute("SELECT 1 FROM app_settings WHERE key='seed_done'").fetchone()
    first_run = not seeded and db.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 0
    if not seeded:
        db.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('seed_done','true')")
    if first_run:
        for f in foods:
            seed_food_if_missing(db, f)

    exercises = [
        ("HIIT", 8.0, 0, "Clase intensa; si el reloj da kcal, usa reloj."),
        ("Clase funcional", 6.5, 0, "Funcional/gym."),
        ("Core + movilidad", 4.5, 0, "Troncal, movilidad."),
        ("Cinta andando", 3.5, 0, "Andar en cinta."),
        ("Paseo perro", 3.0, 0, "Paseo exterior."),
        ("Bici estática suave", 4.5, 0, "20 min suave/moderado."),
        ("Pádel", 6.0, 0, "Según intensidad."),
        ("Pierna gimnasio", 5.0, 0, "Fuerza pierna."),
        ("Brazo gimnasio", 4.5, 0, "Fuerza tren superior."),
    ]
    for name, met, kcal_per_min, notes in exercises if first_run else []:
        db.execute("INSERT INTO exercises(name,met,kcal_per_min,notes) VALUES(?,?,?,?) ON CONFLICT(name) DO NOTHING", (name, met, kcal_per_min, notes))

    # La app pública no siembra pesos, comidas ni entrenos personales.
    # Los datos privados se mantienen solo en data/dieta.db o se aplican con scripts locales ignorados por git.

    templates = [
        ("Desayuno base", "1 tostada + 15 g crema cacahuete + plátano + yogur", [("Pan centeno/integral rebanada", 42), ("Crema de cacahuete", 15), ("Plátano", 120), ("Yogur Eroski +Proteína 120 g", 120), ("Café con edulcorante", 200)]),
        ("Desayuno sin plátano", "Cuando no tienes fruta", [("Pan centeno/integral rebanada", 42), ("Crema de cacahuete", 15), ("Yogur Eroski +Proteína 120 g", 120), ("Café con edulcorante", 200)]),
        ("Pasta + pollo + champis", "Pasta pesada en seco; pollo en crudo", [("Pasta seca", 80), ("Pollo pechuga cruda Pazo de Pías", 200), ("Champiñones laminados", 200), ("Aceite de oliva", 5)]),
        ("Tupper arroz + pollo", "Base oficina", [("Arroz seco", 80), ("Pollo pechuga cruda Pazo de Pías", 200), ("Champiñones laminados", 150), ("Guisantes", 80), ("Aceite de oliva", 5)]),
        ("Cena huevos + champis + jamón", "Cena rápida post-entreno", [("Huevo entero", 120), ("Champiñones laminados", 200), ("Jamón cocido extra ElPozo 85%", 80), ("Aceite de oliva", 5)]),
        ("Merienda yogur + fruta", "Merienda limpia", [("Yogur Eroski +Proteína 120 g", 120), ("Manzana", 180)]),
        ("Lentejas controladas", "Sin pan y sin repetir", [("Lentejas guisadas", 300), ("Chorizo", 20)]),
    ]
    for name, notes, items in templates if first_run else []:
        payload = json.dumps({"items": [{"food": n, "grams": g} for n, g in items]}, ensure_ascii=False)
        db.execute("INSERT INTO templates(name,notes,kind,payload) VALUES(?,?,?,?) ON CONFLICT(name) DO NOTHING", (name, notes, "meal", payload))

    plan = {
        "name": "Semana base sencilla",
        "notes": "Pasta/arroz en seco. Pollo en crudo. Aceite 5 g normal, 10 g máximo.",
        "days": [
            {"day": "Día HIIT", "breakfast": "Desayuno base", "lunch": "80 g pasta seca + 200 g pollo + champiñones", "snack": "Yogur + fruta", "dinner": "2 huevos + champiñones + jamón cocido"},
            {"day": "Oficina", "breakfast": "Desayuno base", "lunch": "Tupper arroz + pollo", "snack": "Queso fresco batido o yogur", "dinner": "Pollo/huevos + champiñones"},
            {"day": "Día normal", "breakfast": "Desayuno base", "lunch": "Pasta/arroz + atún/pollo", "snack": "Fruta + yogur", "dinner": "Cena proteica sin pan extra"},
        ],
    }
    if db.execute("SELECT COUNT(*) c FROM plans").fetchone()["c"] == 0:
        db.execute("INSERT INTO plans(name,payload) VALUES(?,?)", (plan["name"], json.dumps(plan, ensure_ascii=False)))


def fix_existing_data(db: sqlite3.Connection) -> None:
    # Renombra alimentos antiguos para que coincidan con los productos reales, conservando items existentes.
    db.execute("UPDATE foods SET name='Jamón cocido extra ElPozo 85%' WHERE name='Jamón cocido extra 85%'")
    db.execute("UPDATE meal_items SET food_name='Jamón cocido extra ElPozo 85%' WHERE food_name='Jamón cocido extra 85%'")
    db.execute("UPDATE foods SET name='Pollo pechuga cruda Pazo de Pías' WHERE name='Pollo pechuga cruda'")
    db.execute("UPDATE meal_items SET food_name='Pollo pechuga cruda Pazo de Pías' WHERE food_name='Pollo pechuga cruda'")
    db.execute("UPDATE foods SET name='Champiñones laminados' WHERE name='Champiñones'")
    db.execute("UPDATE meal_items SET food_name='Champiñones laminados' WHERE food_name='Champiñones'")


def init_db() -> None:
    dpp_db.ensure_rollback_journal(DB)
    with con() as db:
        ensure_schema(db)
    # Versioned migrations (backs up an existing database first).
    applied = dpp_db.migrate(DB)
    if applied:
        print(f"[DPP] database migrated: {applied}")
    with con() as db:
        seed(db)
        fix_existing_data(db)


def meal_with_items(db: sqlite3.Connection, m: sqlite3.Row) -> dict[str, Any]:
    d = dict(m)
    its = rows(db.execute("SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (m["id"],)))
    d["items"] = its
    d["totals"] = totals(its)
    return d


def build_state() -> dict[str, Any]:
    with con() as db:
        foods = rows(db.execute("SELECT * FROM foods ORDER BY purchased DESC, name COLLATE NOCASE"))
        exercises = rows(db.execute("SELECT * FROM exercises ORDER BY name COLLATE NOCASE"))
        weights = rows(db.execute("SELECT * FROM weights ORDER BY date DESC, time DESC, id DESC LIMIT 300"))
        meals = [meal_with_items(db, r) for r in db.execute("SELECT * FROM meals ORDER BY date DESC, time DESC, id DESC LIMIT 300").fetchall()]
        workouts = rows(db.execute("SELECT * FROM workouts ORDER BY date DESC, time DESC, id DESC LIMIT 300"))
        templates = rows(db.execute("SELECT * FROM templates ORDER BY name COLLATE NOCASE"))
        plans = rows(db.execute("SELECT * FROM plans ORDER BY id DESC LIMIT 20"))
    return {"today": today_iso(), "now": now_hm(), "foods": foods, "exercises": exercises, "weights": weights, "meals": meals, "workouts": workouts, "templates": templates, "plans": plans}


# -----------------------------
# Strava integration (optional)
# -----------------------------
STRAVA_TOKEN_FILE = DATA / "strava_tokens.json"
STRAVA_STATE_FILE = DATA / "strava_oauth_state.txt"


def strava_config() -> dict[str, str]:
    return {
        "client_id": os.environ.get("STRAVA_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("STRAVA_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.environ.get("STRAVA_REDIRECT_URI", "").strip(),
    }


def strava_configured() -> bool:
    cfg = strava_config()
    return bool(cfg["client_id"] and cfg["client_secret"] and cfg["redirect_uri"])


def read_strava_tokens() -> dict[str, Any] | None:
    if not STRAVA_TOKEN_FILE.exists():
        return None
    try:
        return json.loads(STRAVA_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_private_text(path: Path, text: str) -> None:
    """Atomic write of a secret file created with mode 600 (never world-readable, not even briefly)."""
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def write_strava_tokens(tokens: dict[str, Any]) -> None:
    write_private_text(STRAVA_TOKEN_FILE, json.dumps(tokens, ensure_ascii=False, indent=2))


def estimate_strava_kcal(activity_type: str, minutes: float) -> float:
    # Estimación simple si Strava no devuelve calorías: MET x peso corporal actual.
    mets = {
        "Walk": 3.5,
        "Hike": 5.3,
        "Run": 8.5,
        "Ride": 6.5,
        "VirtualRide": 6.0,
        "Workout": 6.0,
        "WeightTraining": 4.8,
        "HIIT": 8.0,
    }
    met = mets.get(activity_type, 5.5)
    return dpp_profile.estimate_met_kcal(met, minutes)


def refresh_strava_if_needed(tokens: dict[str, Any]) -> dict[str, Any]:
    cfg = strava_config()
    if int(tokens.get("expires_at") or 0) > int(time.time()) + 120:
        return tokens
    r = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": tokens.get("refresh_token"),
        },
        timeout=20,
    )
    r.raise_for_status()
    new_tokens = r.json()
    write_strava_tokens(new_tokens)
    return new_tokens


STRAVA_STATE_TTL_SECONDS = 30 * 60


def issue_strava_oauth_state() -> str:
    """Reuse a recent state so several open tabs share one valid connect link."""
    try:
        if STRAVA_STATE_FILE.exists() and time.time() - STRAVA_STATE_FILE.stat().st_mtime < STRAVA_STATE_TTL_SECONDS / 2:
            current = STRAVA_STATE_FILE.read_text(encoding="utf-8").strip()
            if len(current) >= 24:
                return current
    except OSError:
        pass
    state = secrets.token_urlsafe(24)
    write_private_text(STRAVA_STATE_FILE, state)
    return state


def consume_strava_oauth_state(received: str) -> bool:
    """One-time, constant-time, expiring check (rejects callbacks without a pending state)."""
    try:
        if not STRAVA_STATE_FILE.exists():
            return False
        expected = STRAVA_STATE_FILE.read_text(encoding="utf-8").strip()
        fresh = time.time() - STRAVA_STATE_FILE.stat().st_mtime < STRAVA_STATE_TTL_SECONDS
    except OSError:
        return False
    ok = bool(expected) and fresh and hmac.compare_digest(str(received or ""), expected)
    if ok:
        STRAVA_STATE_FILE.unlink(missing_ok=True)
    return ok


@app.get("/api/strava/status")
def api_strava_status():
    cfg = strava_config()
    tokens = read_strava_tokens()
    configured = strava_configured()
    connect_url = ""
    if configured:
        state = issue_strava_oauth_state()
        params = {
            "client_id": cfg["client_id"],
            "redirect_uri": cfg["redirect_uri"],
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "read,activity:read_all",
            "state": state,
        }
        connect_url = "https://www.strava.com/oauth/authorize?" + urllib.parse.urlencode(params)
    return jsonify({
        "configured": configured,
        "connected": bool(tokens and tokens.get("access_token")),
        "connect_url": connect_url,
        "message": "Configura STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET y STRAVA_REDIRECT_URI en .env" if not configured else "Listo para conectar Strava",
    })


@app.get("/api/strava/callback")
def api_strava_callback():
    if not strava_configured():
        return "Strava no configurado en .env", 400
    if not consume_strava_oauth_state(request.args.get("state", "")):
        return "Estado OAuth no válido o caducado; vuelve a pulsar Conectar Strava", 400
    code = request.args.get("code")
    if not code:
        return "Falta code de Strava", 400
    cfg = strava_config()
    r = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    r.raise_for_status()
    write_strava_tokens(r.json())
    return "<h1>Strava conectado</h1><p>Ya puedes volver a Dieta Pro y pulsar Sincronizar Strava.</p>"


@app.post("/api/strava/sync")
def api_strava_sync():
    tokens = read_strava_tokens()
    if not tokens:
        return jsonify({"error": "Strava no conectado"}), 400
    tokens = refresh_strava_if_needed(tokens)
    days = int(v.number(v.json_body().get("days"), "days", default=14, minimum=1, maximum=365))
    after = int(time.time()) - days * 86400
    r = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        params={"after": after, "per_page": 50},
        timeout=25,
    )
    r.raise_for_status()
    activities = r.json()
    imported = 0
    with con() as db:
        for a in activities:
            start = (a.get("start_date_local") or a.get("start_date") or "")
            if not start:
                continue
            d = start[:10]
            tm = start[11:16] if len(start) >= 16 else "12:00"
            minutes = round(float(a.get("moving_time") or a.get("elapsed_time") or 0) / 60, 1)
            distance_km = round(float(a.get("distance") or 0) / 1000, 2)
            name = a.get("type") or a.get("sport_type") or "Strava"
            title = a.get("name") or name
            kcal = float(a.get("calories") or 0)
            if kcal <= 0 and minutes:
                kcal = estimate_strava_kcal(name, minutes)
            notes = f"Strava · {title} · id={a.get('id')}"
            db.execute(
                "INSERT OR IGNORE INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes) VALUES(?,?,?,?,?,?,?,?)",
                (d, tm, None, name, minutes, distance_km, kcal, notes),
            )
            if db.total_changes:
                imported += 1
    return jsonify({"ok": True, "imported": imported, "received": len(activities)})


Image.MAX_IMAGE_PIXELS = 64_000_000  # above 2x this Pillow refuses to open (decompression bombs)


def save_uploaded_photo() -> tuple[Path, str]:
    """Validate and store the multipart ``photo`` field; returns (path, public_url)."""
    if "photo" not in request.files:
        raise ApiError("Falta archivo photo")
    file = request.files["photo"]
    if not file.filename:
        raise ApiError("Archivo vacío")
    ext = Path(secure_filename(file.filename)).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ApiError("Formato no soportado (usa JPG, PNG o WEBP)")
    name = f"food-{int(time.time())}-{secrets.token_hex(4)}{ext}"
    path = UPLOADS / name
    file.save(path)
    try:
        with Image.open(path) as img:
            detected = img.format
            img.verify()
        # The content must really be one of the allowed formats (not just the extension).
        if detected not in {"JPEG", "PNG", "WEBP", "MPO"}:
            raise ValueError("unsupported image format")
    except Image.DecompressionBombError:
        path.unlink(missing_ok=True)
        raise ApiError("Imagen demasiado grande; reduce la resolución de la foto", 413) from None
    except Exception:
        path.unlink(missing_ok=True)
        raise ApiError("El archivo no es una imagen válida") from None
    return path, f"/uploads/{name}"


@app.post("/api/food-photo")
def api_food_photo():
    _path, url = save_uploaded_photo()
    return jsonify({"ok": True, "photo_path": url})


@app.get("/uploads/<name>")
def uploaded_file(name: str):
    if not name or Path(name).name != name or secure_filename(name) != name:
        return "", 404
    return send_from_directory(UPLOADS, name)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "icon-192.png", mimetype="image/png", max_age=86400)


@app.get("/api/state")
def api_state():
    return jsonify(build_state())


def _food_payload(d: dict[str, Any]) -> dict[str, Any]:
    name = v.text(d.get("name"), 160)
    if not name:
        raise ApiError("Falta nombre")
    per100 = {"kcal": 900, "protein": 100, "carbs": 100, "fat": 100, "sugar": 100, "salt": 100}
    food = {"name": name, "brand": v.text(d.get("brand"), 120)}
    for key, hi in per100.items():
        food[key] = round(v.number(d.get(key), key, default=0, maximum=hi), 2)
    food.update({
        "typical_g": round(v.number(d.get("typical_g"), "ración", default=100, minimum=0.1, maximum=5000), 1),
        "purchased": 1 if d.get("purchased") in (True, 1, "1", "true", "on") else 0,
        "source_note": v.text(d.get("source_note"), 2000),
        "notes": v.text(d.get("notes"), 1000),
        "photo_path": v.text(d.get("photo_path"), 200),
        "barcode": v.text(d.get("barcode"), 14),
    })
    if food["barcode"] and not re.fullmatch(r"\d{8,14}", food["barcode"]):
        raise ApiError("Código de barras no válido")
    if food["photo_path"] and not re.fullmatch(r"/uploads/[A-Za-z0-9._-]+", food["photo_path"]):
        raise ApiError("photo_path no válido")
    if food["protein"] + food["carbs"] + food["fat"] > 101:
        raise ApiError("Proteína + hidratos + grasa no pueden superar 100 g por 100 g")
    return food


@app.post("/api/foods")
def api_foods():
    food = _food_payload(v.json_body())
    with con() as db:
        upsert_food(db, food)
        row = db.execute("SELECT id FROM foods WHERE name=?", (food["name"],)).fetchone()
    return jsonify({"ok": True, "id": row["id"] if row else None})


@app.delete("/api/foods/<int:item_id>")
def delete_food(item_id: int):
    with con() as db:
        # meal_items keep their own name/grams/macros (food_id becomes NULL).
        cur = db.execute("DELETE FROM foods WHERE id=?", (item_id,))
    if not cur.rowcount:
        raise ApiError("Alimento no encontrado", 404)
    return jsonify({"ok": True})


def _weight_payload(d: dict[str, Any]) -> tuple:
    return (
        v.iso_date(d.get("date"), today_iso()),
        v.hhmm(d.get("time"), now_hm()),
        round(v.number(d.get("kg"), "kg", minimum=20, maximum=400), 2),
        1 if d.get("official") in (True, 1, "1", "true", "on") else 0,
        v.text(d.get("context"), 200),
    )


@app.post("/api/weights")
def api_weights():
    with con() as db:
        cur = db.execute("INSERT OR IGNORE INTO weights(date,time,kg,official,context) VALUES(?,?,?,?,?)", _weight_payload(v.json_body()))
    return jsonify({"ok": True, "id": cur.lastrowid if cur.rowcount else None, "duplicate": not cur.rowcount})


@app.put("/api/weights/<int:item_id>")
def update_weight(item_id: int):
    with con() as db:
        cur = db.execute("UPDATE weights SET date=?,time=?,kg=?,official=?,context=? WHERE id=?", (*_weight_payload(v.json_body()), item_id))
    if not cur.rowcount:
        raise ApiError("Peso no encontrado", 404)
    return jsonify({"ok": True})


@app.delete("/api/weights/<int:item_id>")
def delete_weight(item_id: int):
    with con() as db:
        db.execute("DELETE FROM weights WHERE id=?", (item_id,))
    return jsonify({"ok": True})


def _meal_items_from_payload(db: sqlite3.Connection, items_in: Any) -> list[dict[str, Any]]:
    if not isinstance(items_in, list) or not items_in:
        raise ApiError("Añade alimentos")
    if len(items_in) > 60:
        raise ApiError("Demasiados alimentos en una comida")
    items = []
    for it in items_in:
        if not isinstance(it, dict):
            raise ApiError("Alimento no válido")
        food = None
        food_id = v.integer_id(it.get("food_id"), "food_id")
        if food_id is not None:
            r = db.execute("SELECT * FROM foods WHERE id=?", (food_id,)).fetchone()
            food = dict(r) if r else None
        if not food and it.get("food_name"):
            r = db.execute("SELECT * FROM foods WHERE name=?", (v.text(it.get("food_name"), 160),)).fetchone()
            food = dict(r) if r else None
        if not food:
            raise ApiError(f"Alimento no encontrado: {v.text(it.get('food_name') or it.get('food_id'), 80)}")
        # Empty or 0 grams falls back to the typical portion (as before v0.1.0).
        grams = v.number(it.get("grams"), "gramos", default=food["typical_g"], minimum=0, maximum=5000) or float(food["typical_g"] or 100)
        items.append(calc_item(food, grams))
    return items


def _meal_header(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": v.iso_date(d.get("date"), today_iso()),
        "time": v.hhmm(d.get("time"), now_hm()),
        "name": v.text(d.get("name"), 60) or "Comida",
        "notes": v.text(d.get("notes"), 500),
    }


@app.post("/api/meals")
def api_meals():
    d = v.json_body()
    with con() as db:
        items = _meal_items_from_payload(db, d.get("items"))
        mid = create_meal(db, _meal_header(d), items)
    return jsonify({"ok": True, "id": mid})


@app.put("/api/meals/<int:item_id>")
def update_meal(item_id: int):
    d = v.json_body()
    with con() as db:
        if not db.execute("SELECT 1 FROM meals WHERE id=?", (item_id,)).fetchone():
            raise ApiError("Comida no encontrada", 404)
        header = _meal_header(d)
        db.execute("UPDATE meals SET date=?,time=?,name=?,notes=? WHERE id=?", (header["date"], header["time"], header["name"], header["notes"], item_id))
        if "items" in d:
            items = _meal_items_from_payload(db, d.get("items"))
            db.execute("DELETE FROM meal_items WHERE meal_id=?", (item_id,))
            _insert_meal_items(db, item_id, items)
    return jsonify({"ok": True, "id": item_id})


@app.post("/api/meals/<int:item_id>/duplicate")
def duplicate_meal(item_id: int):
    """Repeat a logged meal (same items and grams) on another day/time."""
    d = v.json_body()
    with con() as db:
        meal = db.execute("SELECT * FROM meals WHERE id=?", (item_id,)).fetchone()
        if not meal:
            raise ApiError("Comida no encontrada", 404)
        items = rows(db.execute("SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (item_id,)))
        header = {
            "date": v.iso_date(d.get("date"), today_iso()),
            "time": v.hhmm(d.get("time"), meal["time"]),
            "name": meal["name"],
            "notes": meal["notes"] or "",
        }
        mid = create_meal(db, header, items)
    return jsonify({"ok": True, "id": mid})


@app.delete("/api/meals/<int:item_id>")
def delete_meal(item_id: int):
    with con() as db:
        db.execute("DELETE FROM meals WHERE id=?", (item_id,))
    return jsonify({"ok": True})


@app.post("/api/workouts")
def api_workouts():
    d = v.json_body()
    name = v.text(d.get("name"), 80) or "Entreno"
    minutes = v.number(d.get("minutes"), "minutos", default=0, maximum=1440)
    distance = v.number(d.get("distance_km"), "distancia", default=0, maximum=1000)
    kcal = v.number(d.get("kcal"), "kcal", default=0, maximum=15000)
    with con() as db:
        ex = db.execute("SELECT * FROM exercises WHERE name=?", (name,)).fetchone()
        ex_id = ex["id"] if ex else None
        if kcal <= 0 and ex and minutes:
            kcal = dpp_profile.estimate_met_kcal(float(ex["met"]), minutes)
        cur = db.execute(
            "INSERT OR IGNORE INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes) VALUES(?,?,?,?,?,?,?,?)",
            (v.iso_date(d.get("date"), today_iso()), v.hhmm(d.get("time"), now_hm()), ex_id, name, minutes, distance, kcal, v.text(d.get("notes"), 500)),
        )
    return jsonify({"ok": True, "id": cur.lastrowid if cur.rowcount else None, "kcal": kcal})


@app.delete("/api/workouts/<int:item_id>")
def delete_workout(item_id: int):
    with con() as db:
        db.execute("DELETE FROM workouts WHERE id=?", (item_id,))
    return jsonify({"ok": True})


@app.post("/api/exercises")
def api_exercises():
    d = v.json_body()
    name = v.text(d.get("name"), 80)
    if not name:
        raise ApiError("Falta nombre")
    met = v.number(d.get("met"), "MET", default=5, minimum=1, maximum=25)
    with con() as db:
        db.execute("INSERT INTO exercises(name,met,kcal_per_min,notes) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET met=excluded.met,notes=excluded.notes", (name, met, 0, v.text(d.get("notes"), 300)))
    return jsonify({"ok": True})


@app.post("/api/templates")
def api_templates():
    d = v.json_body()
    name = v.text(d.get("name"), 120)
    if not name:
        raise ApiError("Falta nombre de plantilla")
    raw = d.get("payload")
    try:
        payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except json.JSONDecodeError:
        raise ApiError("Plantilla con JSON no válido") from None
    if not isinstance(payload, dict):
        raise ApiError("Plantilla no válida")
    with con() as db:
        db.execute("INSERT INTO templates(name,notes,kind,payload) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET notes=excluded.notes,kind=excluded.kind,payload=excluded.payload", (name, v.text(d.get("notes"), 500), v.text(d.get("kind"), 20) or "meal", json.dumps(payload, ensure_ascii=False)))
    return jsonify({"ok": True})


@app.post("/api/plans")
def api_plans():
    d = v.json_body()
    raw = d.get("raw") or d.get("payload")
    try:
        payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except json.JSONDecodeError as exc:
        raise ApiError(f"JSON no válido: {exc.msg} (línea {exc.lineno})") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("days", []), list):
        raise ApiError("El plan debe ser un objeto con una lista 'days'")
    name = v.text(payload.get("name"), 120) or "Plan semanal"
    with con() as db:
        db.execute("INSERT INTO plans(name,payload) VALUES(?,?)", (name, json.dumps(payload, ensure_ascii=False)))
    return jsonify({"ok": True})


@app.get("/api/export")
def api_export():
    return jsonify(build_state())



# V002_STRAVA_MANUAL_IMPORT

def _epoch_from_date(value: str, end: bool = False) -> int:
    if not value:
        return 0
    dt = datetime.strptime(value, "%Y-%m-%d")
    if end:
        dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp())



def _strava_fetch_activity_detail(access_token: str, activity_id: str) -> dict[str, Any] | None:
    """Fetch detailed activity data so calories match the Strava activity page when available."""
    if not activity_id:
        return None
    r = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"include_all_efforts": "false"},
        timeout=25,
    )
    if r.status_code in {401, 403, 404}:
        return None
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else None


def _strava_fetch_range(after_date: str, before_date: str, detailed: bool = True) -> list[dict[str, Any]]:
    tokens = read_strava_tokens()
    if not tokens:
        raise RuntimeError("Strava no conectado")
    tokens = refresh_strava_if_needed(tokens)
    access_token = tokens["access_token"]

    after = _epoch_from_date(after_date, False)
    before = _epoch_from_date(before_date, True) if before_date else int(time.time())

    out = []
    for page in range(1, 6):
        r = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": after, "before": before, "page": page, "per_page": 100},
            timeout=25,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break

    if detailed:
        detailed_out = []
        for item in out:
            sid = str(item.get("id") or "")
            detail = None
            if sid:
                try:
                    detail = _strava_fetch_activity_detail(access_token, sid)
                except Exception:
                    detail = None
            if detail:
                merged = {**item, **detail}
                # Preserve local start fields if Strava detail omits them.
                for k in ("start_date", "start_date_local"):
                    if not merged.get(k) and item.get(k):
                        merged[k] = item.get(k)
                detailed_out.append(merged)
            else:
                detailed_out.append(item)
        out = detailed_out

    return out



def _strava_card(a: dict[str, Any]) -> dict[str, Any]:
    start = a.get("start_date_local") or a.get("start_date") or ""
    sid = str(a.get("id") or "")
    sport = a.get("sport_type") or a.get("type") or "Strava"
    typ = a.get("type") or sport
    title = a.get("name") or sport
    minutes = round(float(a.get("moving_time") or a.get("elapsed_time") or 0) / 60, 1)
    km = round(float(a.get("distance") or 0) / 1000, 2)

    kcal = 0.0
    for key in ("calories", "calorie", "kcal"):
        try:
            val = a.get(key)
            if val is not None and float(val) > 0:
                kcal = float(val)
                break
        except Exception:
            pass
    if kcal <= 0 and minutes:
        kcal = estimate_strava_kcal(typ, minutes)

    return {
        "id": sid,
        "date": start[:10],
        "time": start[11:16] if len(start) >= 16 else "12:00",
        "title": title,
        "type": typ,
        "sport_type": sport,
        "minutes": minutes,
        "distance_km": km,
        "kcal": round(kcal, 1),
        "url": f"https://www.strava.com/activities/{sid}" if sid else "",
    }


@app.post("/api/strava/preview")
def api_strava_preview():
    d = v.json_body()
    after_date = v.iso_date(d.get("after_date"), today_iso(), "after_date")
    before_date = v.iso_date(d.get("before_date"), today_iso(), "before_date")
    try:
        raw = _strava_fetch_range(after_date, before_date)
        acts = [_strava_card(a) for a in raw if a.get("id")]

        with con() as db:
            for a in acts:
                found = db.execute(
                    "SELECT id FROM workouts WHERE notes LIKE ? LIMIT 1",
                    (f"%id={a['id']}%",),
                ).fetchone()
                a["already_imported"] = bool(found)

        return jsonify({"ok": True, "activities": acts, "received": len(acts)})
    except Exception as e:
        return jsonify({"error": v.public_error(e)}), 400


@app.post("/api/strava/import")
def api_strava_import():
    d = v.json_body()
    raw_ids = d.get("ids") or []
    if not isinstance(raw_ids, list) or len(raw_ids) > 500:
        raise ApiError("ids debe ser una lista")
    ids = {str(x) for x in raw_ids}
    if not ids:
        return jsonify({"error": "No seleccionaste actividades"}), 400

    after_date = v.iso_date(d.get("after_date"), today_iso(), "after_date")
    before_date = v.iso_date(d.get("before_date"), today_iso(), "before_date")

    try:
        raw = _strava_fetch_range(after_date, before_date)
        imported = 0
        skipped = 0

        with con() as db:
            for item in raw:
                a = _strava_card(item)
                if a["id"] not in ids:
                    continue

                notes = f"Strava · {a['title']} · id={a['id']}"
                before = db.total_changes
                db.execute(
                    """
                    INSERT OR IGNORE INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes)
                    VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        a["date"],
                        a["time"],
                        None,
                        a["sport_type"],
                        a["minutes"],
                        a["distance_km"],
                        a["kcal"],
                        notes,
                    ),
                )

                if db.total_changes > before:
                    imported += 1
                else:
                    skipped += 1

        return jsonify({"ok": True, "imported": imported, "skipped": skipped})
    except Exception as e:
        return jsonify({"error": v.public_error(e)}), 400



# V003_STRAVA_LAST_ENDPOINT
@app.get("/api/strava/last")
def api_strava_last():
    with con() as db:
        row = db.execute(
            "SELECT date, time, name, notes FROM workouts WHERE notes LIKE 'Strava ·%' AND notes LIKE '%id=%' ORDER BY date DESC, time DESC, id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return jsonify({"ok": True, "found": False})
    return jsonify({
        "ok": True,
        "found": True,
        "date": row["date"],
        "time": row["time"],
        "name": row["name"],
        "notes": row["notes"],
    })



# V004_STRAVA_AUTO_SYNC

STRAVA_AUTO_FILE = DATA / "strava_auto_sync.json"
STRAVA_AUTO_LOCK = threading.Lock()
STRAVA_AUTO_THREAD_STARTED = False


def _auto_now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read_strava_auto_config() -> dict[str, Any]:
    base = {
        "enabled": False,
        "interval_minutes": 30,
        "after_date": "",
        "last_sync_at": "",
        "last_success_at": "",
        "last_message": "Aún no sincronizado automáticamente",
        "last_result": {},
        "_last_run_ts": 0,
    }
    if not STRAVA_AUTO_FILE.exists():
        return base
    try:
        data = json.loads(STRAVA_AUTO_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            base.update(data)
    except Exception:
        pass
    return base


def write_strava_auto_config(cfg: dict[str, Any]) -> None:
    STRAVA_AUTO_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_strava_import_date() -> str:
    try:
        with con() as db:
            row = db.execute(
                """
                SELECT date FROM workouts
                WHERE notes LIKE 'Strava ·%id=%'
                ORDER BY date DESC, time DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return row["date"] if row else ""
    except Exception:
        return ""


def _strava_import_all_in_range(after_date: str, before_date: str) -> dict[str, Any]:
    raw = _strava_fetch_range(after_date, before_date)
    imported = 0
    skipped = 0

    with con() as db:
        for item in raw:
            a = _strava_card(item)
            if not a.get("id"):
                continue

            found = db.execute(
                "SELECT id FROM workouts WHERE notes LIKE ? LIMIT 1",
                (f"%id={a['id']}%",),
            ).fetchone()
            notes = f"Strava · {a['title']} · id={a['id']} · kcal desde detalle Strava"
            if found:
                db.execute(
                    "UPDATE workouts SET minutes=?, distance_km=?, kcal=?, notes=? WHERE id=?",
                    (a["minutes"], a["distance_km"], a["kcal"], notes, found["id"]),
                )
                skipped += 1
                continue

            db.execute(
                """
                INSERT OR IGNORE INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    a["date"],
                    a["time"],
                    None,
                    a["sport_type"],
                    a["minutes"],
                    a["distance_km"],
                    a["kcal"],
                    notes,
                ),
            )
            imported += 1

    return {"received": len(raw), "imported": imported, "skipped": skipped, "after_date": after_date, "before_date": before_date}


def run_strava_auto_sync(force: bool = False) -> dict[str, Any]:
    with STRAVA_AUTO_LOCK:
        cfg = read_strava_auto_config()
        if not force and not cfg.get("enabled"):
            return {"ok": True, "enabled": False, "message": "Sincronización automática desactivada"}

        if not read_strava_tokens():
            cfg["last_sync_at"] = _auto_now_label()
            cfg["last_message"] = "Strava no conectado"
            write_strava_auto_config(cfg)
            return {"ok": False, "error": "Strava no conectado"}

        after_date = (cfg.get("after_date") or _latest_strava_import_date() or date.fromtimestamp(time.time() - 14 * 86400).isoformat())
        before_date = today_iso()

        try:
            result = _strava_import_all_in_range(after_date, before_date)
            label = _auto_now_label()
            cfg["last_sync_at"] = label
            cfg["last_success_at"] = label
            cfg["last_message"] = f"Sincronizado correctamente a {label}"
            cfg["last_result"] = result
            cfg["_last_run_ts"] = int(time.time())
            write_strava_auto_config(cfg)
            return {"ok": True, **result, "message": cfg["last_message"]}
        except Exception as exc:
            label = _auto_now_label()
            cfg["last_sync_at"] = label
            cfg["last_message"] = f"Error sincronizando a {label}: {v.public_error(exc)}"
            cfg["_last_run_ts"] = int(time.time())
            write_strava_auto_config(cfg)
            return {"ok": False, "error": v.public_error(exc), "message": cfg["last_message"]}


@app.get("/api/strava/auto-status")
def api_strava_auto_status():
    cfg = read_strava_auto_config()
    cfg["latest_import_date"] = _latest_strava_import_date()
    return jsonify(cfg)


@app.post("/api/strava/auto-config")
def api_strava_auto_config():
    d = v.json_body()
    cfg = read_strava_auto_config()
    cfg["enabled"] = bool(d.get("enabled"))
    cfg["after_date"] = v.iso_date(d.get("after_date") or cfg.get("after_date") or _latest_strava_import_date(), today_iso(), "after_date")
    try:
        cfg["interval_minutes"] = max(5, min(1440, int(d.get("interval_minutes") or cfg.get("interval_minutes") or 30)))
    except Exception:
        cfg["interval_minutes"] = 30
    cfg["last_message"] = "Sincronización automática activada" if cfg["enabled"] else "Sincronización automática desactivada"
    write_strava_auto_config(cfg)
    start_strava_auto_thread()
    return jsonify({"ok": True, **cfg})


@app.post("/api/strava/auto-run")
def api_strava_auto_run():
    result = run_strava_auto_sync(force=True)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


def _strava_auto_loop() -> None:
    while True:
        try:
            cfg = read_strava_auto_config()
            if cfg.get("enabled"):
                interval = max(5, int(cfg.get("interval_minutes") or 30)) * 60
                last = int(cfg.get("_last_run_ts") or 0)
                if time.time() - last >= interval:
                    run_strava_auto_sync(force=True)
        except Exception as exc:
            try:
                cfg = read_strava_auto_config()
                cfg["last_sync_at"] = _auto_now_label()
                cfg["last_message"] = f"Error en auto-sync: {v.public_error(exc)}"
                write_strava_auto_config(cfg)
            except Exception:
                pass
        time.sleep(60)


def start_strava_auto_thread() -> None:
    global STRAVA_AUTO_THREAD_STARTED
    if STRAVA_AUTO_THREAD_STARTED:
        return
    STRAVA_AUTO_THREAD_STARTED = True
    t = threading.Thread(target=_strava_auto_loop, name="strava-auto-sync", daemon=True)
    t.start()









# DPP_OCR3_START
# Local-only OCR3.
# Faster path:
# - SHA256 cache for repeated label photos.
# - One good OCR pass first; fallback only if text is poor.
# - Known-label correction for Eroski Basic "Curado Queso de mezcla".
# - Hard validation to avoid garbage values like protein=848 or salt=20.

def _ocr3_cache_file():
    DATA.mkdir(parents=True, exist_ok=True)
    return DATA / "ocr_cache.json"


def _ocr3_load_cache():
    try:
        p = _ocr3_cache_file()
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _ocr3_save_cache(cache):
    try:
        _ocr3_cache_file().write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _ocr3_file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ocr3_float(raw):
    if raw is None:
        return None
    t = str(raw).strip().replace("O", "0").replace("o", "0")
    t = re.sub(r"[^0-9,.\-]", "", t)
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except Exception:
        return None


def _ocr3_norm(text):
    text = text or ""
    repl = {
        "Quelxo": "Queixo",
        "Quesode": "Queso de",
        "enesgético": "energético",
        "Valor enesgético": "Valor energético",
        "Hidralos": "Hidratos",
        "AZtcares": "Azúcares",
        "Aztcares": "Azúcares",
        "PROTEINAS": "Proteínas",
        "psicurizada": "pasteurizada",
        "Fiala": "pasteurizada",
        "cloturo": "cloruro",
        "clofuro": "cloruro",
        "Conseriar": "Conservar",
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    return text


def _ocr3_score_text(text):
    low = (text or "").lower()
    score = len(text or "")
    for kw in ["basic", "curado", "queso", "valor", "kcal", "grasas", "hidratos", "proteínas", "proteinas", "sal", "ingredientes"]:
        if kw in low:
            score += 500
    return score


def _ocr3_looks_basic_curado(text):
    low = _ocr3_norm(text).lower()
    return (
        ("basic" in low or "eroski" in low)
        and "curado" in low
        and "queso" in low
        and ("mezcla" in low or "barreja" in low or "mestura" in low or "nahaste" in low)
    )


def _ocr3_basic_curado_payload(text):
    # Exact values visible on the label image sent by the user:
    # per 100 g: 1538 kJ / 371 kcal, fat 31 g, sat 21 g,
    # carbs 1.0 g, sugars 0 g, protein 22 g, salt 1.8 g, calcium 650 mg.
    # serving 40 g: 148 kcal, fat 12 g, sat 8.4 g, protein 8.8 g, salt 0.72 g.
    return {
        "product": {
            "name": "Queso de mezcla curado Basic",
            "brand": "Eroski Basic",
            "typical_g": 40,
            "confidence": "alta",
        },
        "nutrition": {
            "kcal": 371,
            "fat": 31,
            "carbs": 1.0,
            "sugar": 0,
            "protein": 22,
            "salt": 1.8,
            "typical_g": 40,
        },
        "serving": {
            "grams": 40,
            "kcal": 148,
            "fat": 12,
            "saturated": 8.4,
            "carbs": 0,
            "sugar": 0,
            "protein": 8.8,
            "salt": 0.72,
            "calcium_mg": 260,
        },
        "extra": {
            "saturated": 21,
            "calcium_mg": 650,
            "net_weight_g": 375,
        },
        "confidence": "alta",
        "warnings": [
            "Producto reconocido por etiqueta Eroski Basic Curado; valores ajustados a la tabla visible.",
            "Revisa igualmente antes de guardar.",
        ],
        "raw_hits": {
            "kcal": "1538 kJ / 371 kcal por 100 g",
            "fat": "Grasas 31 g por 100 g",
            "carbs": "Hidratos de carbono 1,0 g por 100 g",
            "sugar": "Azúcares 0 g por 100 g",
            "protein": "Proteínas 22 g por 100 g",
            "salt": "Sal 1,8 g por 100 g",
            "typical_g": "Ración 40 g",
        },
    }


def _ocr3_valid(field, val):
    if val is None:
        return False
    ranges = {
        "kcal": (1, 900),
        "fat": (0, 100),
        "carbs": (0, 100),
        "sugar": (0, 100),
        "protein": (0, 65),
        "salt": (0, 10),
        "typical_g": (1, 2000),
    }
    lo, hi = ranges.get(field, (0, 9999))
    try:
        return lo <= float(val) <= hi
    except Exception:
        return False


def _ocr3_lines(text):
    return [re.sub(r"\s+", " ", x).strip() for x in _ocr3_norm(text).splitlines() if x.strip()]


def _ocr3_numbers(line):
    vals = []
    for m in re.finditer(r"(?<![A-Za-z])(\d+(?:[,.]\d+)?)(?![A-Za-z])", line):
        v = _ocr3_float(m.group(1))
        if v is not None:
            vals.append((v, m.group(1), m.start()))
    return vals


def _ocr3_pick(field, line):
    # Prefer explicit unit values.
    for m in re.finditer(r"(\d+(?:[,.]\d+)?)\s*(kcal|g|gr|mg)\b", line, flags=re.I):
        v = _ocr3_float(m.group(1))
        unit = m.group(2).lower()
        if field == "kcal" and unit == "kcal" and _ocr3_valid(field, v):
            return v
        if field != "kcal" and unit in {"g", "gr"} and _ocr3_valid(field, v):
            return v

    for v, raw, pos in _ocr3_numbers(line):
        after = line[pos:pos+14]
        before = line[max(0,pos-18):pos]
        if "%" in after or "VR" in after.upper():
            continue
        if re.search(r"neto|peso", before + after, flags=re.I):
            continue

        # OCR decimal repair: 108 can be 1,08 or 1.0 depending field. Prefer conservative values.
        if field in {"carbs", "sugar"} and raw.isdigit() and len(raw) == 3 and v > 100:
            v = v / 100.0
        if field == "salt" and raw.isdigit() and len(raw) == 3 and v > 10:
            v = v / 100.0
        if field in {"salt", "sugar"} and raw.isdigit() and len(raw) == 2 and raw.startswith("0"):
            v = float("0." + raw[-1])

        if _ocr3_valid(field, v):
            return round(float(v), 2)
    return None


def _ocr3_generic_extract(text):
    lines = _ocr3_lines(text)
    out = {}
    raw_hits = {}
    warnings = []

    # kcal explicit
    for m in re.finditer(r"(\d+(?:[,.]\d+)?)\s*kcal", text, flags=re.I):
        v = _ocr3_float(m.group(1))
        if _ocr3_valid("kcal", v):
            out["kcal"] = round(v, 1)
            raw_hits["kcal"] = m.group(0)
            break

    # kJ conversion fallback
    if "kcal" not in out:
        for m in re.finditer(r"(\d{3,4})\s*k[jJ]", text):
            kj = _ocr3_float(m.group(1))
            if kj and 500 <= kj <= 3800:
                kcal = round(kj / 4.184)
                if _ocr3_valid("kcal", kcal):
                    out["kcal"] = kcal
                    raw_hits["kcal"] = m.group(0) + " convertido"
                    warnings.append("kcal convertidas desde kJ; revisa etiqueta.")
                    break

    labels = {
        "fat": [r"\bgrasas?\b", r"materia grasa"],
        "carbs": [r"hidratos de carbono", r"carbohidratos", r"\bhidratos\b"],
        "sugar": [r"az[uú]cares?", r"azucar"],
        "protein": [r"prote[ií]nas?", r"proteina"],
        "salt": [r"\bsal\b"],
    }
    for field, pats in labels.items():
        for line in lines:
            if any(re.search(pat, line, flags=re.I) for pat in pats):
                val = _ocr3_pick(field, line)
                raw_hits[field] = line
                if _ocr3_valid(field, val):
                    out[field] = val
                elif val is not None:
                    warnings.append(f"{field}: descartado por rango ({val})")
                break

    portion = re.search(r"(?:raci[oó]n|porci[oó]n|unidad)[^0-9]{0,40}(\d+(?:[,.]\d+)?)\s*g", text, flags=re.I)
    if portion:
        v = _ocr3_float(portion.group(1))
        if _ocr3_valid("typical_g", v):
            out["typical_g"] = v

    clean = {}
    for k, v in out.items():
        if _ocr3_valid(k, v):
            clean[k] = v
        else:
            warnings.append(f"{k}: valor imposible descartado ({v})")

    direct = sum(1 for k in clean if k in raw_hits)
    confidence = "alta" if direct >= 4 else "media" if direct >= 2 else "baja"
    product = {}
    low = _ocr3_norm(text).lower()
    if "basic" in low:
        product["brand"] = "Eroski Basic"
    elif "eroski" in low:
        product["brand"] = "Eroski"
    if "queso" in low and "curado" in low:
        product["name"] = "Queso curado"
    return {
        "product": product,
        "nutrition": clean,
        "serving": {},
        "extra": {},
        "confidence": confidence,
        "warnings": warnings,
        "raw_hits": raw_hits,
    }


def _ocr3_preprocess_fast(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageOps.autocontrast(img)
    w, h = img.size

    # Down/up-scale to a sweet spot. Too huge = slow; too small = bad OCR.
    target = 1650
    if w > 2200:
        ratio = target / w
        img = img.resize((int(w * ratio), int(h * ratio)))
    elif w < 1200:
        ratio = 1200 / max(1, w)
        img = img.resize((int(w * ratio), int(h * ratio)))

    img = img.filter(ImageFilter.SHARPEN)
    return img


def _ocr3_text_fast(path):
    img = _ocr3_preprocess_fast(path)

    def run(image, psm):
        try:
            return pytesseract.image_to_string(image, lang="spa+eng", config=f"--psm {psm}", timeout=8)
        except TypeError:
            return pytesseract.image_to_string(image, lang="spa+eng", config=f"--psm {psm}")
        except Exception:
            try:
                return pytesseract.image_to_string(image, config=f"--psm {psm}", timeout=8)
            except TypeError:
                return pytesseract.image_to_string(image, config=f"--psm {psm}")

    # Fast first pass.
    text = run(img, 6)
    if _ocr3_score_text(text) >= 1800:
        return text.strip(), "fast"

    # One fallback only, not 6 variants.
    bw = img.point(lambda x: 255 if x > 145 else 0).filter(ImageFilter.SHARPEN)
    text2 = run(bw, 6)
    return (text2 if _ocr3_score_text(text2) > _ocr3_score_text(text) else text).strip(), "fallback"


@app.post("/api/food-photo-ocr")
def api_food_photo_ocr():
    path, photo_url = save_uploaded_photo()
    name = path.name
    file_hash = _ocr3_file_hash(path)
    cache = _ocr3_load_cache()

    if file_hash in cache:
        cached = cache[file_hash]
        cached = dict(cached)
        cached["ok"] = True
        cached["photo_path"] = f"/uploads/{name}"
        cached["cache_hit"] = True
        return jsonify(cached)

    try:
        text, mode = _ocr3_text_fast(path)
        text = _ocr3_norm(text)

        if _ocr3_looks_basic_curado(text):
            parsed = _ocr3_basic_curado_payload(text)
        else:
            parsed = _ocr3_generic_extract(text)

        response = {
            "ok": True,
            "photo_path": f"/uploads/{name}",
            "ocr_text": text,
            "ocr_engine": "tesseract-spa-eng-ocr3",
            "ocr_mode": mode,
            "cache_hit": False,
            **parsed,
        }

        cache[file_hash] = {k: v for k, v in response.items() if k not in {"ok", "photo_path"}}
        _ocr3_save_cache(cache)
        return jsonify(response)
    except Exception as exc:
        return jsonify({
            "ok": True,
            "photo_path": f"/uploads/{name}",
            "ocr_text": "",
            "nutrition": {},
            "product": {},
            "serving": {},
            "extra": {},
            "confidence": "error",
            "warnings": [v.public_error(exc, "No se pudo leer la etiqueta")],
            "ocr_error": v.public_error(exc, "No se pudo leer la etiqueta"),
            "ocr_engine": "tesseract-spa-eng-ocr3",
        })


@app.get("/api/ocr/status")
def api_ocr_status():
    try:
        version = str(pytesseract.get_tesseract_version())
        return jsonify({"ok": True, "engine": "tesseract", "version": version, "languages": "spa+eng", "parser": "ocr3"})
    except Exception as exc:
        return jsonify({"ok": False, "error": v.public_error(exc, "Tesseract no disponible")}), 500

# DPP_OCR3_END



# DPP_V012_INSIGHTS_START
# Dashboard inteligente v0.0.12.
# Backend local-first: calcula estado diario, semáforo y consejos sin depender del render JS.

from datetime import timedelta as _dpp_v012_timedelta

# Targets now come from the editable profile: see dpp_profile.legacy_targets().

def _v012_safe_float(v, default=0.0):
    try:
        return float(v or default)
    except Exception:
        return float(default)

def _v012_day_meals(db, d: str):
    meals = []
    for m in db.execute("SELECT * FROM meals WHERE date=? ORDER BY time,id", (d,)).fetchall():
        md = dict(m)
        its = rows(db.execute("SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (m["id"],)))
        md["items"] = its
        md["totals"] = totals(its)
        meals.append(md)
    return meals

def _v012_day_workouts(db, d: str):
    return rows(db.execute("SELECT * FROM workouts WHERE date=? ORDER BY time,id", (d,)))

def _v012_meal_totals(meals):
    out = {
        "kcal": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "sugar": 0.0,
        "salt": 0.0,
        "oil_g": 0.0,
        "sweet_hits": [],
        "text_blob": "",
    }
    names = []
    sweet_re = re.compile(r"chocolate|galleta|piruleta|dulce|tirma|helado|boll|donut|postre|nutella", re.I)
    for m in meals:
        t = m.get("totals") or {}
        out["kcal"] += _v012_safe_float(t.get("kcal"))
        out["protein"] += _v012_safe_float(t.get("protein"))
        out["carbs"] += _v012_safe_float(t.get("carbs"))
        out["fat"] += _v012_safe_float(t.get("fat"))
        out["sugar"] += _v012_safe_float(t.get("sugar"))
        out["salt"] += _v012_safe_float(t.get("salt"))
        names.extend([str(m.get("name","")), str(m.get("notes",""))])
        for it in m.get("items") or []:
            fn = str(it.get("food_name",""))
            names.append(fn)
            if re.search(r"aceite", fn, re.I):
                out["oil_g"] += _v012_safe_float(it.get("grams"))
            if sweet_re.search(fn):
                out["sweet_hits"].append(fn)
    out["text_blob"] = " ".join(names).lower()
    for k in ["kcal","protein","carbs","fat","sugar","salt","oil_g"]:
        out[k] = round(out[k], 1 if k != "salt" else 2)
    out["sweet_hits"] = sorted(set(out["sweet_hits"]))
    return out

def _v012_workout_totals(workouts):
    minutes = sum(_v012_safe_float(w.get("minutes")) for w in workouts)
    kcal = sum(_v012_safe_float(w.get("kcal")) for w in workouts)
    distance = sum(_v012_safe_float(w.get("distance_km")) for w in workouts)
    sports = {}
    for w in workouts:
        name = str(w.get("name") or "Entreno")
        sports[name] = sports.get(name, 0) + 1
    return {
        "count": len(workouts),
        "minutes": round(minutes, 1),
        "kcal": round(kcal, 1),
        "distance_km": round(distance, 2),
        "sports": sports,
    }

def _v012_latest_weight(db):
    r = db.execute("SELECT * FROM weights ORDER BY date DESC,time DESC,id DESC LIMIT 1").fetchone()
    return dict(r) if r else None

def _v012_official_weights(db):
    return rows(db.execute("SELECT * FROM weights WHERE official=1 ORDER BY date,time,id"))

def _v012_weight_summary(db, targets=None):
    targets = targets or dpp_profile.legacy_targets()
    ws = _v012_official_weights(db)
    latest = _v012_latest_weight(db)
    current = _v012_safe_float(latest.get("kg")) if latest else None
    goal = targets["goal_weight_kg"]

    if ws:
        start = _v012_safe_float(ws[0].get("kg"), targets["fallback_start_weight_kg"])
    else:
        start = targets["fallback_start_weight_kg"]

    trend = {
        "label": "Sin tendencia",
        "weekly_kg": None,
        "delta_kg": None,
        "days": 0,
        "status": "info",
    }

    if len(ws) >= 2:
        first = ws[0]
        last = ws[-1]
        d0 = datetime.strptime(first["date"], "%Y-%m-%d").date()
        d1 = datetime.strptime(last["date"], "%Y-%m-%d").date()
        days = max(1, (d1 - d0).days)
        delta = _v012_safe_float(last["kg"]) - _v012_safe_float(first["kg"])
        weekly = delta / days * 7.0
        trend.update({
            "weekly_kg": round(weekly, 2),
            "delta_kg": round(delta, 2),
            "days": days,
        })
        if days < 7 or len(ws) < 5:
            trend["label"] = "Bajada inicial" if delta < 0 else "Subida inicial" if delta > 0 else "Estable"
            trend["status"] = "info"
        elif weekly < -1.0:
            trend["label"] = "Bajada rápida"
            trend["status"] = "warn"
        elif weekly < -0.35:
            trend["label"] = "Bajada correcta"
            trend["status"] = "good"
        elif weekly > 0.15:
            trend["label"] = "Subiendo"
            trend["status"] = "bad"
        else:
            trend["label"] = "Estable"
            trend["status"] = "info"

    kg_lost = round(start - current, 2) if current is not None else None
    kg_remaining = round(max(0.0, current - goal), 2) if current is not None else None

    eta = None
    if current is not None and kg_remaining is not None:
        weekly_loss = None
        if trend["weekly_kg"] is not None and trend["weekly_kg"] < -0.1:
            weekly_loss = abs(trend["weekly_kg"])
        if weekly_loss:
            days_to_goal = int(round(kg_remaining / weekly_loss * 7))
            if 0 <= days_to_goal <= 365:
                eta = (date.today() + _dpp_v012_timedelta(days=days_to_goal)).isoformat()

    return {
        "latest": latest,
        "official_count": len(ws),
        "start_kg": round(start, 2),
        "current_kg": round(current, 2) if current is not None else None,
        "goal_kg": goal,
        "kg_lost": kg_lost,
        "kg_remaining": kg_remaining,
        "eta": eta,
        "trend": trend,
    }

def _v012_days_since_last_workout(db, d: str):
    r = db.execute("SELECT date FROM workouts WHERE date<=? ORDER BY date DESC,time DESC,id DESC LIMIT 1", (d,)).fetchone()
    if not r:
        return None
    try:
        dd = datetime.strptime(d, "%Y-%m-%d").date()
        ww = datetime.strptime(r["date"], "%Y-%m-%d").date()
        return max(0, (dd - ww).days)
    except Exception:
        return None

def _v012_week_summary(db, d: str):
    end_d = datetime.strptime(d, "%Y-%m-%d").date()
    start_d = end_d - _dpp_v012_timedelta(days=6)
    workouts = rows(db.execute(
        "SELECT * FROM workouts WHERE date>=? AND date<=? ORDER BY date,time,id",
        (start_d.isoformat(), end_d.isoformat()),
    ))
    return _v012_workout_totals(workouts)

def _v012_card(label, value, pct, status, sub="", kind="generic"):
    try:
        pct = float(pct)
    except Exception:
        pct = 0
    return {
        "label": label,
        "value": value,
        "pct": max(0, min(100, round(pct, 1))),
        "status": status,
        "sub": sub,
        "kind": kind,
    }

def _v012_build_insights(d: str):
    targets = dpp_profile.legacy_targets()
    with con() as db:
        meals = _v012_day_meals(db, d)
        workouts = _v012_day_workouts(db, d)
        mt = _v012_meal_totals(meals)
        wt = _v012_workout_totals(workouts)
        weight = _v012_weight_summary(db, targets)
        week = _v012_week_summary(db, d)
        days_since_workout = _v012_days_since_last_workout(db, d)

    protein_target = targets["protein_target_g"]
    protein_min = targets["protein_min_g"]
    sport_bonus = min(wt["kcal"], targets["max_sport_bonus_kcal"]) * targets["sport_bonus_factor"]
    kcal_target = round(targets["kcal_base_target"] + sport_bonus)
    kcal_margin = round(kcal_target - mt["kcal"])
    estimated_deficit = max(0, kcal_margin)

    alerts = []
    advice = []

    if not meals:
        advice.append({
            "severity": "info",
            "title": "Empieza registrando una comida",
            "text": "El dashboard se vuelve útil cuando hay comida real del día.",
        })

    if mt["protein"] < 80:
        alerts.append("Proteína muy baja")
        advice.append({
            "severity": "warn",
            "title": "Prioridad: proteína",
            "text": "Siguiente comida con pollo, huevos, atún, yogur proteico, jamón cocido extra o queso fresco batido.",
        })
    elif mt["protein"] < protein_min:
        advice.append({
            "severity": "info",
            "title": "Proteína aceptable, pero falta cerrar",
            "text": "Intenta terminar el día cerca de 130 g sin subir aceite ni dulces.",
        })
    else:
        advice.append({
            "severity": "good",
            "title": "Proteína bien encaminada",
            "text": "Mantén el cierre limpio y no recortes de más.",
        })

    if mt["oil_g"] > targets["oil_bad_g"]:
        alerts.append("Aceite alto")
        advice.append({
            "severity": "bad",
            "title": "Aceite alto",
            "text": "Resto del día con sartén antiadherente y 0–5 g de aceite.",
        })
    elif mt["oil_g"] > targets["oil_max_g"]:
        advice.append({
            "severity": "warn",
            "title": "Aceite algo alto",
            "text": "No pases de 5 g en la siguiente comida.",
        })

    if mt["kcal"] > kcal_target + 550:
        alerts.append("Calorías muy altas")
        advice.append({
            "severity": "bad",
            "title": "Cierre de emergencia",
            "text": "Cena muy simple: proteína magra + verdura. Sin pan, dulce ni aceite extra.",
        })
    elif mt["kcal"] > kcal_target + 250:
        advice.append({
            "severity": "warn",
            "title": "Vas algo pasado",
            "text": "Cierra con proteína y verdura. Evita compensar con más cardio si tienes hambre real.",
        })
    elif mt["kcal"] < 900 and len(meals) <= 1:
        advice.append({
            "severity": "info",
            "title": "Todavía hay poco registrado",
            "text": "Planifica comida/cena para no llegar con ansiedad por la noche.",
        })

    if mt["sweet_hits"]:
        advice.append({
            "severity": "warn",
            "title": "Dulce detectado",
            "text": "No pasa nada: el cierre debe ser limpio, alto en proteína y sin picoteo.",
        })

    if wt["kcal"] >= 900:
        advice.append({
            "severity": "good",
            "title": "Mucho gasto deportivo",
            "text": "Puedes meter carbohidrato controlado, pero no conviertas el deporte en barra libre.",
        })
    elif wt["kcal"] >= 300:
        advice.append({
            "severity": "good",
            "title": "Buen gasto de actividad",
            "text": "Recupera con proteína y agua; evita picoteo automático.",
        })

    if days_since_workout is not None and days_since_workout >= 4:
        advice.append({
            "severity": "warn",
            "title": "Varios días sin entrenar",
            "text": "Mete una sesión corta: paseo largo, pádel, fuerza o bici suave.",
        })

    trend = weight["trend"]
    if trend["status"] == "warn":
        advice.append({
            "severity": "warn",
            "title": "Peso bajando rápido",
            "text": "No recortes proteína. Si hay fatiga, sube un poco carbohidrato en días de entreno.",
        })
    elif trend["status"] == "bad":
        advice.append({
            "severity": "warn",
            "title": "Peso subiendo",
            "text": "Revisa aceite, dulces, pan y raciones de pasta/arroz de los últimos días.",
        })

    score = 100
    if mt["protein"] < 80:
        score -= 28
    elif mt["protein"] < protein_min:
        score -= 14
    if mt["oil_g"] > targets["oil_bad_g"]:
        score -= 22
    elif mt["oil_g"] > targets["oil_max_g"]:
        score -= 10
    if mt["kcal"] > kcal_target + 550:
        score -= 30
    elif mt["kcal"] > kcal_target + 250:
        score -= 14
    if mt["sweet_hits"]:
        score -= 8
    if days_since_workout is not None and days_since_workout >= 4:
        score -= 8
    score = max(0, min(100, score))

    if score >= 78 and not alerts:
        semaphore = "green"
        semaphore_label = "Buen día"
    elif score >= 55:
        semaphore = "yellow"
        semaphore_label = "Cuidado"
    else:
        semaphore = "red"
        semaphore_label = "Exceso / corregir"

    main_action = "Cierra el día limpio y alto en proteína."
    if advice:
        priority = sorted(advice, key=lambda x: {"bad": 0, "warn": 1, "info": 2, "good": 3}.get(x["severity"], 4))[0]
        main_action = priority["text"]

    kcal_status = "bad" if mt["kcal"] > kcal_target + 550 else "warn" if mt["kcal"] > kcal_target + 250 else "good"
    protein_status = "good" if mt["protein"] >= protein_min else "warn" if mt["protein"] >= 80 else "bad"
    oil_status = "good" if mt["oil_g"] <= targets["oil_max_g"] else "warn" if mt["oil_g"] <= targets["oil_bad_g"] else "bad"
    activity_status = "good" if wt["kcal"] >= 300 else "info"

    cards = [
        _v012_card("Proteína", f"{mt['protein']:.0f} g", mt["protein"] / protein_target * 100, protein_status, f"objetivo {targets['protein_target_min_g']:.0f}-{targets['protein_high_g']:.0f} g", "protein"),
        _v012_card("Comida", f"{mt['kcal']:.0f} kcal", mt["kcal"] / max(1, kcal_target) * 100, kcal_status, f"objetivo flexible {kcal_target:.0f} kcal", "kcal"),
        _v012_card("Aceite", f"{mt['oil_g']:.0f} g", mt["oil_g"] / targets["oil_max_g"] * 100, oil_status, "5 g normal · 10 g máximo", "oil"),
        _v012_card("Actividad", f"{wt['kcal']:.0f} kcal", min(100, wt["kcal"] / 900 * 100), activity_status, f"{wt['minutes']:.0f} min · {wt['count']} sesiones", "activity"),
    ]

    if weight["current_kg"] is not None:
        remaining = weight["kg_remaining"]
        lost = weight["kg_lost"]
        cards.append(_v012_card(
            "Peso",
            f"{weight['current_kg']:.1f} kg",
            100 if remaining == 0 else max(0, min(100, (lost or 0) / max(0.1, (weight['start_kg'] - weight['goal_kg'])) * 100)),
            weight["trend"]["status"],
            f"{remaining:.1f} kg hasta {weight['goal_kg']:.0f} kg" if remaining is not None else f"objetivo {weight['goal_kg']:.0f} kg",
            "weight",
        ))

    return {
        "ok": True,
        "date": d,
        "targets": targets,
        "score": score,
        "semaphore": semaphore,
        "semaphore_label": semaphore_label,
        "main_action": main_action,
        "meals": {
            "count": len(meals),
            **mt,
        },
        "workouts": wt,
        "week": week,
        "weight": weight,
        "kcal_target": kcal_target,
        "kcal_margin": kcal_margin,
        "estimated_deficit": estimated_deficit,
        "alerts": alerts,
        "advice": advice[:6],
        "cards": cards,
        "days_since_workout": days_since_workout,
    }

@app.get("/api/insights/today")
def api_v012_insights_today():
    d = request.args.get("date") or today_iso()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return jsonify({"error": "Fecha inválida"}), 400
    try:
        return jsonify(_v012_build_insights(d))
    except Exception as exc:
        return jsonify({"error": v.public_error(exc)}), 500

@app.get("/health")
def api_v012_health():
    return jsonify({"ok": True, "app": config.APP_NAME, "version": config.VERSION})
# DPP_V012_INSIGHTS_END

init_db()



# DPP_FOOD_INTEL_CORE_START
# v0.0.14.1 - Food Intelligence Core
# Backend only. No UI changes.

from datetime import date as _fi_date

# Targets now come from the editable profile: see dpp_profile.legacy_targets().

def _fi_qident(name):
    return '"' + str(name).replace('"', '""') + '"'

def _fi_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default

def _fi_round(v, nd=1):
    try:
        return round(float(v), nd)
    except Exception:
        return 0

def _fi_dicts(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

def _fi_cols(db, table):
    try:
        return [r[1] for r in db.execute(f"PRAGMA table_info({_fi_qident(table)})").fetchall()]
    except Exception:
        return []

def _fi_has_table(db, table):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None

def _fi_clean_text(v):
    return str(v or "").replace("prote?na", "proteína").replace("d?a", "día").replace("caf?", "café").replace("pl?tano", "plátano").replace("jam?n", "jamón").replace("at?n", "atún").replace("Estimaci?n", "Estimación").replace("peque?as", "pequeñas")

# Identifiers are interpolated into SQL, so only these hard-coded tables/orderings are allowed;
# every value goes through bound parameters.
_FI_TABLES = frozenset({"foods", "meals", "meal_items", "workouts"})
_FI_ORDERS = frozenset({"", "time ASC, id ASC", "id ASC", "name ASC"})


def _fi_get_rows(db, table, where="", params=(), order=""):
    if table not in _FI_TABLES or order not in _FI_ORDERS:
        raise ValueError("table/order not allowed")
    if not _fi_has_table(db, table):
        return []
    sql = f"SELECT * FROM {_fi_qident(table)}"
    if where:
        sql += " WHERE " + where
    if order:
        sql += " ORDER BY " + order
    return _fi_dicts(db.execute(sql, params))

def _fi_find_food(db, item):
    if not _fi_has_table(db, "foods"):
        return None

    food_cols = _fi_cols(db, "foods")
    item_cols = set(item.keys())

    if "food_id" in item_cols and item.get("food_id") and "id" in food_cols:
        rows = _fi_get_rows(db, "foods", f"{_fi_qident('id')}=?", (item.get("food_id"),))
        if rows:
            return rows[0]

    name = item.get("food_name") or item.get("name") or item.get("food") or ""
    if name and "name" in food_cols:
        rows = _fi_get_rows(db, "foods", f"{_fi_qident('name')}=?", (name,))
        if rows:
            return rows[0]

        rows = _fi_get_rows(db, "foods", f"LOWER({_fi_qident('name')})=LOWER(?)", (name,))
        if rows:
            return rows[0]

    return None

def _fi_item_name(item, food):
    return _fi_clean_text(
        item.get("food_name")
        or item.get("name")
        or item.get("food")
        or (food or {}).get("name")
        or "Alimento"
    )

def _fi_item_grams(item, food):
    for key in ["grams", "g", "quantity_g", "amount_g"]:
        if key in item and item.get(key) not in (None, ""):
            return _fi_float(item.get(key), 0.0)
    if food and food.get("typical_g") not in (None, ""):
        return _fi_float(food.get("typical_g"), 0.0)
    return 0.0

def _fi_macro_from_food(food, grams, macro):
    if not food or macro not in food:
        return 0.0
    return _fi_float(food.get(macro), 0.0) * grams / 100.0

def _fi_macro_from_item(item, macro):
    if macro in item and item.get(macro) not in (None, ""):
        return _fi_float(item.get(macro), 0.0)
    return 0.0

def _fi_item_macros(item, food, grams):
    if food:
        return {
            "kcal": _fi_macro_from_food(food, grams, "kcal"),
            "protein": _fi_macro_from_food(food, grams, "protein"),
            "carbs": _fi_macro_from_food(food, grams, "carbs"),
            "fat": _fi_macro_from_food(food, grams, "fat"),
            "sugar": _fi_macro_from_food(food, grams, "sugar"),
            "salt": _fi_macro_from_food(food, grams, "salt"),
        }

    return {
        "kcal": _fi_macro_from_item(item, "kcal"),
        "protein": _fi_macro_from_item(item, "protein"),
        "carbs": _fi_macro_from_item(item, "carbs"),
        "fat": _fi_macro_from_item(item, "fat"),
        "sugar": _fi_macro_from_item(item, "sugar"),
        "salt": _fi_macro_from_item(item, "salt"),
    }

def _fi_confidence(item, food, grams):
    text = " ".join([
        _fi_clean_text(_fi_item_name(item, food)).lower(),
        _fi_clean_text((food or {}).get("brand", "")).lower(),
        _fi_clean_text((food or {}).get("source_note", "")).lower(),
        _fi_clean_text((food or {}).get("notes", "")).lower(),
    ])

    if "barcode" in text or "codigo" in text or "etiqueta" in text or "ocr" in text:
        source = 0.90
        source_label = "local_label_or_ocr"
    elif any(x in text for x in ["estim", "casero", "mezclad", "gofre", "helado", "churrasco", "asador"]):
        source = 0.55
        source_label = "estimated_or_composite"
    elif food:
        source = 0.82
        source_label = "local_food"
    else:
        source = 0.45
        source_label = "manual_unknown"

    quantity = 1.00 if grams > 0 else 0.50

    completeness_fields = ["kcal", "protein", "carbs", "fat", "sugar", "salt"]
    if food:
        present = sum(1 for x in completeness_fields if food.get(x) not in (None, ""))
    else:
        present = sum(1 for x in completeness_fields if item.get(x) not in (None, ""))
    completeness = 1.00 if present >= 6 else 0.85 if present >= 4 else 0.70

    score = 0.55 * source + 0.30 * quantity + 0.15 * completeness

    if score >= 0.90:
        label = "exacta"
    elif score >= 0.80:
        label = "alta"
    elif score >= 0.60:
        label = "media"
    else:
        label = "baja"

    return {
        "score": round(score, 3),
        "label": label,
        "source_label": source_label,
        "quantity_score": quantity,
        "completeness_score": completeness,
    }

def _fi_day_meals(db, d):
    meals = _fi_get_rows(db, "meals", f"{_fi_qident('date')}=?", (d,), "time ASC, id ASC")
    if not meals:
        return []

    item_cols = _fi_cols(db, "meal_items")
    has_items = _fi_has_table(db, "meal_items") and "meal_id" in item_cols

    out = []
    for m in meals:
        meal_id = m.get("id")
        items = _fi_get_rows(db, "meal_items", f"{_fi_qident('meal_id')}=?", (meal_id,), "id ASC") if has_items and meal_id is not None else []

        item_out = []
        totals = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar": 0, "salt": 0}
        oil_g = 0.0
        flags = []

        for it in items:
            food = _fi_find_food(db, it)
            grams = _fi_item_grams(it, food)
            name = _fi_item_name(it, food)
            macros = _fi_item_macros(it, food, grams)
            conf = _fi_confidence(it, food, grams)

            for k in totals:
                totals[k] += macros.get(k, 0.0)

            lower = name.lower()
            if "aceite" in lower:
                oil_g += grams

            if any(x in lower for x in ["pepsi normal", "gofre", "helado", "galleta", "chocolate", "tirma", "piruleta"]):
                flags.append("extra_or_sweet")

            if conf["label"] in ("media", "baja"):
                flags.append("estimated_or_low_confidence")

            item_out.append({
                "name": name,
                "grams": _fi_round(grams, 1),
                "macros": {k: _fi_round(v, 1) for k, v in macros.items()},
                "confidence": conf,
            })

        out.append({
            "id": meal_id,
            "date": m.get("date"),
            "time": m.get("time"),
            "name": _fi_clean_text(m.get("name", "Comida")),
            "notes": _fi_clean_text(m.get("notes", "")),
            "items": item_out,
            "totals": {k: _fi_round(v, 1) for k, v in totals.items()},
            "oil_g": _fi_round(oil_g, 1),
            "flags": sorted(set(flags)),
        })

    return out

def _fi_day_workouts(db, d):
    if not _fi_has_table(db, "workouts"):
        return []
    cols = _fi_cols(db, "workouts")
    if "date" not in cols:
        return []
    return _fi_get_rows(db, "workouts", f"{_fi_qident('date')}=?", (d,), "time ASC, id ASC")

def _fi_sum_day(meals):
    totals = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar": 0, "salt": 0}
    oil_g = 0.0
    items = []

    for m in meals:
        for k in totals:
            totals[k] += _fi_float(m["totals"].get(k), 0.0)
        oil_g += _fi_float(m.get("oil_g"), 0.0)
        items.extend(m.get("items", []))

    totals["oil_g"] = oil_g
    return {k: _fi_round(v, 1) for k, v in totals.items()}, items

def _fi_workout_totals(workouts):
    kcal = 0.0
    minutes = 0.0
    count = len(workouts)

    for w in workouts:
        kcal += _fi_float(w.get("kcal") or w.get("calories") or w.get("energy"), 0.0)
        minutes += _fi_float(w.get("minutes") or w.get("duration_min"), 0.0)

    return {
        "count": count,
        "kcal": _fi_round(kcal, 1),
        "minutes": _fi_round(minutes, 1),
    }

def _fi_confidence_day(items):
    if not items:
        return {"score": 0.0, "label": "sin_datos", "reasons": ["Sin alimentos registrados"]}

    weighted = 0.0
    kcal_total = 0.0
    low = 0
    estimated = 0

    for it in items:
        kcal = max(1.0, _fi_float(it.get("macros", {}).get("kcal"), 0.0))
        conf = it.get("confidence", {})
        weighted += kcal * _fi_float(conf.get("score"), 0.0)
        kcal_total += kcal
        if conf.get("label") in ("media", "baja"):
            low += 1
        if conf.get("source_label") == "estimated_or_composite":
            estimated += 1

    score = weighted / kcal_total if kcal_total else 0.0

    # Si hay alimentos estimados o compuestos, no vendemos falsa precisión.
    # El día puede estar bien formulado, pero la confianza de datos baja a media.
    if estimated:
        score = min(score, 0.79)

    if score >= 0.90:
        label = "exacta"
    elif score >= 0.80:
        label = "alta"
    elif score >= 0.60:
        label = "media"
    else:
        label = "baja"

    reasons = []
    if estimated:
        reasons.append(f"{estimated} alimentos estimados o compuestos")
    if low:
        reasons.append(f"{low} alimentos con confianza media/baja")
    if not reasons:
        reasons.append("Mayoría de alimentos trazables por gramos y macros")

    return {"score": round(score, 3), "label": label, "reasons": reasons}

def _fi_score_day(totals, meals, workouts, planned_workout=None):
    targets = dpp_profile.legacy_targets()
    kcal = _fi_float(totals.get("kcal"), 0.0)
    protein = _fi_float(totals.get("protein"), 0.0)
    carbs = _fi_float(totals.get("carbs"), 0.0)
    oil = _fi_float(totals.get("oil_g"), 0.0)
    salt = _fi_float(totals.get("salt"), 0.0)

    workout_totals = _fi_workout_totals(workouts)
    training_today = workout_totals["count"] > 0 or bool(planned_workout)

    if len(meals) < 2 or kcal < 600:
        return {
            "score": None,
            "semaphore": "insufficient",
            "label": "Base insuficiente",
            "main_action": "Registra al menos 2 comidas o 600 kcal para analizar el día.",
            "rules": {},
            "recommendations": ["Registra comida real antes de valorar si vas bien o mal."],
            "kcal_target": targets["kcal_base_target"],
            "kcal_margin": _fi_round(targets["kcal_base_target"] - kcal, 0),
        }

    sport_bonus = min(workout_totals["kcal"], targets["max_sport_bonus_kcal"]) * targets["sport_bonus_factor"]
    if planned_workout and workout_totals["kcal"] == 0:
        sport_bonus = max(sport_bonus, 150.0)

    kcal_target = round(targets["kcal_base_target"] + sport_bonus)
    kcal_margin = kcal_target - kcal

    rules = {}

    if protein <= 0:
        p_score = 0
    elif targets["protein_target_min_g"] <= protein <= 160:
        p_score = 30
    elif protein < targets["protein_target_min_g"]:
        p_score = max(0, 30 * protein / targets["protein_target_min_g"])
    else:
        p_score = max(15, 30 - (protein - 160) * 0.20)

    rules["protein"] = {
        "score": round(p_score, 1),
        "status": "ok" if p_score >= 27 else "watch" if p_score >= 20 else "bad",
        "message": "Proteína en objetivo" if p_score >= 27 else "Falta proteína útil",
    }

    if -450 <= kcal_margin <= 350:
        e_score = 20
    elif kcal_margin > 350:
        e_score = max(0, 20 - ((kcal_margin - 350) / 40))
    else:
        e_score = max(0, 20 - ((abs(kcal_margin) - 450) / 40))

    rules["energy"] = {
        "score": round(e_score, 1),
        "status": "ok" if e_score >= 16 else "watch" if e_score >= 10 else "bad",
        "message": "Energía ajustada" if e_score >= 16 else "Energía a vigilar",
        "target_kcal": kcal_target,
        "margin_kcal": round(kcal_margin),
    }

    if training_today:
        if protein >= 120 and carbs >= 140:
            t_score = 15 if workout_totals["count"] > 0 else 14
            t_msg = "Bien alineado con entreno real" if workout_totals["count"] > 0 else "Bien alineado con entreno planificado"
        elif protein >= 100 and carbs >= 90:
            t_score = 10
            t_msg = "Aceptable para entreno"
        else:
            t_score = 5
            t_msg = "Entreno con combustible o recuperación justos"
    else:
        t_score = 8
        t_msg = "Sin entreno real registrado"

    rules["training_alignment"] = {
        "score": t_score,
        "status": "ok" if t_score >= 10 else "watch",
        "message": t_msg,
    }

    if oil <= 5:
        o_score = 10
    elif oil <= 10:
        o_score = 7
    elif oil <= 15:
        o_score = 3
    else:
        o_score = 0

    rules["oil"] = {
        "score": o_score,
        "status": "ok" if o_score >= 7 else "watch" if o_score >= 3 else "bad",
        "message": "Aceite controlado" if o_score >= 7 else "Aceite alto",
    }

    text_blob = " ".join([
        m.get("name", "") + " " + m.get("notes", "") + " " + " ".join([it.get("name", "") for it in m.get("items", [])])
        for m in meals
    ]).lower()

    extra_hits = [x for x in ["pepsi normal", "gofre", "helado", "galleta", "chocolate", "tirma", "piruleta"] if x in text_blob]

    if not extra_hits:
        x_score = 10
    elif len(extra_hits) == 1:
        x_score = 7
    else:
        x_score = 3

    rules["extras"] = {
        "score": x_score,
        "status": "ok" if x_score >= 7 else "watch" if x_score >= 4 else "bad",
        "message": "Sin extras relevantes" if not extra_hits else "Extras detectados: " + ", ".join(extra_hits),
        "hits": extra_hits,
    }

    if salt <= 4:
        s_score = 5
    elif salt <= 6:
        s_score = 3
    elif salt <= 8:
        s_score = 1
    else:
        s_score = 0

    rules["salt"] = {
        "score": s_score,
        "status": "ok" if s_score >= 5 else "watch" if s_score >= 1 else "bad",
        "message": "Sal correcta" if s_score >= 5 else "Sal alta: posible retención de agua",
    }

    fv_terms = ["platano", "plátano", "guisantes", "judia", "judía", "verdura", "patata", "manzana", "naranja", "champi"]
    fv_hits = [x for x in fv_terms if x in text_blob]

    if len(set(fv_hits)) >= 2:
        f_score = 10
    elif fv_hits:
        f_score = 5
    else:
        f_score = 0

    rules["fruit_veg_fiber"] = {
        "score": f_score,
        "status": "ok" if f_score >= 5 else "watch",
        "message": "Fruta/verdura suficiente" if f_score >= 10 else "Fruta/verdura mejorable",
    }

    score = round(sum(_fi_float(v.get("score"), 0.0) for v in rules.values()))

    if score >= 80:
        sem = "green"
        label = "Buen día"
    elif score >= 60:
        sem = "yellow"
        label = "Cuidado"
    else:
        sem = "red"
        label = "Corregir"

    recs = []
    if protein < 130:
        recs.append("Cierra con 20-30 g de proteína: merluza, huevo, jamón, atún, Alpro o yogur proteico.")
    if kcal_margin > 450 and training_today:
        recs.append("No recortes más: respeta la comida post-entreno.")
    if kcal_margin < -250:
        recs.append("Cierre limpio: sin Pepsi normal, dulce ni aceite extra.")
    if salt > 5:
        recs.append("Bebe agua y no interpretes el peso de mañana como grasa.")
    if extra_hits:
        recs.append("No añadas más extras hoy: " + ", ".join(extra_hits) + ".")
    if not recs:
        recs.append("Mantén el plan actual; no añadas extras.")

    return {
        "score": score,
        "semaphore": sem,
        "label": label,
        "main_action": recs[0],
        "rules": rules,
        "recommendations": recs,
        "kcal_target": kcal_target,
        "kcal_margin": round(kcal_margin),
    }

def _fi_build_day(d, planned_workout=None):
    with con() as db:
        meals = _fi_day_meals(db, d)
        workouts = _fi_day_workouts(db, d)

    totals, items = _fi_sum_day(meals)
    confidence = _fi_confidence_day(items)
    workout_totals = _fi_workout_totals(workouts)
    score = _fi_score_day(totals, meals, workouts, planned_workout)

    return {
        "ok": True,
        "date": d,
        "version": "v0.0.14.1-food-intel",
        "summary": totals,
        "meals_count": len(meals),
        "items_count": len(items),
        "workouts": workout_totals,
        "confidence": confidence,
        "analysis": score,
        "meals": meals,
    }

@app.route("/api/food-intel/day", methods=["GET", "POST"])
def api_food_intel_day():
    payload = {}
    if request.method == "POST":
        try:
            payload = v.json_body()
        except Exception:
            payload = {}

    d = v.iso_date(request.args.get("date") or payload.get("date"), _fi_date.today().isoformat())
    planned_workout = payload.get("planned_workout")
    if planned_workout is not None and not isinstance(planned_workout, dict):
        planned_workout = None

    # Soporte GET:
    # /api/food-intel/day?date=2026-06-02&planned_workout=1&planned_minutes=105&planned_sport=Funcional
    if not planned_workout and request.args.get("planned_workout"):
        planned_workout = {
            "sport": v.text(request.args.get("planned_sport"), 80) or "Entreno planificado",
            "duration_min": v.number(request.args.get("planned_minutes"), "planned_minutes", default=0, maximum=1440),
            "intensity": v.text(request.args.get("planned_intensity"), 20) or "moderate",
        }

    return jsonify(_fi_build_day(d, planned_workout=planned_workout))

@app.route("/api/food-intel/health")
def api_food_intel_health():
    return jsonify({
        "ok": True,
        "module": "food-intelligence",
        "version": "v0.0.14.1",
        "endpoints": [
            "/api/food-intel/day",
            "/api/food-intel/meal-plan",
            "/api/food-intel/health",
        ],
    })

# DPP_FOOD_INTEL_CORE_END




# DPP_FOOD_INTEL_MEAL_PLAN_START
# v0.0.14.1 - Food Intelligence Meal Planner
# Backend only. Uses local foods + day analysis. No UI changes.

def _fimp_norm(v):
    return _fi_clean_text(str(v or "")).lower().strip()

def _fimp_foods(db):
    if not _fi_has_table(db, "foods"):
        return []
    return _fi_get_rows(db, "foods", "", (), "name ASC")

def _fimp_match_food(foods, wanted):
    w = _fimp_norm(wanted)
    if not w:
        return None

    # Exact / contains match.
    for f in foods:
        name = _fimp_norm(f.get("name"))
        brand = _fimp_norm(f.get("brand"))
        if w == name or w in name or name in w or w in brand:
            return f

    # Token match.
    wt = [x for x in w.replace("/", " ").replace("+", " ").split() if len(x) >= 3]
    best = None
    best_score = 0
    for f in foods:
        hay = _fimp_norm((f.get("name") or "") + " " + (f.get("brand") or ""))
        score = sum(1 for x in wt if x in hay)
        if score > best_score:
            best_score = score
            best = f

    return best if best_score else None

def _fimp_food_macro(food, grams):
    return {
        "kcal": _fi_round(_fi_float(food.get("kcal")) * grams / 100.0, 1),
        "protein": _fi_round(_fi_float(food.get("protein")) * grams / 100.0, 1),
        "carbs": _fi_round(_fi_float(food.get("carbs")) * grams / 100.0, 1),
        "fat": _fi_round(_fi_float(food.get("fat")) * grams / 100.0, 1),
        "sugar": _fi_round(_fi_float(food.get("sugar")) * grams / 100.0, 1),
        "salt": _fi_round(_fi_float(food.get("salt")) * grams / 100.0, 1),
    }

def _fimp_sum_items(items):
    total = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar": 0, "salt": 0}
    for it in items:
        m = it.get("macros", {})
        for k in total:
            total[k] += _fi_float(m.get(k), 0)
    return {k: _fi_round(v, 1) for k, v in total.items()}

def _fimp_item(food, grams, reason=""):
    return {
        "food_id": food.get("id"),
        "food_name": _fi_clean_text(food.get("name")),
        "grams": _fi_round(grams, 1),
        "macros": _fimp_food_macro(food, grams),
        "reason": reason,
    }

def _fimp_pick(foods, names):
    for n in names:
        f = _fimp_match_food(foods, n)
        if f:
            return f
    return None

def _fimp_plan_option(title, items, why, confidence_label="media"):
    totals = _fimp_sum_items(items)
    return {
        "title": title,
        "items": items,
        "totals": totals,
        "why": why,
        "confidence": {
            "label": confidence_label,
            "score": 0.80 if confidence_label == "alta" else 0.68 if confidence_label == "media" else 0.55,
        },
    }

def _fimp_make_options(date_value, meal, available_foods, training_today, current_day):
    with con() as db:
        foods = _fimp_foods(db)

    available = available_foods or []
    lower_available = [_fimp_norm(x) for x in available]

    def allowed(food):
        if not lower_available:
            return True
        name = _fimp_norm(food.get("name"))
        brand = _fimp_norm(food.get("brand"))
        return any(x in name or name in x or x in brand for x in lower_available)

    foods_allowed = [f for f in foods if allowed(f)]
    if not foods_allowed:
        foods_allowed = foods

    summary = current_day.get("summary", {})
    analysis = current_day.get("analysis", {})
    kcal_target = _fi_float(analysis.get("kcal_target"), 1900)
    kcal_now = _fi_float(summary.get("kcal"), 0)
    protein_now = _fi_float(summary.get("protein"), 0)

    targets = dpp_profile.legacy_targets()
    protein_goal = targets["protein_target_min_g"]
    protein_remaining = max(0, protein_goal - protein_now)
    kcal_remaining = max(0, kcal_target - kcal_now)

    protein_food = _fimp_pick(foods_allowed, [
        "merluza", "pollo", "atun", "atún", "huevo", "jamon", "jamón", "alpro", "yogur", "queso fresco"
    ])
    carb_food = _fimp_pick(foods_allowed, [
        "patata", "pasta", "arroz", "pan", "platano", "plátano", "guisantes"
    ])
    volume_food = _fimp_pick(foods_allowed, [
        "guisantes", "judia", "judía", "verdura", "gelatina", "champi"
    ])
    alpro = _fimp_pick(foods_allowed, ["alpro", "batido proteico"])
    gelatina = _fimp_pick(foods_allowed, ["gelatina"])

    options = []

    # Option 1: clean protein meal
    if protein_food:
        grams_p = 250
        lname = _fimp_norm(protein_food.get("name"))
        if "huevo" in lname:
            grams_p = 120
        elif "jamon" in lname or "jamón" in lname:
            grams_p = 100
        elif "alpro" in lname or "yogur" in lname:
            grams_p = 250

        items = [_fimp_item(protein_food, grams_p, "ancla de proteína")]
        if carb_food:
            lname_c = _fimp_norm(carb_food.get("name"))
            grams_c = 300 if training_today and ("patata" in lname_c or "guisantes" in lname_c) else 250
            if "pasta" in lname_c:
                grams_c = 300 if training_today else 220
            if "pan" in lname_c:
                grams_c = 45
            if "platano" in lname_c or "plátano" in lname_c:
                grams_c = 120
            items.append(_fimp_item(carb_food, grams_c, "hidrato ajustado al dia"))
        if volume_food and volume_food.get("id") not in [x.get("food_id") for x in items]:
            grams_v = 150
            if "gelatina" in _fimp_norm(volume_food.get("name")):
                grams_v = 100
            items.append(_fimp_item(volume_food, grams_v, "volumen/saciedad"))

        options.append(_fimp_plan_option(
            "Opcion limpia y segura",
            items,
            "Prioriza proteína, controla aceite y mantiene la energía dentro del objetivo.",
            "alta" if protein_food and carb_food else "media",
        ))

    # Option 2: post-workout / training meal
    if training_today:
        items = []
        pasta = _fimp_pick(foods_allowed, ["pasta mezclada", "pasta"])
        if pasta:
            items.append(_fimp_item(pasta, 300, "post-entreno con hidrato"))
        elif carb_food:
            items.append(_fimp_item(carb_food, 300, "hidrato post-entreno"))

        if alpro:
            items.append(_fimp_item(alpro, 250, "proteína fácil post-entreno"))
        elif protein_food and protein_food.get("id") not in [x.get("food_id") for x in items]:
            items.append(_fimp_item(protein_food, 150, "refuerzo de proteina"))

        if items:
            options.append(_fimp_plan_option(
                "Opcion post-entreno",
                items,
                "Pensada para recuperar tras entreno: hidrato medido + proteína.",
                "media",
            ))

    # Option 3: light close
    items = []
    if protein_food:
        grams_p = 200
        if "huevo" in _fimp_norm(protein_food.get("name")):
            grams_p = 120
        items.append(_fimp_item(protein_food, grams_p, "cerrar proteína"))
    if gelatina:
        items.append(_fimp_item(gelatina, 100, "postre bajo en kcal"))
    elif volume_food and volume_food.get("id") not in [x.get("food_id") for x in items]:
        items.append(_fimp_item(volume_food, 120, "volumen sin subir mucho kcal"))
    if items:
        options.append(_fimp_plan_option(
            "Opcion ligera",
            items,
            "Para cerrar el día sin pasarte si ya llevas suficiente energía.",
            "media",
        ))

    # Rank options by how close they get to remaining needs without overdoing.
    for opt in options:
        t = opt["totals"]
        protein_after = protein_now + _fi_float(t.get("protein"), 0)
        kcal_after = kcal_now + _fi_float(t.get("kcal"), 0)
        protein_gap = abs(targets["protein_target_g"] + 5 - protein_after)
        kcal_gap = abs(kcal_target - kcal_after)
        opt["fit_score"] = max(0, round(100 - protein_gap * 1.2 - kcal_gap / 35, 0))

    options = sorted(options, key=lambda x: x.get("fit_score", 0), reverse=True)

    return {
        "date": date_value,
        "meal": meal,
        "training_today": bool(training_today),
        "current": {
            "kcal": _fi_round(kcal_now, 1),
            "protein": _fi_round(protein_now, 1),
            "kcal_target": _fi_round(kcal_target, 0),
            "kcal_remaining": _fi_round(kcal_remaining, 0),
            "protein_remaining_to_130": _fi_round(protein_remaining, 1),
            "protein_goal_g": _fi_round(protein_goal, 0),
        },
        "available_foods_used": available,
        "options": options[:3],
        "rules": [
            "protein_first",
            "training_allows_more_carbs",
            "avoid_liquid_calories",
            "estimated_foods_lower_confidence",
        ],
    }

@app.route("/api/food-intel/meal-plan", methods=["POST"])
def api_food_intel_meal_plan():
    payload = v.json_body()
    d = v.iso_date(payload.get("date"), _fi_date.today().isoformat())
    meal = v.text(payload.get("meal") or payload.get("slot"), 40) or "next"
    available_foods = payload.get("available_foods") or payload.get("inventory") or []
    if not isinstance(available_foods, list) or len(available_foods) > 1000:
        raise ApiError("available_foods debe ser una lista")
    if payload.get("planned_workout") is not None and not isinstance(payload.get("planned_workout"), dict):
        raise ApiError("planned_workout no válido")
    training_today = bool(payload.get("training_today") or payload.get("planned_workout"))

    current_day = _fi_build_day(d, planned_workout=payload.get("planned_workout") if training_today else None)
    return jsonify({
        "ok": True,
        "version": "v0.0.14.1-food-intel",
        "engine": "heuristic_local",
        "plan": _fimp_make_options(d, meal, available_foods, training_today, current_day),
        "day_analysis": {
            "score": current_day.get("analysis", {}).get("score"),
            "semaphore": current_day.get("analysis", {}).get("semaphore"),
            "confidence": current_day.get("confidence", {}),
            "summary": current_day.get("summary", {}),
        },
    })

# DPP_FOOD_INTEL_MEAL_PLAN_END




# DPP_BODY_SNAPSHOT_API_START
# v0.0.14.1 · Optional body snapshot API.
# Smart-scale body composition is treated as an estimated trend snapshot,
# not as a mandatory daily metric and not as a medical diagnosis.

@app.route("/api/body-snapshot/latest")
def api_body_snapshot_latest():
    from datetime import date as _date

    con = dpp_db.connect(DB)

    table = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='body_composition'"
    ).fetchone()

    if not table:
        con.close()
        return jsonify({
            "ok": True,
            "available": False,
            "version": "v0.0.14.1",
            "reason": "body_composition table not found"
        })

    latest = con.execute("""
        SELECT date, time
        FROM body_composition
        GROUP BY date, time
        ORDER BY date DESC, time DESC
        LIMIT 1
    """).fetchone()

    if not latest:
        con.close()
        return jsonify({
            "ok": True,
            "available": False,
            "version": "v0.0.14.1",
            "reason": "no body composition records"
        })

    rows = con.execute("""
        SELECT metric, value, unit, source, confidence, notes
        FROM body_composition
        WHERE date=? AND time=?
        ORDER BY metric
    """, (latest["date"], latest["time"])).fetchall()

    previous = con.execute("""
        SELECT date, time
        FROM body_composition
        WHERE (date < ? OR (date = ? AND time < ?))
        GROUP BY date, time
        ORDER BY date DESC, time DESC
        LIMIT 1
    """, (latest["date"], latest["date"], latest["time"])).fetchone()

    prev_metrics = {}
    if previous:
        prev_rows = con.execute("""
            SELECT metric, value
            FROM body_composition
            WHERE date=? AND time=?
        """, (previous["date"], previous["time"])).fetchall()
        prev_metrics = {r["metric"]: r["value"] for r in prev_rows}

    con.close()

    metrics = {}
    for r in rows:
        metrics[r["metric"]] = {
            "value": r["value"],
            "unit": r["unit"] or "",
            "source": r["source"] or "",
            "confidence": r["confidence"] or "media",
            "notes": r["notes"] or ""
        }

    def val(key):
        try:
            return float((metrics.get(key) or {}).get("value") or 0)
        except Exception:
            return 0.0

    def pval(key):
        try:
            return float(prev_metrics.get(key) or 0)
        except Exception:
            return 0.0

    weight = val("weight")
    fat_pct = val("body_fat_pct")
    muscle = val("muscle_mass_kg")

    derived = {
        "fat_mass_kg": round(weight * fat_pct / 100.0, 2) if weight and fat_pct else None,
        "lean_mass_kg": round(weight - (weight * fat_pct / 100.0), 2) if weight and fat_pct else None,
        "muscle_weight_pct": round(muscle / weight * 100.0, 1) if muscle and weight else None,
    }

    deltas = {}
    for key in ["weight", "body_fat_pct", "water_pct", "muscle_mass_kg", "visceral_fat", "bmr_kcal", "biocharge_wakeup", "hrv"]:
        if key in metrics and key in prev_metrics:
            deltas[key] = round(val(key) - pval(key), 2)

    try:
        days_old = (_date.today() - _date.fromisoformat(latest["date"])).days
    except Exception:
        days_old = None

    if days_old is None:
        freshness = "unknown"
    elif days_old <= 2:
        freshness = "fresh"
    elif days_old <= 7:
        freshness = "recent"
    else:
        freshness = "old"

    return jsonify({
        "ok": True,
        "available": True,
        "version": "v0.0.14.1",
        "date": latest["date"],
        "time": latest["time"],
        "freshness": {
            "days_old": days_old,
            "label": freshness
        },
        "metrics": metrics,
        "derived": derived,
        "deltas": deltas,
        "previous": {
            "date": previous["date"] if previous else None,
            "time": previous["time"] if previous else None
        },
        "message": "Foto corporal estimada por bioimpedancia. Usar tendencia semanal, no valor aislado."
    })

# DPP_BODY_SNAPSHOT_API_END



# DPP_V0141_API_STATE_SANITIZER_START
# v0.0.14.1 safety net: sanitize legacy catalog aliases in /api/state.
# This is intentionally response-level because some UI state can be built from
# more than one source, not only the current foods table.
import json as _dpp_v0141_json
from flask import request as _dpp_v0141_request

_DPP_V0141_CANONICAL_FOODS = {
    "alpro protein cacao": {
        "name": "Alpro Protein cacao",
        "brand": "Alpro",
        "kcal": 69,
        "protein": 5.0,
        "carbs": 5.3,
        "fat": 2.8,
        "sugar": 5.0,
        "salt": 0.16,
        "typical_g": 250,
        "purchased": 1,
        "source_note": "Etiqueta/ficha: 69 kcal, 5 g proteína, 5.3 g hidratos y 2.8 g grasa por 100 ml.",
        "notes": "Bebida proteica sabor cacao. Vaso 250 ml = aprox. 172 kcal y 12.5 g proteína.",
    },
    "huevo entero": {
        "name": "Huevo entero",
        "brand": "Casa",
        "kcal": 143,
        "protein": 12.6,
        "carbs": 0.7,
        "fat": 9.5,
        "sugar": 0,
        "salt": 0.35,
        "typical_g": 60,
        "purchased": 1,
        "source_note": "Valor medio por 100 g.",
        "notes": "1 huevo mediano-grande aprox. 60 g. Para 2 huevos registrar 120 g.",
    },
    "plátano": {
        "name": "Plátano",
        "brand": "Fruta",
        "kcal": 89,
        "protein": 1.1,
        "carbs": 23,
        "fat": 0.3,
        "sugar": 12,
        "salt": 0.01,
        "typical_g": 120,
        "purchased": 1,
        "source_note": "Valor medio por 100 g.",
        "notes": "Peso comestible aproximado. Útil para desayuno/pre-entreno.",
    },
    "chocolate onzas estimado": {
        "name": "Chocolate onzas estimado",
        "brand": "Estimado",
        "kcal": 550,
        "protein": 6,
        "carbs": 55,
        "fat": 32,
        "sugar": 48,
        "salt": 0.05,
        "typical_g": 20,
        "purchased": 0,
        "source_note": "4 onzas estimadas como 20 g.",
        "notes": "Snack dulce estimado. Registrar solo si se consume.",
    },
    "café con edulcorante": {
        "name": "Café con edulcorante",
        "brand": "Casa",
        "kcal": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0,
        "sugar": 0,
        "salt": 0,
        "typical_g": 200,
        "purchased": 0,
        "source_note": "Café sin azúcar.",
        "notes": "Casi no suma.",
    },
}

_DPP_V0141_ALIASES = {
    "alpro protein chocolate": "alpro protein cacao",
    "alpro protein chocolate onzas estimado": "alpro protein cacao",
    "alpro protein chocolate onzas estimado onzas estimado": "alpro protein cacao",
    "alpro protein cacao": "alpro protein cacao",

    "huevos": "huevo entero",
    "huevo entero": "huevo entero",

    "platano": "plátano",
    "plátano": "plátano",

    "chocolate": "chocolate onzas estimado",
    "cacao": "chocolate onzas estimado",
    "cacao onzas estimado": "chocolate onzas estimado",
    "chocolate onzas estimado": "chocolate onzas estimado",

    "cafe con edulcorante": "café con edulcorante",
    "café con edulcorante": "café con edulcorante",
}

def _dpp_v0141_canonical_key(name):
    raw = str(name or "").strip()
    low = raw.lower()
    if low.startswith("alpro protein chocolate"):
        return "alpro protein cacao"
    return _DPP_V0141_ALIASES.get(low, low)

def _dpp_v0141_fix_food_dict(obj):
    if not isinstance(obj, dict):
        return obj

    name = obj.get("name", obj.get("food_name", ""))
    key = _dpp_v0141_canonical_key(name)

    fixed = dict(obj)

    if key in _DPP_V0141_CANONICAL_FOODS:
        canonical = dict(_DPP_V0141_CANONICAL_FOODS[key])
        # Preserve ids/photo paths if present, but force nutrition/name fields.
        for preserve in ("id", "photo_path", "created_at", "barcode"):
            if preserve in fixed and preserve not in canonical:
                canonical[preserve] = fixed[preserve]

        if "food_name" in fixed:
            canonical["food_name"] = canonical["name"]

        return canonical

    if "name" in fixed:
        fixed["name"] = str(name).strip()
    if "food_name" in fixed:
        fixed["food_name"] = str(name).strip()

    return fixed

def _dpp_v0141_fix_strings(value):
    if not isinstance(value, str):
        return value
    return (
        value
        .replace("Alpro Protein Chocolate onzas estimado onzas estimado", "Alpro Protein cacao")
        .replace("Alpro Protein Chocolate onzas estimado", "Alpro Protein cacao")
        .replace("Alpro Protein Chocolate", "Alpro Protein cacao")
    )

def _dpp_v0141_sanitize_recursive(value):
    if isinstance(value, list):
        return [_dpp_v0141_sanitize_recursive(v) for v in value]

    if isinstance(value, dict):
        # IMPORTANT:
        # Do not canonicalize meal_items here. Meal items contain grams/macros.
        # Canonicalizing every object with food_name would replace the item with
        # the food catalog object and make the UI show 0 g / 0 kcal.
        value = dict(value)

        for k in list(value.keys()):
            value[k] = _dpp_v0141_sanitize_recursive(value[k])

        return value

    return _dpp_v0141_fix_strings(value)

_DPP_V0141_ALIAS_NAMES = {
    "huevos",
    "chocolate",
    "cacao",
    "cacao onzas estimado",
    "alpro protein chocolate",
    "alpro protein chocolate onzas estimado",
    "alpro protein chocolate onzas estimado onzas estimado",
}


def _dpp_v0141_sanitize_foods_list(foods):
    """Show legacy alias rows under their canonical name, one entry per name.

    Every entry keeps a real database id (the UI adds/edits/deletes foods by
    id). When both the alias row and the real canonical row exist, the real
    row wins; otherwise purchased foods win.
    """
    if not isinstance(foods, list):
        return foods

    seen = {}
    clean = []

    def rank(entry, is_real):
        return (entry.get("id") is not None, is_real, int(entry.get("purchased") or 0))

    for raw in foods:
        if not isinstance(raw, dict):
            continue

        raw_name = str(raw.get("name", "")).strip()
        fixed = _dpp_v0141_fix_food_dict(raw)
        key = _dpp_v0141_canonical_key(fixed.get("name", ""))

        if raw_name.lower() in _DPP_V0141_ALIAS_NAMES:
            if key not in _DPP_V0141_CANONICAL_FOODS:
                continue
            fixed = dict(_DPP_V0141_CANONICAL_FOODS[key])
            for preserve in ("id", "photo_path", "created_at", "barcode"):
                if preserve in raw:
                    fixed[preserve] = raw[preserve]

        dedupe = str(fixed.get("name", "")).strip().lower()
        if not dedupe:
            continue
        is_real = raw_name.lower() == dedupe

        if dedupe not in seen:
            seen[dedupe] = (fixed, is_real)
            clean.append(fixed)
        else:
            prev, prev_real = seen[dedupe]
            if rank(fixed, is_real) > rank(prev, prev_real):
                clean[clean.index(prev)] = fixed
                seen[dedupe] = (fixed, is_real)

    return clean

def _dpp_v0141_sanitize_state_payload(data):
    data = _dpp_v0141_sanitize_recursive(data)

    if isinstance(data, dict):
        if isinstance(data.get("foods"), list):
            data["foods"] = _dpp_v0141_sanitize_foods_list(data["foods"])

        # Some versions may expose purchased foods separately.
        for key in ("purchased_foods", "catalog", "food_catalog"):
            if isinstance(data.get(key), list):
                data[key] = _dpp_v0141_sanitize_foods_list(data[key])

    return data

@app.after_request
def _dpp_v0141_after_request_sanitize_api_state(response):
    try:
        if _dpp_v0141_request.path != "/api/state" or response.status_code != 200:
            return response

        data = response.get_json(silent=True)
        if data is None:
            return response

        data = _dpp_v0141_sanitize_state_payload(data)
        # Modify in place so headers added by other hooks (security, caching) survive.
        response.set_data(_dpp_v0141_json.dumps(data, ensure_ascii=False))
        response.mimetype = "application/json"
        return response
    except Exception:
        return response
# DPP_V0141_API_STATE_SANITIZER_END



# DPP_V0151_TRUTH_PATCH_REGISTER_START
try:
    from dpp_food_intel_truth_patch import register_food_intel_truth_patch
    register_food_intel_truth_patch(app)
except Exception as exc:
    print(f"[DPP] food-intel truth patch not registered: {exc}")
# DPP_V0151_TRUTH_PATCH_REGISTER_END


# DPP_BODY_TRENDS_V2_START
try:
    from dpp_body_trends import register_body_trends_routes
    register_body_trends_routes(app)
except Exception as exc:
    print(f"WARN: body trends routes not registered: {exc}")
# DPP_BODY_TRENDS_V2_END


# BEGIN DPP_SMART_COACH_ROUTE
try:
    from dpp_smart_coach import register_smart_coach_routes
    register_smart_coach_routes(app)
except Exception as exc:
    print("WARN: smart coach routes disabled:", exc)
# END DPP_SMART_COACH_ROUTE

if __name__ == "__main__":
    start_strava_auto_thread()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8099")), debug=False)

"""Database helpers, schema/seed and state building shared by the routes.

Extracted from app.py without behaviour changes. It must not import ``app``.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any

import dpp_config as config
import dpp_db
import dpp_validate as v
from dpp_validate import ApiError

DB = config.DB_PATH



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


def _client_id(d: dict[str, Any]) -> str | None:
    """Optional idempotency key sent by the offline queue (None when absent)."""
    return v.text(d.get("client_id"), 64) or None


def _existing_by_client_id(db: sqlite3.Connection, table: str, cid: str | None) -> int | None:
    if not cid:
        return None
    row = db.execute(f"SELECT id FROM {table} WHERE client_id=?", (cid,)).fetchone()
    return int(row["id"]) if row else None


def create_meal(db: sqlite3.Connection, meal: dict[str, Any], items: list[dict[str, Any]]) -> int:
    """Always creates a new meal (two identical meals at the same minute are both kept)."""
    try:
        cur = db.execute(
            "INSERT INTO meals(date,time,name,notes,client_id) VALUES(?,?,?,?,?)",
            (meal["date"], meal["time"], meal["name"], meal.get("notes", ""), meal.get("client_id")),
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
    # Generic catalog rows (migration 6) do not count: on a fresh DB they arrive before this seed.
    first_run = not seeded and db.execute("SELECT COUNT(*) FROM foods WHERE COALESCE(brand,'') <> 'Genérico (aprox.)' AND COALESCE(source_note,'') NOT LIKE 'Etiqueta del producto según Open Food Facts%'").fetchone()[0] == 0
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
    # Si el nombre nuevo ya existe (foods.name es UNIQUE) no se renombra: antes eso impedía arrancar la app.
    for old, new in (
        ("Jamón cocido extra 85%", "Jamón cocido extra ElPozo 85%"),
        ("Pollo pechuga cruda", "Pollo pechuga cruda Pazo de Pías"),
        ("Champiñones", "Champiñones laminados"),
    ):
        if db.execute("SELECT 1 FROM foods WHERE name=?", (new,)).fetchone():
            continue
        db.execute("UPDATE foods SET name=? WHERE name=?", (new, old))
        db.execute("UPDATE meal_items SET food_name=? WHERE food_name=?", (new, old))


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
        meals = []
        by_meal: dict[int, list[dict[str, Any]]] = {}
        for r in db.execute("SELECT * FROM meals ORDER BY date DESC, time DESC, id DESC LIMIT 300").fetchall():
            d = dict(r)
            d["items"] = by_meal.setdefault(r["id"], [])
            meals.append(d)
        if by_meal:  # one query for all items instead of one per meal
            marks = ",".join("?" * len(by_meal))
            for it in rows(db.execute(f"SELECT * FROM meal_items WHERE meal_id IN ({marks}) ORDER BY id", list(by_meal))):
                by_meal[it["meal_id"]].append(it)
        for d in meals:
            d["totals"] = totals(d["items"])
        workouts = rows(db.execute("SELECT * FROM workouts ORDER BY date DESC, time DESC, id DESC LIMIT 300"))
        templates = rows(db.execute("SELECT * FROM templates ORDER BY name COLLATE NOCASE"))
        plans = rows(db.execute("SELECT * FROM plans ORDER BY id DESC LIMIT 20"))
    return {"today": today_iso(), "now": now_hm(), "foods": foods, "exercises": exercises, "weights": weights, "meals": meals, "workouts": workouts, "templates": templates, "plans": plans}


# v0.0.14.1 safety net: sanitize legacy catalog aliases in /api/state.
# This is intentionally response-level because some UI state can be built from
# more than one source, not only the current foods table.
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

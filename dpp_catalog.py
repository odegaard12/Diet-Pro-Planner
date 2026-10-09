"""Generic food catalog (approximate per-100 g values from public food-composition tables).

Added once by a database migration: only names that do not exist yet are inserted, so foods the
user created or edited are never touched. Branded products are not listed here on purpose (their
labels vary); use the barcode / Open Food Facts lookup or a label photo for those.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

NOTE = "Valor medio aproximado (tablas de composición). Ajusta con la etiqueta si la tienes."

# name, kcal, protein, carbs, fat, sugar, salt, typical portion (g)
_GENERIC: list[tuple[str, float, float, float, float, float, float, float]] = [
    # Carnes y pescados (crudo salvo indicación)
    ("Pechuga de pavo", 107, 24.0, 0.0, 1.0, 0.0, 0.15, 180),
    ("Ternera magra", 131, 21.0, 0.0, 5.0, 0.0, 0.15, 180),
    ("Carne picada mixta", 240, 18.0, 0.0, 18.5, 0.0, 0.2, 150),
    ("Lomo de cerdo", 152, 21.0, 0.0, 7.5, 0.0, 0.15, 150),
    ("Muslo de pollo sin piel", 120, 19.5, 0.0, 4.5, 0.0, 0.2, 150),
    ("Salmón", 208, 20.0, 0.0, 13.5, 0.0, 0.15, 150),
    ("Atún fresco", 130, 23.5, 0.0, 4.0, 0.0, 0.1, 150),
    ("Bacalao fresco", 78, 18.0, 0.0, 0.5, 0.0, 0.25, 200),
    ("Gambas peladas", 85, 19.0, 0.5, 1.0, 0.0, 0.6, 120),
    ("Sardinas en aceite (escurridas)", 210, 24.0, 0.0, 12.5, 0.0, 0.9, 80),
    ("Jamón serrano", 240, 30.0, 0.5, 13.0, 0.5, 4.5, 30),
    ("Pavo en lonchas", 100, 19.0, 2.0, 1.5, 1.5, 1.8, 60),
    # Huevos y lácteos
    ("Clara de huevo", 48, 11.0, 0.7, 0.2, 0.7, 0.42, 100),
    ("Leche semidesnatada", 46, 3.2, 4.7, 1.6, 4.7, 0.13, 250),
    ("Leche desnatada", 34, 3.4, 4.9, 0.1, 4.9, 0.13, 250),
    ("Yogur natural", 61, 3.5, 4.7, 3.2, 4.7, 0.13, 125),
    ("Yogur griego natural", 115, 5.0, 4.0, 9.0, 4.0, 0.13, 125),
    ("Skyr natural", 63, 11.0, 4.0, 0.2, 4.0, 0.1, 150),
    ("Queso fresco tipo Burgos", 170, 12.0, 3.0, 12.0, 3.0, 0.9, 60),
    ("Queso fresco batido 0%", 46, 8.0, 3.5, 0.2, 3.5, 0.1, 200),
    ("Requesón", 98, 11.0, 3.5, 4.3, 3.5, 0.4, 100),
    ("Queso curado", 400, 26.0, 0.5, 33.0, 0.5, 1.7, 30),
    ("Mozzarella", 250, 18.0, 1.0, 19.0, 1.0, 0.6, 60),
    ("Bebida de soja sin azúcar", 33, 3.3, 0.6, 1.8, 0.4, 0.1, 250),
    # Cereales, legumbres y tubérculos (en seco salvo indicación)
    ("Copos de avena", 370, 13.5, 59.0, 7.0, 1.0, 0.01, 50),
    ("Pan blanco", 265, 8.5, 50.0, 3.0, 3.0, 1.2, 60),
    ("Pan integral", 245, 9.5, 41.0, 3.5, 3.5, 1.1, 60),
    ("Arroz integral", 350, 7.5, 74.0, 2.7, 0.7, 0.01, 80),
    ("Quinoa", 368, 14.0, 64.0, 6.0, 0.0, 0.01, 70),
    ("Cuscús", 360, 13.0, 72.0, 1.5, 1.0, 0.02, 70),
    ("Garbanzos cocidos", 140, 7.0, 19.0, 2.5, 0.5, 0.3, 200),
    ("Lentejas cocidas", 116, 9.0, 16.0, 0.4, 1.8, 0.2, 200),
    ("Alubias cocidas", 115, 7.5, 16.0, 0.5, 0.5, 0.3, 200),
    ("Batata", 86, 1.6, 20.0, 0.1, 4.2, 0.1, 200),
    ("Patata cruda", 77, 2.0, 17.0, 0.1, 0.8, 0.01, 250),
    ("Tortilla de trigo", 310, 8.5, 50.0, 7.5, 2.5, 1.2, 60),
    # Verduras
    ("Brócoli", 34, 2.8, 4.0, 0.4, 1.7, 0.03, 200),
    ("Judías verdes", 31, 1.8, 4.5, 0.2, 3.3, 0.01, 250),
    ("Calabacín", 17, 1.2, 2.2, 0.3, 1.7, 0.01, 250),
    ("Espinacas", 23, 2.9, 1.4, 0.4, 0.4, 0.2, 150),
    ("Tomate", 18, 0.9, 3.0, 0.2, 2.6, 0.01, 150),
    ("Lechuga", 15, 1.4, 1.5, 0.2, 0.8, 0.02, 100),
    ("Pimiento rojo", 31, 1.0, 5.0, 0.3, 4.2, 0.01, 120),
    ("Cebolla", 40, 1.1, 8.0, 0.1, 4.2, 0.01, 80),
    ("Zanahoria", 41, 0.9, 8.0, 0.2, 4.7, 0.17, 100),
    ("Pepino", 15, 0.7, 2.5, 0.1, 1.7, 0.01, 150),
    # Frutas
    ("Fresas", 32, 0.7, 6.0, 0.3, 4.9, 0.0, 150),
    ("Arándanos", 57, 0.7, 12.0, 0.3, 10.0, 0.0, 100),
    ("Kiwi", 61, 1.1, 12.0, 0.5, 9.0, 0.0, 100),
    ("Pera", 57, 0.4, 13.0, 0.1, 10.0, 0.0, 180),
    ("Uvas", 69, 0.7, 17.0, 0.2, 16.0, 0.0, 150),
    ("Sandía", 30, 0.6, 7.5, 0.2, 6.2, 0.0, 300),
    ("Melón", 34, 0.8, 8.0, 0.2, 7.9, 0.03, 300),
    ("Aguacate", 160, 2.0, 2.0, 15.0, 0.7, 0.02, 70),
    # Frutos secos y otros
    ("Almendras", 580, 21.0, 9.0, 50.0, 4.4, 0.0, 25),
    ("Nueces", 650, 15.0, 7.0, 65.0, 2.6, 0.0, 25),
    ("Cacahuetes tostados", 590, 26.0, 13.0, 49.0, 4.0, 0.8, 25),
    ("Chocolate negro 85%", 600, 11.0, 15.0, 52.0, 11.0, 0.03, 20),
    ("Miel", 304, 0.3, 82.0, 0.0, 82.0, 0.01, 15),
    ("Proteína whey (polvo)", 390, 78.0, 6.0, 6.0, 4.0, 0.4, 30),
]

GENERIC_FOODS: list[dict] = [
    {"name": n, "brand": "Genérico (aprox.)", "kcal": k, "protein": p, "carbs": c, "fat": f,
     "sugar": s, "salt": sa, "typical_g": t, "purchased": 0, "source_note": NOTE, "notes": ""}
    for n, k, p, c, f, s, sa, t in _GENERIC
]


def add_missing(db: sqlite3.Connection) -> int:
    """Insert catalog foods whose name is not in the table yet; returns how many were added."""
    have = {row[0].strip().lower() for row in db.execute("SELECT name FROM foods")}
    cols = {row[1] for row in db.execute("PRAGMA table_info(foods)")}
    added = 0
    for food in GENERIC_FOODS:
        if food["name"].lower() in have:
            continue
        # Column names come from the fixed dict above, filtered by the real table columns.
        data = {k: v for k, v in food.items() if k in cols}
        keys = ", ".join(data)
        db.execute(f"INSERT INTO foods({keys}) VALUES({', '.join('?' for _ in data)})", tuple(data.values()))
        added += 1
    return added


SUPERMARKET_NOTE = "Etiqueta del producto según Open Food Facts (ODbL). Revisa si cambia la receta."
_ES_PATH = Path(__file__).with_name("dpp_catalog_es.json")


def supermarket_foods() -> list[dict]:
    """Spanish supermarket own-brand products: [name, brand, barcode, kcal, prot, carbs, fat, sugar, salt, portion]."""
    rows = json.loads(_ES_PATH.read_text(encoding="utf-8"))
    # foods.name is UNIQUE, so the short brand goes in the name too ("Tomate frito · Consum").
    return [
        {"name": f"{n} · {b.split(' (')[0]}", "brand": b, "barcode": code, "kcal": k, "protein": p, "carbs": c, "fat": f,
         "sugar": s, "salt": sa, "typical_g": t, "purchased": 0, "source_note": SUPERMARKET_NOTE, "notes": ""}
        for n, b, code, k, p, c, f, s, sa, t in rows
    ]


def add_supermarket(db: sqlite3.Connection) -> int:
    """Insert supermarket products whose barcode (or name) is not in the table yet."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(foods)")}
    has_code = "barcode" in cols
    codes = {r[0] for r in db.execute("SELECT barcode FROM foods")} if has_code else set()
    named = {r[0].strip().lower() for r in db.execute("SELECT name FROM foods")}
    added = 0
    for food in supermarket_foods():
        if food["barcode"] in codes or food["name"].lower() in named:
            continue
        named.add(food["name"].lower())
        data = {k: v for k, v in food.items() if k in cols}
        keys = ", ".join(data)
        db.execute(f"INSERT INTO foods({keys}) VALUES({', '.join('?' for _ in data)})", tuple(data.values()))
        added += 1
    return added

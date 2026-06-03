import os
import sqlite3
from pathlib import Path

DB = Path(os.environ.get("DPP_DB", "data/dieta.db"))

if not DB.exists():
    raise SystemExit(f"No existe DB: {DB}")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def table_exists(name):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    ).fetchone() is not None

if not table_exists("foods"):
    raise SystemExit(f"La DB no tiene tabla foods: {DB}")

def ensure_food(name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g, purchased, source_note, notes):
    row = con.execute(
        "SELECT id FROM foods WHERE lower(name)=lower(?) ORDER BY id ASC LIMIT 1",
        (name,)
    ).fetchone()

    if row:
        fid = row["id"]
    else:
        cur = con.execute("""
            INSERT INTO foods(name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g, purchased, source_note, notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g, purchased, source_note, notes))
        fid = cur.lastrowid

    con.execute("""
        UPDATE foods
        SET name=?, brand=?, kcal=?, protein=?, carbs=?, fat=?, sugar=?, salt=?,
            typical_g=?, purchased=?, source_note=?, notes=?
        WHERE id=?
    """, (name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g, purchased, source_note, notes, fid))
    return fid

def delete_food_exact(name):
    con.execute("DELETE FROM foods WHERE lower(name)=lower(?)", (name,))

def delete_duplicate_canonicals(name):
    rows = con.execute(
        "SELECT id FROM foods WHERE lower(name)=lower(?) ORDER BY id ASC",
        (name,)
    ).fetchall()
    if len(rows) <= 1:
        return
    keep = rows[0]["id"]
    for r in rows[1:]:
        con.execute("DELETE FROM foods WHERE id=?", (r["id"],))

def replace_meal_item(old, new):
    if table_exists("meal_items"):
        con.execute("UPDATE meal_items SET food_name=? WHERE food_name=?", (new, old))

def replace_meal_item_like(pattern, new):
    if table_exists("meal_items"):
        con.execute("UPDATE meal_items SET food_name=? WHERE food_name LIKE ?", (new, pattern))

def replace_notes_0306(old, new):
    if table_exists("meals"):
        con.execute(
            "UPDATE meals SET notes=replace(notes, ?, ?) WHERE date='2026-06-03'",
            (old, new)
        )

# 1) Crear/forzar canonicales buenos.
ensure_food(
    "Alpro Protein cacao", "Alpro",
    69, 5.0, 5.3, 2.8, 5.0, 0.16, 250, 1,
    "Etiqueta/ficha: 69 kcal, 5 g proteína, 5.3 g hidratos y 2.8 g grasa por 100 ml.",
    "Bebida proteica sabor cacao. Vaso 250 ml = aprox. 172 kcal y 12.5 g proteína."
)

ensure_food(
    "Huevo entero", "Casa",
    143, 12.6, 0.7, 9.5, 0, 0.35, 60, 1,
    "Valor medio por 100 g.",
    "1 huevo mediano-grande aprox. 60 g. Para 2 huevos registrar 120 g."
)

ensure_food(
    "Plátano", "Fruta",
    89, 1.1, 23, 0.3, 12, 0.01, 120, 1,
    "Valor medio por 100 g.",
    "Peso comestible aproximado. Útil para desayuno/pre-entreno."
)

ensure_food(
    "Chocolate onzas estimado", "Estimado",
    550, 6, 55, 32, 48, 0.05, 20, 0,
    "4 onzas estimadas como 20 g.",
    "Snack dulce estimado. Registrar solo si se consume."
)

ensure_food(
    "Café con edulcorante", "Casa",
    0, 0, 0, 0, 0, 0, 200, 0,
    "Café sin azúcar.",
    "Casi no suma."
)

# 2) Reasignar referencias antiguas exactas.
replace_meal_item_like("Alpro Protein%", "Alpro Protein cacao")
replace_meal_item("Huevos", "Huevo entero")
replace_meal_item("Platano", "Plátano")
replace_meal_item("Chocolate", "Chocolate onzas estimado")
replace_meal_item("cacao", "Chocolate onzas estimado")
replace_meal_item("cacao onzas estimado", "Chocolate onzas estimado")

# 3) Limpiar notas SOLO del día afectado, para no romper textos históricos.
for old in [
    "Alpro Protein Chocolate onzas estimado onzas estimado",
    "Alpro Protein Chocolate onzas estimado",
    "Alpro Protein Chocolate",
]:
    replace_notes_0306(old, "Alpro Protein cacao")

# 4) Borrar alias exactos del catálogo. No se toca nada parcial.
for bad in [
    "Huevos",
    "Chocolate",
    "cacao",
    "cacao onzas estimado",
    "Alpro Protein Chocolate",
    "Alpro Protein Chocolate onzas estimado",
    "Alpro Protein Chocolate onzas estimado onzas estimado",
]:
    delete_food_exact(bad)

# 5) Borrar duplicados exactos de canonicales.
for good in [
    "Alpro Protein cacao",
    "Huevo entero",
    "Plátano",
    "Chocolate onzas estimado",
    "Café con edulcorante",
]:
    delete_duplicate_canonicals(good)

con.commit()

print(f"== DB corregida: {DB} ==")
for pat in ["Alpro", "Huevo", "Plátano", "Chocolate", "Café"]:
    print(f"\n-- {pat}")
    rows = con.execute(
        "SELECT id,name,kcal,protein,typical_g,purchased FROM foods WHERE name LIKE ? ORDER BY name,id",
        (f"%{pat}%",)
    ).fetchall()
    for r in rows:
        print(dict(r))

con.close()

import sqlite3
from pathlib import Path

DB = Path("data/dieta.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def food_id(name):
    row = con.execute(
        "SELECT id FROM foods WHERE lower(name)=lower(?) ORDER BY id ASC LIMIT 1",
        (name,)
    ).fetchone()
    return row["id"] if row else None

def ensure_food(name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g, purchased, source_note, notes):
    fid = food_id(name)
    if fid is None:
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

# Canonicales correctos.
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

# Referencias exactas antiguas.
con.execute("UPDATE meal_items SET food_name='Huevo entero' WHERE food_name='Huevos'")
con.execute("UPDATE meal_items SET food_name='Plátano' WHERE food_name='Platano'")
con.execute("UPDATE meal_items SET food_name='Alpro Protein cacao' WHERE food_name LIKE 'Alpro Protein%'")
con.execute("UPDATE meal_items SET food_name='Chocolate onzas estimado' WHERE food_name IN ('Chocolate','cacao','cacao onzas estimado')")

# Notas del día actual: quitar falso chocolate del Alpro.
con.execute("""
UPDATE meals
SET notes=replace(notes, 'Alpro Protein Chocolate onzas estimado onzas estimado', 'Alpro Protein cacao')
WHERE date='2026-06-03'
""")
con.execute("""
UPDATE meals
SET notes=replace(notes, 'Alpro Protein Chocolate onzas estimado', 'Alpro Protein cacao')
WHERE date='2026-06-03'
""")
con.execute("""
UPDATE meals
SET notes=replace(notes, 'Alpro Protein Chocolate', 'Alpro Protein cacao')
WHERE date='2026-06-03'
""")

# Borrar aliases exactos del catálogo, no textos parciales.
for bad in [
    "Huevos",
    "Chocolate",
    "cacao",
    "cacao onzas estimado",
    "Alpro Protein Chocolate",
    "Alpro Protein Chocolate onzas estimado",
    "Alpro Protein Chocolate onzas estimado onzas estimado",
]:
    con.execute("DELETE FROM foods WHERE lower(name)=lower(?)", (bad,))

# Eliminar duplicados exactos de canonicales.
for name in ["Alpro Protein cacao", "Huevo entero", "Plátano", "Chocolate onzas estimado", "Café con edulcorante"]:
    rows = con.execute("SELECT id FROM foods WHERE lower(name)=lower(?) ORDER BY id ASC", (name,)).fetchall()
    if len(rows) > 1:
        keep = rows[0]["id"]
        for r in rows[1:]:
            con.execute("DELETE FROM foods WHERE id=?", (r["id"],))

con.commit()

print("== Verificación final ==")
for pat in ["Alpro", "Huevo", "Plátano", "Chocolate", "Café"]:
    print("\\n--", pat)
    for r in con.execute(
        "SELECT id,name,kcal,protein,typical_g,purchased FROM foods WHERE name LIKE ? ORDER BY name,id",
        (f"%{pat}%",)
    ):
        print(dict(r))

con.close()

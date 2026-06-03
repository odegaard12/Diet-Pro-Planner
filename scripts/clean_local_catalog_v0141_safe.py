import sqlite3
from pathlib import Path

DB = Path("data/dieta.db")

def q(name):
    return '"' + str(name).replace('"', '""') + '"'

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def tables():
    return [r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]

def cols(table):
    return [r["name"] for r in con.execute(f"PRAGMA table_info({q(table)})")]

def replace_text(old, new):
    for table in tables():
        for col in cols(table):
            try:
                con.execute(
                    f"UPDATE {q(table)} SET {q(col)}=replace({q(col)}, ?, ?) "
                    f"WHERE CAST({q(col)} AS TEXT) LIKE ?",
                    (old, new, f"%{old}%")
                )
            except Exception:
                pass

def set_food(name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g, source_note, notes, purchased=1):
    row = con.execute(
        "SELECT id FROM foods WHERE lower(name)=lower(?) ORDER BY purchased DESC, id ASC LIMIT 1",
        (name,)
    ).fetchone()

    if row:
        con.execute("""
            UPDATE foods
            SET name=?, brand=?, kcal=?, protein=?, carbs=?, fat=?, sugar=?, salt=?,
                typical_g=?, purchased=?, source_note=?, notes=?
            WHERE id=?
        """, (name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g,
              purchased, source_note, notes, row["id"]))
        return row["id"]

    cur = con.execute("""
        INSERT INTO foods(name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g, purchased, source_note, notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g,
          purchased, source_note, notes))
    return cur.lastrowid

def merge_food_alias(canonical, aliases, keep_values=None):
    keep = con.execute(
        "SELECT id FROM foods WHERE lower(name)=lower(?) ORDER BY purchased DESC, id ASC LIMIT 1",
        (canonical,)
    ).fetchone()

    if not keep:
        for a in aliases:
            r = con.execute(
                "SELECT id FROM foods WHERE lower(name)=lower(?) ORDER BY purchased DESC, id ASC LIMIT 1",
                (a,)
            ).fetchone()
            if r:
                con.execute("UPDATE foods SET name=? WHERE id=?", (canonical, r["id"]))
                keep = r
                break

    if not keep:
        return

    keep_id = keep["id"]

    for a in aliases:
        replace_text(a, canonical)
        con.execute("DELETE FROM foods WHERE lower(name)=lower(?) AND id<>?", (a, keep_id))

    con.execute("DELETE FROM foods WHERE lower(name)=lower(?) AND id<>?", (canonical, keep_id))

    if keep_values:
        con.execute("""
            UPDATE foods
            SET brand=?, kcal=?, protein=?, carbs=?, fat=?, sugar=?, salt=?,
                typical_g=?, purchased=?, source_note=?, notes=?
            WHERE id=?
        """, (*keep_values, keep_id))

# 1) Reparaciones de texto concretas, no globales peligrosas.
specific = [
    ("Alpro Protein Chocolate onzas estimado onzas estimado", "Alpro Protein cacao"),
    ("Alpro Protein Chocolate onzas estimado", "Alpro Protein cacao"),
    ("vaso Alpro Protein Chocolate onzas estimado onzas estimado", "vaso Alpro Protein cacao"),
    ("vaso Alpro Protein Chocolate onzas estimado", "vaso Alpro Protein cacao"),
    ("sabor Chocolate onzas estimado onzas estimado", "sabor cacao"),
    ("sabor Chocolate onzas estimado", "sabor cacao"),
    ("Chocolate onzas estimado onzas estimado", "Chocolate onzas estimado"),
    ("Galletas pequeñas con Chocolate onzas estimado estimadas", "Galletas pequeñas con cacao estimadas"),
]
for old, new in specific:
    replace_text(old, new)

# 2) Alpro correcto.
set_food(
    "Alpro Protein cacao",
    "Alpro",
    69, 5.0, 5.3, 2.8, 5.0, 0.16, 250,
    "Etiqueta/ficha: 69 kcal, 5 g proteína, 5.3 g hidratos y 2.8 g grasa por 100 ml.",
    "Bebida proteica sabor cacao. Vaso 250 ml = aprox. 172 kcal y 12.5 g proteína.",
    1
)

# Borrar variantes corruptas de Alpro tras mover referencias.
for bad in [
    "Alpro Protein Chocolate onzas estimado",
    "Alpro Protein Chocolate onzas estimado onzas estimado",
]:
    con.execute("UPDATE meal_items SET food_name='Alpro Protein cacao' WHERE lower(food_name)=lower(?)", (bad,))
    con.execute("DELETE FROM foods WHERE lower(name)=lower(?)", (bad,))

# 3) Chocolate/cacao: dejar solo un alimento dulce canonical.
merge_food_alias(
    "Chocolate onzas estimado",
    [
        "Chocolate",
        "cacao",
        "cacao onzas estimado",
        "Chocolate onzas estimado",
        "Chocolate onzas estimado onzas estimado",
    ],
    keep_values=(
        "Estimado", 550, 6, 55, 32, 48, 0.05, 20, 1,
        "4 onzas estimadas como 20 g.",
        "Snack dulce estimado. Registrar solo si se consume."
    )
)

# 4) Galletas con cacao.
merge_food_alias(
    "Galletas pequeñas con cacao estimadas",
    [
        "Galletas pequeñas con Chocolate onzas estimado estimadas",
        "Galletas pequeñas con cacao estimadas",
    ],
    keep_values=(
        "Estimado", 480, 6, 68, 20, 28, 0.4, 18, 0,
        "3 galletas pequeñas estimadas como 18 g.",
        "Snack dulce nocturno estimado."
    )
)

# 5) Huevos: dejar solo Huevo entero.
merge_food_alias(
    "Huevo entero",
    ["Huevos", "Huevo entero"],
    keep_values=(
        "Casa", 143, 12.6, 0.7, 9.5, 0, 0.35, 60, 1,
        "Valor medio por 100 g.",
        "1 huevo mediano-grande aprox. 60 g. Para 2 huevos registrar 120 g."
    )
)

# 6) Plátano: dejar uno.
merge_food_alias(
    "Plátano",
    ["Platano", "Plátano"],
    keep_values=(
        "Fruta", 89, 1.1, 23, 0.3, 12, 0.01, 120, 1,
        "Valor medio por 100 g.",
        "Peso comestible aproximado. Útil para desayuno/pre-entreno."
    )
)

# 7) Café a 0 real.
merge_food_alias(
    "Café con edulcorante",
    ["Cafe con edulcorante", "Café con edulcorante"],
    keep_values=(
        "Casa", 0, 0, 0, 0, 0, 0, 200, 0,
        "Café sin azúcar.",
        "Casi no suma."
    )
)

# 8) Guisantes único.
merge_food_alias(
    "Guisantes",
    ["Guisantes cocidos", "Guisantes"],
    keep_values=(
        "Casa", 81, 5.4, 14, 0.4, 5.7, 0.02, 100, 1,
        "Valor medio por 100 g.",
        "Verdura/legumbre fácil."
    )
)

# 9) Limpiar nombres antiguos en template text.
for old, new in [
    ("Huevos", "Huevo entero"),
    ("Alpro Protein Chocolate", "Alpro Protein cacao"),
    ("cacao onzas estimado", "Chocolate onzas estimado"),
]:
    replace_text(old, new)

con.commit()

print("== Duplicados exactos restantes ==")
dups = con.execute("""
    SELECT lower(name) k, COUNT(*) n, group_concat(id || ':' || name, ' | ') names
    FROM foods
    GROUP BY lower(name)
    HAVING COUNT(*) > 1
    ORDER BY n DESC, k
""").fetchall()
if not dups:
    print("Sin duplicados exactos.")
else:
    for r in dups:
        print(dict(r))

print()
print("== Alimentos corregidos ==")
for r in con.execute("""
    SELECT id, name, brand, kcal, protein, typical_g, purchased
    FROM foods
    WHERE name IN (
      'Alpro Protein cacao',
      'Chocolate onzas estimado',
      'Galletas pequeñas con cacao estimadas',
      'Huevo entero',
      'Plátano',
      'Café con edulcorante',
      'Guisantes'
    )
    ORDER BY name
"""):
    print(dict(r))

con.close()

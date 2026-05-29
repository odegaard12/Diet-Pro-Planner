"""Migración local privada de Óscar v9.
No subir a GitHub. Este archivo queda excluido al publicar.

Objetivo:
- Ordenar lunes/martes/miércoles/jueves sin mezclar días.
- Eliminar el peso erróneo 85,95.
- Mantener pesos reales confirmados.
- Añadir comidas reales/planificadas confirmadas en el chat.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "dieta.db"


def con():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def food(db, name: str):
    r = db.execute("SELECT * FROM foods WHERE name=?", (name,)).fetchone()
    if not r:
        raise RuntimeError(f"No existe alimento: {name}")
    return dict(r)


def item(f: dict, grams: float):
    k = float(grams) / 100.0
    return (
        f["id"], f["name"], round(float(grams), 1),
        round(float(f["kcal"]) * k, 1), round(float(f["protein"]) * k, 1),
        round(float(f["carbs"] or 0) * k, 1), round(float(f["fat"] or 0) * k, 1),
        round(float(f["sugar"] or 0) * k, 1), round(float(f["salt"] or 0) * k, 2),
    )


def delete_meal_at(db, date: str, time: str, name: str | None = None):
    if name:
        rs = db.execute("SELECT id FROM meals WHERE date=? AND time=? AND name=?", (date, time, name)).fetchall()
    else:
        rs = db.execute("SELECT id FROM meals WHERE date=? AND time=?", (date, time)).fetchall()
    for r in rs:
        db.execute("DELETE FROM meals WHERE id=?", (r["id"],))


def insert_meal(db, date: str, time: str, name: str, notes: str, pairs: list[tuple[str, float]]):
    delete_meal_at(db, date, time, name)
    db.execute("INSERT INTO meals(date,time,name,notes) VALUES(?,?,?,?)", (date, time, name, notes))
    meal_id = db.execute("SELECT last_insert_rowid() id").fetchone()["id"]
    for n, grams in pairs:
        it = item(food(db, n), float(grams))
        db.execute(
            """INSERT INTO meal_items(meal_id,food_id,food_name,grams,kcal,protein,carbs,fat,sugar,salt)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (meal_id, *it),
        )


def insert_weight(db, date: str, time: str, kg: float, official: bool, context: str):
    db.execute("DELETE FROM weights WHERE date=? AND time=?", (date, time))
    db.execute(
        "INSERT INTO weights(date,time,kg,official,context) VALUES(?,?,?,?,?)",
        (date, time, kg, 1 if official else 0, context),
    )


def insert_workout(db, date: str, time: str, name: str, minutes: float, km: float, kcal: float, notes: str):
    db.execute("DELETE FROM workouts WHERE date=? AND time=? AND name=?", (date, time, name))
    ex = db.execute("SELECT id FROM exercises WHERE name=?", (name,)).fetchone()
    db.execute(
        "INSERT INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes) VALUES(?,?,?,?,?,?,?,?)",
        (date, time, ex["id"] if ex else None, name, minutes, km, kcal, notes),
    )


def save_plan(db):
    db.execute("DELETE FROM plans WHERE name LIKE 'Plan real 25-28 mayo%'")
    plan = {
        "name": "Plan real 25-28 mayo · ordenado",
        "notes": "Privado. Martes 26 = lentejas + patata/guisantes + actividad. Miércoles 27 = pollo/pasta. Jueves 28 = tupper frío + partido.",
        "days": [
            {
                "day": "Lunes 25 · cena estimada",
                "breakfast": "No registrado",
                "lunch": "No registrado",
                "snack": "Sándwich tostado de jamón + 3 onzas de chocolate; luego 20 min bici estática",
                "dinner": "Merluza + patata + guisantes. Registro estimado porque no se pesó exacto.",
            },
            {
                "day": "Martes 26 · lentejas y restos",
                "breakfast": "Tostada + 15 g crema cacahuete + yogur proteico, sin plátano",
                "lunch": "Lentejas con chorizo + gelatina 0",
                "snack": "Manzana + yogur proteico",
                "dinner": "250 g lentejas + 630 g patata/guisantes + 20 g aceite. Actividad ese día: core, cinta y paseo perro.",
            },
            {
                "day": "Miércoles 27 · pollo dividido 2+2+2",
                "breakfast": "Tostada + 15 g crema cacahuete + plátano + yogur proteico + café con edulcorante",
                "lunch": "80 g pasta seca + 2 piezas pollo + 120 g champiñones + 5 g aceite",
                "snack": "Fruta + yogur proteico",
                "dinner": "2 piezas pollo + 100 g champiñones + gelatina 0 opcional; sin pasta ni pan",
            },
            {
                "day": "Jueves 28 · Santiago + partido 18:00",
                "breakfast": "Tostada + 15 g crema cacahuete + yogur proteico + café con edulcorante",
                "lunch": "Tupper frío: 80 g pasta seca + 2 piezas pollo + 5 g aceite/especias + yogur aparte",
                "snack": "17:15-17:30: plátano antes del partido. Si no hay plátano: 2-3 tortitas de maíz.",
                "dinner": "Registrar real al llegar. Mejor ligera: huevos/atún/jamón + gelatina si apetece.",
            },
        ],
    }
    db.execute("INSERT INTO plans(name,payload) VALUES(?,?)", (plan["name"], json.dumps(plan, ensure_ascii=False)))


def main():
    if not DB.exists():
        raise SystemExit(f"No existe DB: {DB}")
    with con() as db:
        # Limpieza de errores conocidos y rangos que vamos a reordenar.
        db.execute("DELETE FROM weights WHERE abs(kg - 85.95) < 0.001")
        db.execute("DELETE FROM weights WHERE date='2026-05-27' AND time='14:30'")

        # Borramos comidas de estos días para reinsertar ordenadas y evitar duplicados.
        for d in ("2026-05-25", "2026-05-26", "2026-05-27", "2026-05-28"):
            ids = db.execute("SELECT id FROM meals WHERE date=?", (d,)).fetchall()
            for r in ids:
                db.execute("DELETE FROM meals WHERE id=?", (r["id"],))
        for d in ("2026-05-25", "2026-05-26", "2026-05-27", "2026-05-28"):
            db.execute("DELETE FROM workouts WHERE date=?", (d,))

        # Pesos confirmados. Sin 85,95.
        insert_weight(db, "2026-05-26", "18:00", 86.40, False, "martes tarde, referencia")
        insert_weight(db, "2026-05-26", "23:52", 87.20, False, "martes después de cenar, referencia")
        insert_weight(db, "2026-05-27", "09:15", 86.70, True, "miércoles mañana, después baño, peso oficial inicial")
        insert_weight(db, "2026-05-27", "13:08", 86.90, False, "miércoles después de desayunar, referencia")

        # LUNES 25: estimado a partir del chat. Marcado como estimado en notas.
        insert_meal(db, "2026-05-25", "18:30", "Merienda", "Estimado: sándwich tostado con jamón + 3 onzas de chocolate", [
            ("Pan centeno/integral rebanada", 84),
            ("Jamón cocido extra ElPozo 85%", 80),
            ("Chocolate", 30),
        ])
        insert_workout(db, "2026-05-25", "20:00", "Bici estática suave", 20, 0, 90, "Bici estática 20 min")
        insert_meal(db, "2026-05-25", "22:00", "Cena", "Estimado: merluza con patata y guisantes; cena ligera tras merienda fuerte", [
            ("Merluza cocida", 200),
            ("Patata + guisantes guisados", 250),
            ("Aceite de oliva", 5),
        ])

        # MARTES 26: lentejas + patatas/guisantes + actividad. Este era el día de la captura del reloj.
        insert_meal(db, "2026-05-26", "10:30", "Desayuno", "Tostada + 15 g crema cacahuete + yogur proteico; sin plátano", [
            ("Pan centeno/integral rebanada", 42),
            ("Crema de cacahuete", 15),
            ("Yogur Eroski +Proteína 120 g", 120),
            ("Café con edulcorante", 200),
        ])
        insert_meal(db, "2026-05-26", "13:20", "Pre-comida", "Gelatina 0 por hambre antes de comer", [
            ("Gelatina 0 Clesa", 90),
        ])
        insert_meal(db, "2026-05-26", "14:30", "Comida", "Lentejas con chorizo, ración estimada; sin pan", [
            ("Lentejas guisadas", 350),
            ("Chorizo", 25),
            ("Gelatina 0 Clesa", 90),
        ])
        insert_meal(db, "2026-05-26", "18:15", "Merienda", "Manzana + yogur proteico antes de actividad", [
            ("Manzana", 180),
            ("Yogur Eroski +Proteína 120 g", 120),
        ])
        insert_workout(db, "2026-05-26", "18:59", "Core + movilidad", 34, 0, 230, "Registro reloj: troncal")
        insert_workout(db, "2026-05-26", "19:35", "Cinta andando", 10, 0.94, 50, "Cinta")
        insert_workout(db, "2026-05-26", "19:46", "Core + movilidad", 10, 0, 80, "Registro reloj: troncal")
        insert_workout(db, "2026-05-26", "21:53", "Paseo perro", 44, 3.40, 150, "Paseo perro")
        insert_meal(db, "2026-05-26", "23:28", "Cena restos", "250 g lentejas + 650 g patata/guisantes con aceite incluido; aceite aprox. 20 g. Martes, no miércoles.", [
            ("Lentejas guisadas", 250),
            ("Patata + guisantes guisados", 630),
            ("Aceite de oliva", 20),
        ])

        # MIÉRCOLES 27: día actual del pollo/pasta.
        insert_meal(db, "2026-05-27", "10:30", "Desayuno", "Tostada pan centeno/integral + plátano + café con edulcorante + yogur proteico", [
            ("Pan centeno/integral rebanada", 42),
            ("Crema de cacahuete", 15),
            ("Plátano", 120),
            ("Yogur Eroski +Proteína 120 g", 120),
            ("Café con edulcorante", 200),
        ])
        insert_meal(db, "2026-05-27", "14:15", "Comida", "Foto plato: 80 g pasta seca + 2 piezas pollo + 120 g champiñones + 5 g aceite; pollo dividido 2+2+2", [
            ("Pasta seca", 80),
            ("Pollo pechuga cruda Pazo de Pías", 224),
            ("Champiñones laminados", 120),
            ("Aceite de oliva", 5),
        ])
        insert_meal(db, "2026-05-27", "18:15", "Merienda", "Planificada: fruta + yogur proteico; cambiar manzana por plátano si fue plátano", [
            ("Manzana", 180),
            ("Yogur Eroski +Proteína 120 g", 120),
        ])
        insert_meal(db, "2026-05-27", "22:30", "Cena", "Planificada: 2 piezas pollo + 100 g champiñones + gelatina opcional. Sin pasta, sin pan, sin yogur.", [
            ("Pollo pechuga cruda Pazo de Pías", 224),
            ("Champiñones laminados", 100),
            ("Gelatina 0 Clesa", 90),
        ])

        # JUEVES 28: Santiago + partido 18:00. Planificado.
        insert_meal(db, "2026-05-28", "09:00", "Desayuno", "Planificado: tostada + 15 g crema cacahuete + yogur proteico + café con edulcorante", [
            ("Pan centeno/integral rebanada", 42),
            ("Crema de cacahuete", 15),
            ("Yogur Eroski +Proteína 120 g", 120),
            ("Café con edulcorante", 200),
        ])
        insert_meal(db, "2026-05-28", "16:00", "Comida tupper", "Planificado Santiago: tupper frío de pasta + pollo + aceite/especias. Yogur aparte.", [
            ("Pasta seca", 80),
            ("Pollo pechuga cruda Pazo de Pías", 224),
            ("Aceite de oliva", 5),
            ("Yogur Eroski +Proteína 120 g", 120),
        ])
        insert_meal(db, "2026-05-28", "17:20", "Pre-partido", "Planificado antes del partido de las 18:00: plátano. Si no hay, 2-3 tortitas de maíz.", [
            ("Plátano", 120),
        ])

        save_plan(db)
        db.commit()
    print("Migración v9 aplicada: lunes/martes/miércoles/jueves ordenados, pesos corregidos y martes de lentejas/patatas bien fechado.")


if __name__ == "__main__":
    main()

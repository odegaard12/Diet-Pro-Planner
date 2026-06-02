# Food Intelligence Audit

Database: `/home/odegaard12/Diet-Pro-Planner/data/dieta.db`

## Tables

- `exercises`: 9 rows
- `foods`: 54 rows
- `meal_items`: 99 rows
- `meals`: 36 rows
- `plans`: 3 rows
- `sqlite_sequence`: 8 rows
- `templates`: 16 rows
- `weights`: 5 rows
- `workouts`: 13 rows

## Foods

- Exists: True
- Count: 54
- Columns: id, name, brand, kcal, protein, carbs, fat, sugar, salt, typical_g, purchased, source_note, notes, created_at, photo_path

### Estimated or composite food samples

- Jamón cocido extra ElPozo 85%
- Patata + guisantes guisados
- Lentejas guisadas
- Barrita Tirma estimada
- Judia verde plana Eliges
- Jamon cocido extra etiqueta
- Queso Larsa clasico cremoso
- Chocolate onzas estimado
- Piruleta estimada
- Galletas peque?as con chocolate estimadas

### Missing macro samples

- None detected.

## Daily data

- `meals`: exists=True count=36 last_14_days=36
- `workouts`: exists=True count=13 last_14_days=13
- `weights`: exists=True count=5 last_14_days=5

## Broken text samples

- foods.name rowid=477: Galletas peque?as con chocolate estimadas
- foods.source_note rowid=477: 3 galletas peque?as estimadas 18 g.
- foods.source_note rowid=836: Estimaci?n churrasco/asador.
- foods.source_note rowid=837: Patatas de comida libre; estimaci?n.
- foods.notes rowid=836: Estimaci?n churrasco/asador.
- foods.notes rowid=837: Patatas de comida libre; estimaci?n.
- meal_items.food_name rowid=100: Galletas peque?as con chocolate estimadas
- meals.notes rowid=37: 3 galletas peque?as con algo de chocolate.
- meals.notes rowid=42: Churrasco con patatas hasta quedar lleno. Estimaci?n generosa.

## Next implementation

1. Add derived food confidence scoring.
2. Add local source cache tables.
3. Implement `/api/food-intel/day` without changing UI.
4. Add tests for daily score and confidence.
5. Add UI only after endpoint is stable.
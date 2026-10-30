"""Built-in recipes: every ingredient exists in the catalog, the numbers make sense and loading is non-destructive."""
from __future__ import annotations

import json
import sqlite3
import unittest

import _env  # noqa: F401  (isolated data dir + auth token; must come first)

import dpp_catalog
import dpp_recipes

FOODS = {f["name"]: f for f in dpp_catalog.GENERIC_FOODS}


class RecipeCatalogTests(unittest.TestCase):
    def test_enough_unique_recipes_in_every_category(self) -> None:
        names = [r[0].lower() for r in dpp_recipes.RECIPES]
        self.assertGreaterEqual(len(names), 130)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual({r[1] for r in dpp_recipes.RECIPES}, set(dpp_recipes.CATEGORIES))

    def test_every_ingredient_exists_and_amounts_are_sane(self) -> None:
        for name, category, steps, items in dpp_recipes.RECIPES:
            self.assertTrue(items, name)
            self.assertTrue(0 < len(steps) <= 160, name)
            for food, grams in items:
                self.assertIn(food, FOODS, f"{name}: falta {food}")
                self.assertTrue(0 < grams <= 600, f"{name}: {food} {grams} g")
            totals = dpp_recipes.recipe_totals(items, FOODS)
            self.assertTrue(60 <= totals["kcal"] <= 1000, f"{name}: {totals}")

    def test_basics_are_consistent_and_not_duplicated(self) -> None:
        names = [f["name"].lower() for f in dpp_catalog.GENERIC_FOODS]
        self.assertEqual(len(names), len(set(names)))
        for f in dpp_catalog.GENERIC_FOODS:
            self.assertLessEqual(f["protein"] + f["carbs"] + f["fat"], 100.5, f["name"])
            self.assertLessEqual(abs(f["kcal"] - (4 * f["protein"] + 4 * f["carbs"] + 9 * f["fat"])), max(40, 0.25 * f["kcal"]), f["name"])


class LegacyRenameTests(unittest.TestCase):
    def test_old_renames_never_collide_with_an_existing_name(self) -> None:
        import dpp_entrypoint

        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE foods(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        db.execute("CREATE TABLE meal_items(id INTEGER PRIMARY KEY, food_name TEXT)")
        db.executemany("INSERT INTO foods(name) VALUES(?)", [("Champiñones laminados",), ("Champiñones",), ("Pollo pechuga cruda",)])
        dpp_entrypoint.legacy.fix_existing_data(db)  # used to raise IntegrityError on start-up
        names = {r[0] for r in db.execute("SELECT name FROM foods")}
        self.assertEqual(names, {"Champiñones laminados", "Champiñones", "Pollo pechuga cruda Pazo de Pías"})

    def test_no_generic_food_uses_a_legacy_name(self) -> None:
        legacy_old = {"jamón cocido extra 85%", "pollo pechuga cruda", "champiñones"}
        self.assertFalse(legacy_old & {f["name"].lower() for f in dpp_catalog.GENERIC_FOODS})


class AddRecipesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE templates(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, notes TEXT, kind TEXT NOT NULL DEFAULT 'meal', payload TEXT NOT NULL DEFAULT '{}')")

    def test_adds_all_and_is_idempotent(self) -> None:
        self.assertEqual(dpp_recipes.add_recipes(self.db), len(dpp_recipes.RECIPES))
        self.assertEqual(dpp_recipes.add_recipes(self.db), 0)
        row = self.db.execute("SELECT notes, kind, payload FROM templates WHERE name = 'Tostada de aguacate y huevo'").fetchone()
        payload = json.loads(row[2])
        self.assertEqual((row[1], payload["category"], payload["recipe"]), ("meal", "desayuno", True))
        self.assertEqual(payload["items"][0], {"food": "Pan integral", "grams": 60})

    def test_user_templates_with_the_same_name_are_untouched(self) -> None:
        self.db.execute("INSERT INTO templates(name, notes, payload) VALUES('tostada de aguacate y huevo', 'mía', '{\"items\": []}')")
        self.assertEqual(dpp_recipes.add_recipes(self.db), len(dpp_recipes.RECIPES) - 1)
        self.assertEqual(self.db.execute("SELECT notes FROM templates WHERE name LIKE 'tostada de aguacate%'").fetchone()[0], "mía")


if __name__ == "__main__":
    unittest.main()

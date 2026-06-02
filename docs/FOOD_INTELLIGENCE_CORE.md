# Diet Pro Planner - Food Intelligence Core

## Decision

The next strategic step is not more UI. The next step is a deterministic, explainable, local-first food intelligence engine.

## Goals

- Analyze a full day of meals.
- Classify each food as exact, high, medium or low confidence.
- Detect estimated foods, composite meals, missing macros and weak data.
- Recommend the next meal using current intake, training and weight trend.
- Prepare external resolution via Open Food Facts and USDA.
- Keep SQLite as the source of truth.

## Initial endpoints

- GET /api/food-intel/day?date=YYYY-MM-DD
- POST /api/food-intel/meal-plan
- GET /api/food-intel/barcode/<barcode>
- POST /api/plans/<date>/materialize

## Confidence model

item_confidence = 0.55 * source + 0.30 * quantity + 0.15 * completeness

Source scores:
- local_label_exact: 1.00
- local_verified: 0.95
- openfoodfacts_barcode: 0.85
- usda_generic: 0.75
- nutritionix_nlp: 0.65
- homemade_estimated: 0.55
- manual_guess: 0.45

Quantity scores:
- weighed_grams: 1.00
- label_serving: 0.90
- normal_unit: 0.75
- visual_portion: 0.60
- unknown: 0.50

Completeness scores:
- full_macros_source: 1.00
- full_macros_no_source: 0.85
- partial_macros: 0.70

## Daily score

Do not show a score if the day has less than 2 meals or less than 600 kcal.

Components:
- Protein: 30
- Energy: 20
- Training alignment: 15
- Oil: 10
- Extras / liquid calories: 10
- Salt: 5
- Fruit / veg / practical fiber: 10

Total: 100

## Product direction

The app must answer:

- Am I doing well today?
- What is reliable and what is estimated?
- What should I eat next?
- How much should I eat?
- Does this fit my training and weight trend?

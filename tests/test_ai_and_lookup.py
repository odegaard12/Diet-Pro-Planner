from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

import _env
import dpp_ai
import dpp_ai_claude
import dpp_db
import dpp_entrypoint
import dpp_food_lookup

ADVICE = {
    "headline": "Día bien encaminado", "assessment": "Vas bien.",
    "next_meal": {"title": "Cena", "items": [{"food": "Pollo", "grams": 200}], "why": "Proteína"},
    "tips": ["Bebe agua"], "warnings": [],
}


class AiCoachTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = dpp_entrypoint.app.test_client()
        with dpp_db.connect() as db:
            db.execute("DELETE FROM ai_cache")
            db.execute("DELETE FROM ai_usage")

    def tearDown(self) -> None:
        for key in ("ANTHROPIC_API_KEY", "DPP_AI_DAILY_LIMIT"):
            os.environ.pop(key, None)

    def test_disabled_by_default(self) -> None:
        status = self.client.get("/api/ai/status", headers=_env.AUTH).get_json()
        self.assertFalse(status["enabled"])
        response = self.client.post("/api/ai/coach", json={}, headers=_env.AUTH)
        self.assertEqual(response.status_code, 503)

    def test_coach_uses_cache_and_daily_limit(self) -> None:
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        os.environ["DPP_AI_DAILY_LIMIT"] = "1"
        calls = []

        def fake_generate(**kwargs):
            calls.append(kwargs)
            return ADVICE, {"input_tokens": 100, "output_tokens": 50}

        with mock.patch.object(dpp_ai_claude, "generate_json", side_effect=fake_generate):
            first = self.client.post("/api/ai/coach", json={"date": "2026-06-01"}, headers=_env.AUTH).get_json()
            second = self.client.post("/api/ai/coach", json={"date": "2026-06-01"}, headers=_env.AUTH).get_json()
            limited = self.client.post("/api/ai/coach", json={"date": "2026-06-01", "question": "¿y mañana?"}, headers=_env.AUTH)
        self.assertEqual(first["advice"], ADVICE)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"], "identical context is served from cache")
        self.assertEqual(limited.status_code, 429, "daily limit applies to new requests")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model"], "claude-opus-5-5")
        self.assertIn("objetivos", calls[0]["text"])
        self.assertNotIn("test-token", calls[0]["text"])

    def test_label_mapping_clamps_values(self) -> None:
        mapped = dpp_ai._label_to_food({
            "name": "Queso", "brand": "Marca", "serving_g": 40, "confidence": "alta", "notes": "",
            "per_100g": {"kcal": 371, "protein": 22, "carbs": -1, "fat": 31, "sugar": 0, "salt": 250},
        })
        self.assertEqual(mapped["nutrition"]["carbs"], 0)
        self.assertEqual(mapped["nutrition"]["salt"], 100)
        self.assertEqual(mapped["nutrition"]["typical_g"], 40)
        self.assertEqual(mapped["product"]["name"], "Queso")


class ClaudeProviderTests(unittest.TestCase):
    """Request shape against a fake 'anthropic' module (no network)."""

    def fake_module(self, captured):
        module = types.ModuleType("anthropic")
        for name in ("AuthenticationError", "RateLimitError", "BadRequestError", "APIStatusError", "APIConnectionError"):
            setattr(module, name, type(name, (Exception,), {}))

        class Messages:
            def __init__(self, kind):
                self.kind = kind

            def create(self, **kwargs):
                captured.append((self.kind, kwargs))
                block = types.SimpleNamespace(type="text", text='{"ok": true}')
                return types.SimpleNamespace(stop_reason="end_turn", content=[block],
                                             usage=types.SimpleNamespace(input_tokens=10, output_tokens=5))

        class Client:
            def __init__(self, **kwargs):
                self.messages = Messages("messages")
                self.beta = types.SimpleNamespace(messages=Messages("beta"))

        module.Anthropic = Client
        return module

    def test_opus_request_uses_structured_output_and_fallbacks(self) -> None:
        captured = []
        with mock.patch.dict(sys.modules, {"anthropic": self.fake_module(captured)}):
            result, usage = dpp_ai_claude.generate_json(model="claude-opus-5-5", system="s", text="t", schema={"type": "object"})
        self.assertEqual(result, {"ok": True})
        kind, kwargs = captured[0]
        self.assertEqual(kind, "beta")
        self.assertEqual(kwargs["fallbacks"], "default")
        self.assertEqual(kwargs["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("thinking", kwargs)
        self.assertEqual(usage["input_tokens"], 10)

    def test_other_models_use_plain_messages(self) -> None:
        captured = []
        with mock.patch.dict(sys.modules, {"anthropic": self.fake_module(captured)}):
            dpp_ai_claude.generate_json(model="claude-haiku-5-5", system="s", text="t", schema={"type": "object"})
        self.assertEqual(captured[0][0], "messages")
        self.assertNotIn("fallbacks", captured[0][1])


OFF_PRODUCT = {
    "status": 1,
    "product": {
        "code": "8480000123456", "product_name_es": "Yogur proteico natural", "brands": "Marca Test,Otra",
        "serving_quantity": 120, "serving_size": "120 g", "nutriscore_grade": "a",
        "nutriments": {"energy-kj_100g": 251, "proteins_100g": 10, "carbohydrates_100g": 4,
                       "fat_100g": 0.2, "sugars_100g": 4, "sodium_100g": 0.04},
    },
}


class FoodLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        dpp_food_lookup.CACHE_FILE.unlink(missing_ok=True)
        self.client = dpp_entrypoint.app.test_client()

    def test_normalize_product_converts_units(self) -> None:
        food = dpp_food_lookup.normalize_product(OFF_PRODUCT["product"])
        self.assertEqual(food["kcal"], 59.99)  # 251 kJ / 4.184
        self.assertEqual(food["salt"], 0.1)  # sodium x 2.5
        self.assertEqual(food["typical_g"], 120)
        self.assertEqual(food["barcode"], "8480000123456")
        self.assertEqual(food["nutriscore"], "A")
        self.assertIn("Marca Test", food["name"])
        self.assertIsNone(dpp_food_lookup.normalize_product({"product_name": "Sin datos", "nutriments": {}}))

    def test_barcode_lookup_hits_off_once_then_cache(self) -> None:
        response = mock.Mock(status_code=200)
        response.json.return_value = OFF_PRODUCT
        with mock.patch.object(dpp_food_lookup.requests, "get", return_value=response) as get:
            first = self.client.get("/api/foods/barcode/8480000123456", headers=_env.AUTH).get_json()
            second = self.client.get("/api/foods/barcode/8480000123456", headers=_env.AUTH).get_json()
        self.assertTrue(first["found"])
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(get.call_count, 1)
        self.assertIn("DietProPlanner", get.call_args.kwargs["headers"]["User-Agent"])

    def test_invalid_barcode_and_short_query(self) -> None:
        self.assertEqual(self.client.get("/api/foods/barcode/12ab", headers=_env.AUTH).status_code, 400)
        self.assertEqual(self.client.get("/api/foods/search-online?q=yo", headers=_env.AUTH).status_code, 400)

    def test_network_errors_are_reported_cleanly(self) -> None:
        with mock.patch.object(dpp_food_lookup.requests, "get", side_effect=dpp_food_lookup.requests.ConnectionError()):
            response = self.client.get("/api/foods/search-online?q=yogur", headers=_env.AUTH)
        self.assertEqual(response.status_code, 502)
        self.assertIn("Open Food Facts", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

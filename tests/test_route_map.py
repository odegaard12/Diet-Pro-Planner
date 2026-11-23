from __future__ import annotations

import unittest

import _env  # noqa: F401  (sets up the temporary data dir before importing the app)
import dpp_entrypoint

# Golden route map of the served app (frozen at v0.7.7). A refactor must not change it.
RULES = [
    ('/', ['GET', 'HEAD', 'OPTIONS'], 'index'),
    ('/api/activity-plan', ['GET', 'HEAD', 'OPTIONS'], 'activity_plan_list'),
    ('/api/activity-plan', ['OPTIONS', 'POST'], 'activity_plan_create'),
    ('/api/activity-plan/<int:item_id>', ['DELETE', 'OPTIONS'], 'activity_plan_delete'),
    ('/api/activity-plan/<int:item_id>', ['OPTIONS', 'PUT'], 'activity_plan_update'),
    ('/api/activity-plan/<int:item_id>/status', ['OPTIONS', 'POST'], 'activity_plan_status'),
    ('/api/ai/coach', ['OPTIONS', 'POST'], 'ai_coach'),
    ('/api/ai/label', ['OPTIONS', 'POST'], 'ai_label'),
    ('/api/ai/status', ['GET', 'HEAD', 'OPTIONS'], 'ai_status'),
    ('/api/analytics/overview', ['GET', 'HEAD', 'OPTIONS'], 'analytics_overview'),
    ('/api/analytics/tdee', ['GET', 'HEAD', 'OPTIONS'], 'analytics_tdee'),
    ('/api/auth/login', ['OPTIONS', 'POST'], '_dpp_auth_login'),
    ('/api/auth/logout', ['OPTIONS', 'POST'], '_dpp_auth_logout'),
    ('/api/auth/status', ['GET', 'HEAD', 'OPTIONS'], '_dpp_auth_status'),
    ('/api/backup', ['GET', 'HEAD', 'OPTIONS'], 'backup_list'),
    ('/api/backup', ['OPTIONS', 'POST'], 'backup_create'),
    ('/api/backup/download', ['GET', 'HEAD', 'OPTIONS'], 'backup_download'),
    ('/api/body-snapshot/latest', ['GET', 'HEAD', 'OPTIONS'], 'api_body_snapshot_latest'),
    ('/api/body-trends', ['GET', 'HEAD', 'OPTIONS'], 'api_body_trends'),
    ('/api/data-audit', ['GET', 'HEAD', 'OPTIONS'], 'data_audit'),
    ('/api/exercises', ['OPTIONS', 'POST'], 'api_exercises'),
    ('/api/export', ['GET', 'HEAD', 'OPTIONS'], 'api_export'),
    ('/api/export/<kind>.csv', ['GET', 'HEAD', 'OPTIONS'], 'export_csv'),
    ('/api/food-intel/day', ['GET', 'HEAD', 'OPTIONS', 'POST'], 'api_food_intel_day'),
    ('/api/food-intel/health', ['GET', 'HEAD', 'OPTIONS'], 'api_food_intel_health'),
    ('/api/food-intel/meal-plan', ['OPTIONS', 'POST'], 'api_food_intel_meal_plan'),
    ('/api/food-photo', ['OPTIONS', 'POST'], 'api_food_photo'),
    ('/api/food-photo-ocr', ['OPTIONS', 'POST'], 'api_food_photo_ocr'),
    ('/api/foods', ['OPTIONS', 'POST'], 'api_foods'),
    ('/api/foods/<int:item_id>', ['DELETE', 'OPTIONS'], 'delete_food'),
    ('/api/foods/barcode/<code>', ['GET', 'HEAD', 'OPTIONS'], 'food_barcode'),
    ('/api/foods/search-online', ['GET', 'HEAD', 'OPTIONS'], 'food_search_online'),
    ('/api/insights/today', ['GET', 'HEAD', 'OPTIONS'], 'api_v012_insights_today'),
    ('/api/integrations/strava/config', ['GET', 'HEAD', 'OPTIONS'], 'strava_v018_get_config'),
    ('/api/integrations/strava/config', ['OPTIONS', 'POST'], 'strava_v018_save_config'),
    ('/api/integrations/strava/diagnostics', ['GET', 'HEAD', 'OPTIONS'], 'strava_v018_diagnostics'),
    ('/api/integrations/strava/disconnect', ['OPTIONS', 'POST'], 'strava_v018_disconnect'),
    ('/api/integrations/strava/test', ['OPTIONS', 'POST'], 'strava_v018_test'),
    ('/api/meals', ['OPTIONS', 'POST'], 'api_meals'),
    ('/api/meals/<int:item_id>', ['DELETE', 'OPTIONS'], 'delete_meal'),
    ('/api/meals/<int:item_id>', ['OPTIONS', 'PUT'], 'update_meal'),
    ('/api/meals/<int:item_id>/duplicate', ['OPTIONS', 'POST'], 'duplicate_meal'),
    ('/api/ocr/status', ['GET', 'HEAD', 'OPTIONS'], 'api_ocr_status'),
    ('/api/pantry', ['GET', 'HEAD', 'OPTIONS'], 'pantry_get'),
    ('/api/pantry', ['OPTIONS', 'POST'], 'pantry_post'),
    ('/api/pantry/v2', ['GET', 'HEAD', 'OPTIONS'], 'pantry_v2_get'),
    ('/api/pantry/v2', ['OPTIONS', 'POST'], 'pantry_v2_save'),
    ('/api/plans', ['OPTIONS', 'POST'], 'api_plans'),
    ('/api/profile', ['GET', 'HEAD', 'OPTIONS'], 'profile_get'),
    ('/api/profile', ['OPTIONS', 'PUT'], 'profile_put'),
    ('/api/smart-coach/alternative', ['OPTIONS', 'POST'], 'smart_coach_alternative'),
    ('/api/smart-coach/day', ['GET', 'HEAD', 'OPTIONS'], 'smart_coach_day'),
    ('/api/smart-coach/unavailable', ['OPTIONS', 'POST'], 'smart_coach_unavailable'),
    ('/api/state', ['GET', 'HEAD', 'OPTIONS'], 'api_state'),
    ('/api/strava/auto-config', ['OPTIONS', 'POST'], 'api_strava_auto_config'),
    ('/api/strava/auto-run', ['OPTIONS', 'POST'], 'api_strava_auto_run'),
    ('/api/strava/auto-status', ['GET', 'HEAD', 'OPTIONS'], 'api_strava_auto_status'),
    ('/api/strava/callback', ['GET', 'HEAD', 'OPTIONS'], 'api_strava_callback'),
    ('/api/strava/import', ['OPTIONS', 'POST'], 'api_strava_import'),
    ('/api/strava/last', ['GET', 'HEAD', 'OPTIONS'], 'api_strava_last'),
    ('/api/strava/preview', ['OPTIONS', 'POST'], 'api_strava_preview'),
    ('/api/strava/status', ['GET', 'HEAD', 'OPTIONS'], 'api_strava_status'),
    ('/api/strava/sync', ['OPTIONS', 'POST'], 'api_strava_sync'),
    ('/api/templates', ['OPTIONS', 'POST'], 'api_templates'),
    ('/api/weights', ['OPTIONS', 'POST'], 'api_weights'),
    ('/api/weights/<int:item_id>', ['DELETE', 'OPTIONS'], 'delete_weight'),
    ('/api/weights/<int:item_id>', ['OPTIONS', 'PUT'], 'update_weight'),
    ('/api/workouts', ['OPTIONS', 'POST'], 'api_workouts'),
    ('/api/workouts/<int:item_id>', ['DELETE', 'OPTIONS'], 'delete_workout'),
    ('/favicon.ico', ['GET', 'HEAD', 'OPTIONS'], 'favicon'),
    ('/health', ['GET', 'HEAD', 'OPTIONS'], 'api_v012_health'),
    ('/static/<path:filename>', ['GET', 'HEAD', 'OPTIONS'], 'static'),
    ('/sw.js', ['GET', 'HEAD', 'OPTIONS'], 'service_worker'),
    ('/uploads/<name>', ['GET', 'HEAD', 'OPTIONS'], 'uploaded_file'),
    ('/weight-2', ['GET', 'HEAD', 'OPTIONS'], 'weight_2_page'),
]
ENDPOINTS = ['_dpp_auth_login', '_dpp_auth_logout', '_dpp_auth_status', 'activity_plan_create', 'activity_plan_delete', 'activity_plan_list', 'activity_plan_status', 'activity_plan_update', 'ai_coach', 'ai_label', 'ai_status', 'analytics_overview', 'analytics_tdee', 'api_body_snapshot_latest', 'api_body_trends', 'api_exercises', 'api_export', 'api_food_intel_day', 'api_food_intel_health', 'api_food_intel_meal_plan', 'api_food_photo', 'api_food_photo_ocr', 'api_foods', 'api_meals', 'api_ocr_status', 'api_plans', 'api_state', 'api_strava_auto_config', 'api_strava_auto_run', 'api_strava_auto_status', 'api_strava_callback', 'api_strava_import', 'api_strava_last', 'api_strava_preview', 'api_strava_status', 'api_strava_sync', 'api_templates', 'api_v012_health', 'api_v012_insights_today', 'api_weights', 'api_workouts', 'backup_create', 'backup_download', 'backup_list', 'data_audit', 'delete_food', 'delete_meal', 'delete_weight', 'delete_workout', 'duplicate_meal', 'export_csv', 'favicon', 'food_barcode', 'food_search_online', 'index', 'pantry_get', 'pantry_post', 'pantry_v2_get', 'pantry_v2_save', 'profile_get', 'profile_put', 'service_worker', 'smart_coach_alternative', 'smart_coach_day', 'smart_coach_unavailable', 'static', 'strava_v018_diagnostics', 'strava_v018_disconnect', 'strava_v018_get_config', 'strava_v018_save_config', 'strava_v018_test', 'update_meal', 'update_weight', 'uploaded_file', 'weight_2_page']


class RouteMapTests(unittest.TestCase):
    def test_url_map_is_unchanged(self) -> None:
        app = dpp_entrypoint.app
        got = sorted((str(r.rule), sorted(r.methods), r.endpoint) for r in app.url_map.iter_rules())
        self.assertEqual(got, RULES)

    def test_view_functions_are_unchanged(self) -> None:
        self.assertEqual(sorted(dpp_entrypoint.app.view_functions), ENDPOINTS)


if __name__ == "__main__":
    unittest.main()

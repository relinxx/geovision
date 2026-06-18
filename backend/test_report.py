"""
GeoVision Test Report
Run: python test_report.py
"""

import subprocess
import time

VENV_PYTHON = r"c:\Users\relinxx\Documents\geovision\.venv\Scripts\python.exe"
BACKEND_DIR = r"c:\Users\relinxx\Documents\geovision\geovison\backend"

# Maps raw pytest test function names to a human-readable label.
# Tests not in this map are shown under their module with a cleaned-up name.
LABELS = {
    # --- Auth ---
    "test_register_returns_token_and_user":                   "User registration returns JWT token and user object",
    "test_register_rejects_invalid_email":                    "Registration rejects malformed email address",
    "test_login_returns_token_for_valid_credentials":         "Login returns token for correct email/password",
    "test_login_rejects_wrong_credentials":                   "Login returns 401 for wrong password",
    "test_me_returns_current_user_from_bearer_token":         "/auth/me decodes bearer token and returns user",
    "test_logout_returns_message":                            "Logout returns success message (client-side token removal)",

    # --- Spatial Optimize ---
    "test_spatial_optimize_returns_plan_payload":             "Optimizer returns Pareto-ranked land-use plans",
    "test_spatial_optimize_allows_repairable_invalid_geometry": "Self-intersecting geometry is repaired before optimization",
    "test_spatial_optimize_rejects_empty_parcels":            "Optimizer rejects request with zero parcels",
    "test_spatial_optimize_rejects_invalid_adjacency_predicate": "Unsupported adjacency predicate rejected with 422",
    "test_spatial_optimize_interactive_mode_caps_settings":   "Interactive mode caps population/generations for speed",
    "test_spatial_optimize_rejects_invalid_spatial_neighbor_radius": "Spatial neighbor radius >5000m rejected",

    # --- Spatial Compatibility ---
    "test_feature3_optimize_response_contains_spatial_compatibility_payload": "Spatial compatibility fields present when feature enabled",
    "test_feature3_disabled_keeps_old_response_shape":        "Disabling spatial compatibility preserves original response shape",

    # --- Nearby Parcels ---
    "test_nearby_parcels_returns_expected_shape":             "Nearby parcels endpoint returns correct GeoJSON shape",
    "test_nearby_parcels_unknown_parcel_returns_404":         "Unknown APN returns 404 with clear error",
    "test_nearby_parcels_request_rejects_invalid_radius":     "Radius below minimum rejected with 422",
    "test_nearby_parcels_routes_registered":                  "Nearby parcels routes registered at correct paths",

    # --- Orchestrator Endpoints ---
    "test_create_orchestration_plan_returns_job_id":          "Orchestration plan creation returns job ID",
    "test_create_orchestration_plan_rejects_empty_parcel_ids":"Orchestrator rejects empty parcel ID list",
    "test_get_job_status_returns_progress_and_steps":         "Job status endpoint returns progress percentage and steps",
    "test_get_job_status_returns_404_for_missing_job":        "Job status returns 404 for unknown job ID",
    "test_get_job_result_returns_completed_result":           "Completed job result is returned correctly",
    "test_get_job_result_returns_400_when_job_not_completed": "Fetching result of incomplete job returns 400",
    "test_get_job_result_returns_404_for_missing_job":        "Result endpoint returns 404 for missing job",

    # --- Saved Maps ---
    "test_saved_map_returns_404_when_missing":                "Fetching non-existent saved map returns 404",

    # --- Health ---
    "test_health_endpoint_returns_ok":                        "/health returns {status: ok}",
    "test_api_health_alias_returns_ok":                       "/api/health alias also returns {status: ok}",

    # --- Risk Explainer (unit) ---
    "test_explain_returns_zero_score_when_no_hazard_flags_are_active": "Risk score is zero when all hazard flags are off",
    "test_explain_calculates_score_from_active_hazard_flags": "Risk score computed correctly from active hazard flags",
    "test_explain_sorts_contributions_by_largest_contribution_first":  "Hazard contributions sorted descending by weight",
    "test_explain_preserves_precomputed_xgb_risk_score":      "Pre-computed XGBoost score is preserved in output",
    "test_explain_treats_string_one_as_active_flag":          "String '1' treated as active flag (tolerant parsing)",
    "test_counterfactual_calculates_score_changes":           "Counterfactual: score delta computed for flag changes",
    "test_counterfactual_ignores_unknown_change_fields":      "Counterfactual: unknown property keys are silently ignored",
    "test_counterfactual_reports_only_valid_applied_changes": "Counterfactual: only valid changes listed in output",
    "test_counterfactual_does_not_mutate_original_properties":"Counterfactual: original parcel dict is not modified",

    # --- Assignment Explainer ---
    "test_green_assignment_with_high_risk_and_hazards":       "High-risk green assignment produces correct explanation",
    "test_built_use_with_low_risk_gets_positive_feasibility_reason": "Low-risk built use gets positive feasibility reason",
    "test_handles_missing_scores_and_unknown_zoning_safely":  "Missing scores and unknown zoning handled gracefully",
    "test_spatial_explain_assignment_route_is_registered_and_returns_expected_shape": "Explain-assignment route registered and returns expected shape",

    # --- Suitability Agent (unit) ---
    "test_load_data_prefers_xgb_score_and_falls_back_to_rule_score": "XGBoost score preferred; falls back to rule score",
    "test_predict_returns_expected_columns_and_preserves_input_order": "Predict output has all columns in correct order",
    "test_predict_clamps_precomputed_risk_scores_to_valid_range":     "Risk scores clamped to [0, 1]",
    "test_predict_uses_feature_based_fallback_when_apn_is_missing_from_lookup": "Unknown APN uses feature-based heuristic fallback",
    "test_predict_uses_neutral_scores_when_no_risk_or_features_exist":"No risk/features produces neutral suitability scores",
    "test_suitability_scores_follow_expected_risk_heuristics":        "Suitability scores follow risk-inverse heuristics",
    "test_find_default_risk_data_path_returns_first_available_candidate": "Risk data path discovery returns first available file",

    # --- Spatial Agent (unit) ---
    "test_normalize_risk_score_accepts_multiple_property_names":  "Risk score normalised from any supported field name",
    "test_build_parcels_from_geojson_extracts_core_spatial_fields": "GeoJSON parcels parsed into ParcelRecord objects",
    "test_build_parcels_from_geojson_falls_back_to_feature_id_when_apn_missing": "Feature ID used when APN property is missing",
    "test_build_adjacency_from_geojson_detects_touching_neighbors":   "Touching polygon neighbours detected correctly",
    "test_zoning_violation_penalty_counts_invalid_assignments":       "Zoning violation penalty counts illegal assignments",
    "test_green_area_deviation_uses_area_not_parcel_count":           "Green area deviation uses polygon area not count",
    "test_environmental_risk_exposure_counts_only_built_uses":        "Risk exposure only counts residential/commercial/industrial",
    "test_fragmentation_penalty_is_fraction_of_boundary_changes":     "Fragmentation penalty normalised by total boundary edges",
    "test_land_use_balance_penalty_normalizes_target_mix":            "Land-use balance penalty normalises % and fraction targets",
    "test_optimizer_respects_allowed_use_codes_in_generated_assignments": "NSGA-II generates only zoning-allowed assignments",
    "test_optimizer_progress_callback_receives_major_stages":         "Optimizer emits named progress stages for UI",
    "test_optimizer_ignores_progress_callback_errors":                "Broken progress callback does not abort optimization",
    "test_optimizer_rejects_empty_objective_list":                    "Optimizer raises ValueError when no objectives given",

    # --- Spatial Compatibility (unit) ---
    "test_normalize_land_use_accepts_common_variants":            "Land-use label normaliser handles common aliases",
    "test_normalize_risk_value_clamps_and_converts_percentages":  "Risk value normaliser clamps and converts 0-100 inputs",
    "test_build_neighbor_pairs_prevents_duplicate_and_self_pairs":"Neighbour pair builder deduplicates and excludes self-pairs",
    "test_no_neighbor_case_returns_neutral_summary":              "No neighbours produces neutral compatibility summary",
    "test_industrial_near_residential_counts_conflict_and_scores_lower_than_compatible_pair": "Industrial-residential proximity counts as conflict",
    "test_green_near_high_risk_parcel_counts_buffer_and_improves_score": "Green buffer near high-risk parcel improves score",
    "test_spatial_compatibility_objective_is_neutral_without_pairs": "Compatibility objective returns 0 when no pairs exist",

    # --- Nearby Parcels Service (unit) ---
    "test_normalize_risk_value_handles_percentages_and_clamps":       "Risk value handles 0-100 percentages and clamps correctly",
    "test_build_planning_insight_prefers_residential_low_risk_language": "Low-risk insight uses residential-friendly language",
    "test_build_planning_insight_flags_elevated_risk":                "Elevated risk insight flags hazard in language",
    "test_nearby_service_uses_memory_fallback_when_redis_missing":    "Nearby service falls back to in-memory store (no Redis)",
    "test_nearby_service_summary_uses_sample_features":               "Nearby service summary uses sampled parcel features",
    "test_nearby_service_uses_redis_geo_when_available":              "Nearby service uses Redis GEO commands when available",
    "test_nearby_service_raises_clear_error_when_geojson_is_missing": "Nearby service raises clear error when GeoJSON missing",

    # --- Orchestrator Steps (unit) ---
    "test_run_environment_stage_calls_suitability_agent_and_returns_records": "Environment stage calls suitability agent and returns records",
    "test_run_environment_stage_propagates_agent_errors":             "Environment stage propagates agent errors correctly",
    "test_run_zoning_stage_returns_shared_regulations_for_each_parcel": "Zoning stage returns regulations for each parcel",
    "test_run_zoning_stage_returns_placeholder_when_rag_service_cannot_start": "Zoning stage returns placeholder when RAG unavailable",
    "test_run_zoning_stage_returns_empty_regulations_when_retrieve_fails": "Zoning stage returns empty list when retrieval fails",
    "test_merge_outputs_combines_environment_and_zoning_by_parcel_id": "Merge step combines environment and zoning by APN",
    "test_merge_outputs_includes_parcels_that_exist_only_in_zoning_results": "Merge includes parcels found only in zoning results",
    "test_run_spatial_stage_returns_empty_result_when_no_unified_data": "Spatial stage returns empty result with no input data",
    "test_run_spatial_stage_converts_unified_data_and_serializes_optimizer_result": "Spatial stage serialises optimizer output correctly",
    "test_run_spatial_stage_falls_back_to_zero_when_risk_value_is_invalid": "Spatial stage defaults risk to 0 for invalid values",
    "test_run_spatial_stage_propagates_optimizer_errors":             "Spatial stage propagates optimizer errors correctly",

    # --- Redis / Geo ---
    "test_geo_helpers_namespace_keys_and_delegate_calls":             "Redis GEO helpers namespace keys and delegate correctly",

    # --- Job Store ---
    "test_in_memory_job_store_round_trip":                            "In-memory job store creates and retrieves jobs",
    "test_redis_backed_job_store_round_trip":                         "Redis-backed job store creates and retrieves jobs",

    # --- Spatial Cache ---
    "test_cache_key_changes_when_effective_settings_change":          "Cache key changes when optimizer settings change",
    "test_cache_key_is_stable_for_equivalent_requests":               "Cache key is stable for equivalent requests",
    "test_normalize_target_mix_filters_and_normalizes":               "Target mix normalised to fractions summing to 1.0",

    # --- Config ---
    "test_builds_database_and_redis_urls_from_component_env":         "DB and Redis URLs built from component env vars",
    "test_database_url_env_takes_precedence":                         "DATABASE_URL env var overrides component vars",
    "test_allows_vite_fallback_port_for_auth_preflight":              "CORS allows Vite fallback port for auth preflight",
    "test_init_db_runs_alembic_upgrade_head":                         "DB init runs alembic upgrade head",

    # --- Alembic Migration ---
    "test_upgrade_creates_users_table_for_fresh_database":            "Migration creates users table on fresh database",
    "test_upgrade_skips_create_when_users_table_already_exists":      "Migration skips users table creation if it exists",

    # --- NSGA-II ---
    "test_evolve_returns_valid_population":                           "NSGA-II evolve returns valid population with correct size",

    # --- Spatial Agent / Config ---
    "test_defaults_are_valid":                                        "NSGA2Config defaults are all valid values",
    "test_invalid_population_raises":                                 "Invalid population size raises validation error",
    "test_invalid_rates_raise":                                       "Mutation/crossover rates outside [0,1] raise error",
    "test_duplicate_labels_raise":                                    "Duplicate land-use labels raise validation error",
    "test_land_use_labels_are_normalized":                            "Land-use labels are lowercased and deduplicated",

    # --- Spatial Agent / Geo ---
    "test_falls_back_to_feature_id_when_no_property_id":             "Parcel ID falls back to feature.id when APN missing",
    "test_invalid_geometry_does_not_break_adjacency":                 "Invalid geometry skipped without crashing adjacency build",
    "test_prefers_property_ids_over_feature_id":                      "Property APN/id fields preferred over feature.id",

    # --- Spatial Agent / Types ---
    "test_empty_parcel_id_raises":                                    "Empty parcel_id raises ValueError",
    "test_normalization_and_clamping":                                "Risk score normalised and clamped to [0, 1]",
    "test_adjacency_is_normalized":                                   "Adjacency indices are sorted and deduplicated",
    "test_invalid_allowed_code_raises":                               "Invalid allowed-use code raises ValueError",

    # --- Objectives (spatial_agent/tests) ---
    "test_mean_suitability_loss":                                     "Green area deviation from target computed correctly",
    "test_zoning_violation_penalty":                                  "Zoning violation penalty counts and returns correctly",
    "test_land_use_balance_penalty_factory":                          "Land-use balance penalty factory normalises weights",

    # --- Optimizer (spatial_agent/tests) ---
    "test_optimize_geojson_features":                                 "Optimizer runs end-to-end on GeoJSON polygon features",

    # --- infer_allowed_use_labels parametrize ---
    "test_infer_allowed_use_labels_from_properties":                  "Allowed use labels inferred from ZONING_CODE / GP_LAND_USE",
}

# Group display order and section headings
SECTIONS = [
    ("Authentication",            "tests/endpoints/test_auth_endpoints.py"),
    ("Health Check",              "tests/endpoints/test_system_and_suitability_endpoints.py"),
    ("Spatial Optimization",      "tests/endpoints/test_spatial_endpoints.py"),
    ("Spatial Compatibility",     "tests/endpoints/test_spatial_compatibility_flow.py"),
    ("Nearby Parcels",            "tests/endpoints/test_nearby_parcels_endpoints.py"),
    ("Job Orchestrator",          "tests/endpoints/test_orchestrator_endpoints.py"),
    ("Saved Maps",                "tests/endpoints/test_saved_maps_endpoints.py"),
    ("Risk Explainer",            "tests/unit/test_risk_explainer.py"),
    ("Assignment Explainer",      "tests/test_assignment_explainer.py"),
    ("Suitability Agent",         "tests/unit/test_suitability_agent.py"),
    ("Spatial Agent",             "tests/unit/test_spatial_agent.py"),
    ("Spatial Compatibility",     "tests/unit/test_spatial_compatibility.py"),
    ("Nearby Parcels Service",    "tests/unit/test_nearby_parcels_service.py"),
    ("Orchestrator Steps",        "tests/unit/test_orchestrator_steps.py"),
    ("Redis / Geo Store",         "tests/unit/test_redis_store_geo.py"),
    ("Job Store",                 "tests/test_job_store.py"),
    ("Spatial Cache",             "tests/test_spatial_cache.py"),
    ("Config & CORS",             "tests/test_config.py"),
    ("CORS Defaults",             "tests/test_cors_defaults.py"),
    ("Database Init",             "tests/test_database.py"),
    ("Alembic Migration",         "tests/test_alembic_users_migration.py"),
    ("NSGA-II Algorithm",         "agent/spatial_agent/tests/test_nsga2.py"),
    ("Optimizer Config",          "agent/spatial_agent/tests/test_config.py"),
    ("Geo Utilities",             "agent/spatial_agent/tests/test_geo.py"),
    ("Objectives",                "agent/spatial_agent/tests/test_objectives.py"),
    ("Optimizer",                 "agent/spatial_agent/tests/test_optimizer.py"),
    ("Types",                     "agent/spatial_agent/tests/test_types.py"),
]


def run_tests():
    t0 = time.time()
    result = subprocess.run(
        [VENV_PYTHON, "-m", "pytest",
         "tests/", "agent/spatial_agent/tests/",
         "--ignore=tests/unit/test_zoning_rag_service.py",
         "-v", "--tb=no"],
        capture_output=True, text=True,
        cwd=BACKEND_DIR,
    )
    elapsed = time.time() - t0
    return result.stdout + result.stderr, elapsed


def parse_results(output):
    """Returns {module_path: [(test_name, status), ...]}"""
    by_module = {}
    for line in output.splitlines():
        status = None
        if " PASSED" in line:
            status = "PASS"
        elif " FAILED" in line:
            status = "FAIL"
        elif " XFAIL" in line:
            status = "SKIP"
        elif " ERROR" in line and "::" in line:
            status = "FAIL"
        if status is None:
            continue
        # line format: path/to/file.py::ClassName::test_name PASSED [xx%]
        parts = line.strip().split("::")
        if len(parts) < 2:
            continue
        module = parts[0].replace("\\", "/").strip()
        raw_name = parts[-1].split(" ")[0].strip()
        by_module.setdefault(module, []).append((raw_name, status))
    return by_module


def friendly(raw_name):
    """Return a human-readable label for a test function name."""
    # Strip parametrize suffix like [changes0-40.0-25.0]
    base = raw_name.split("[")[0]
    if base in LABELS:
        return LABELS[base]
    # Auto-format: drop 'test_' prefix, replace underscores
    return base.replace("test_", "", 1).replace("_", " ").capitalize()


def status_icon(status):
    return {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}.get(status, "????")


def print_report(by_module, elapsed):
    W = 80
    sep  = "=" * W
    thin = "-" * W

    total_pass = sum(1 for tests in by_module.values() for _, s in tests if s == "PASS")
    total_fail = sum(1 for tests in by_module.values() for _, s in tests if s == "FAIL")
    total_skip = sum(1 for tests in by_module.values() for _, s in tests if s == "SKIP")
    total      = total_pass + total_fail + total_skip

    print()
    print(sep)
    print(f"{'GeoVision Backend  -  Test Report':^{W}}")
    print(sep)
    print(f"  {'Module / Test':<56}  {'Result':>6}")
    print(thin)

    shown_modules = set()

    for section_name, module_path in SECTIONS:
        # normalise slashes for lookup
        key = module_path.replace("\\", "/")
        tests = by_module.get(key)
        if not tests:
            continue
        shown_modules.add(key)

        sec_pass = sum(1 for _, s in tests if s == "PASS")
        sec_fail = sum(1 for _, s in tests if s == "FAIL")
        badge = f"[{sec_pass}/{len(tests)}]"

        print()
        print(f"  {section_name.upper():<56}  {badge:>6}")
        print(f"  {'  ' + module_path:<56}")
        print()

        for raw_name, status in tests:
            label = friendly(raw_name)
            icon  = status_icon(status)
            # Truncate long labels so the line stays within W chars
            max_label = 54
            if len(label) > max_label:
                label = label[:max_label - 2] + ".."
            print(f"    {label:<54}  {icon:>6}")

    # Any module not in SECTIONS (shouldn't happen, but catch stray tests)
    extras = {k: v for k, v in by_module.items() if k not in shown_modules}
    if extras:
        print()
        print(f"  OTHER")
        print()
        for module, tests in extras.items():
            for raw_name, status in tests:
                label = friendly(raw_name)
                icon  = status_icon(status)
                if len(label) > 54:
                    label = label[:52] + ".."
                print(f"    {label:<54}  {icon:>6}")

    print()
    print(sep)
    if total_fail == 0:
        summary = f"  ALL TESTS PASSED   {total_pass} passed"
    else:
        summary = f"  {total_pass} passed  |  {total_fail} FAILED  |  {total_skip} skipped"
    print(f"{summary}   ({elapsed:.1f}s)")
    print(sep)
    print()


if __name__ == "__main__":
    print("\nRunning GeoVision test suite - please wait...\n")
    output, elapsed = run_tests()
    by_module = parse_results(output)
    print_report(by_module, elapsed)

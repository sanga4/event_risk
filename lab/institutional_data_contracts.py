#!/usr/bin/env python3
"""Institutional EventRisk data contracts: auditable expectations, not fake data.

Each dataset specifies required data fields, unit/currency conventions, time
semantics and release gates. A field is NOT certified merely by existing.
This registry is source controlled and is materialized alongside per-field
non-null counts by phase1_field_coverage.py.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Contract:
    dataset: str
    source_table: str
    grain: str
    tier: str
    unit_policy: str
    temporal_policy: str
    license_policy: str
    # required_technical: these MUST be present in implemented source table.
    # required_institutional: absent/uncertified means no institutional release.
    required_technical: tuple[str, ...]
    required_institutional: tuple[str, ...]
    optional: tuple[str, ...] = ()
    notes: str = ""


CONTRACTS = (
    Contract(
        "event_quote_receipt","lab_live_market_captures_v1",
        "venue|market_id|run_id","source_capture","probability_decimal_0_1",
        "retrieved_at_is_not_original_quote_at","venue_market_data_rights",
        ("run_id","venue","market_id","capture_received_at","yes_probability",
         "quote_basis","source_record_sha256","source_response_sha256",
         "contract_sha256","capture_time_verified","data_use_class"),
        ("provider_quote_at","provider_quote_freshness_verified",
         "historical_point_in_time_released"),
        ("yes_bid","yes_ask","last_price","event_id","status","source_url",
         "contract_json","question","event_title"),
        "Receipt timestamps are observable; original quote time is currently unverified."),
    Contract(
        "market_contract_version","lab_live_market_contract_versions_v1",
        "venue|market_id|contract_sha256","source_capture","identity_not_price",
        "first_seen_vintage","venue_metadata_rights",
        ("venue","market_id","contract_sha256","first_captured_at",
         "first_run_id","contract_json"),
        ("source_published_at","original_contract_effective_at",
         "contract_revision_reason"),
        (),
        "Version by first receipt; contract source publication and original effectivity missing."),
    Contract(
        "historical_market_quote","market_snapshots",
        "venue|market_id|ts|source","retrospective","probability_decimal_0_1",
        "backfill_event_time_not_retrieval_time","market_history_rights",
        ("venue","market_id","ts","source"),
        ("retrieved_at","provider_quote_published_at","original_payload_sha256",
         "contract_asof_sha256"),
        ("yes_bid","yes_ask","last"),
        "The 2021-2026 backfill is not independent point-in-time proof."),
    Contract(
        "factor_definition","lab_factor_catalog",
        "factor_id","catalog","family_and_unit_specific",
        "source_spec_versioned","per_provider_license",
        ("factor_id","name","family","unit","provider","provider_series",
         "license_class","active"),
        ("shock_transform","publication_calendar","source_timezone",
         "first_available_lag","factor_definition_version",
         "redistribution_allowed","factor_direction_convention"),
        (),
        "Never mistake nominal-minus-real yield proxy for CPI breakeven."),
    Contract(
        "factor_observation","lab_factor_observations",
        "factor_id|observed_date|revision_source_hash","raw_factor",
        "source_native_yield_percent_or_index",
        "warehouse_ingest_vs_provider_release_vintage","series_license",
        ("factor_id","observed_date","value","unit","ingested_at",
         "availability_at","availability_basis","provider",
         "source_url","record_sha256","run_id"),
        ("source_published_at","source_realtime_start","source_realtime_end",
         "official_vintage_id","original_source_payload_sha256",
         "publication_time_independently_verified"),
        (),
        "FRED realtime intervals may track revisions; don't backdate warehouse ingestion."),
    Contract(
        "security_price","security_prices",
        "ticker|date|source","raw_security","native_currency_price",
        "backfill_fetched_at_not_historical_publication","yahoo_reuse_approval",
        ("ticker","date","close","adj_close","volume","currency",
         "source","fetched_at","run_id"),
        ("permanent_security_id","exchange_mic","asset_class",
         "price_adjustment_method","corporate_action_vintage",
         "total_return_verified","symbol_history_valid_from",
         "symbol_history_valid_to","original_price_published_at",
         "price_license_approved","fx_translation_rule",
         "issuer_country"),
        (),
        "Adjusted close is not verified total-return index or PIT corporate-action vintage."),
    Contract(
        "security_adjusted_return","lab_security_returns_retro_v1",
        "ticker|observed_date","derived_security","USD_log_return_bps",
        "historical_expost_adjusted_close","yahoo_reuse_approval",
        ("ticker","observed_date","adjusted_close","previous_close",
         "previous_observed_date","return_bps","currency","source",
         "fetched_at","source_run_id","large_absolute_log_return",
         "source_availability_pit_verified","corporate_action_vintage_verified",
         "data_use_class","build_id"),
        ("independent_price_source_replay_uri","corporate_action_evidence_id",
         "primary_listing_calendar","benchmark_currency_fx_vintage",
         "sector_asof","issuer_asof"),
        (),
        "SPY is a same-day market control; return is not a forward prediction."),
    Contract(
        "factor_shock","lab_rate_shocks_retro_v1",
        "factor_id|observed_date","derived_factor","yield_change_bp",
        "historical_expost_source_record","source_series_rights",
        ("factor_id","observed_date","yield_level_pct",
         "previous_yield_level_pct","previous_observed_date","shock_bps",
         "provider","source_record_sha256","source_ingested_at",
         "source_availability_at","published_vintage_independently_verified",
         "data_use_class","build_id"),
        ("official_source_publication_at","published_version_id",
         "asof_tradable_at","calendar_close_convention"),
        (),
        "Yield changes cannot serve as equity style total returns."),
    Contract(
        "event_economic_factor_mapping","lab_forward_mapping_hypotheses_v1",
        "path_id","semantic_research","non_numeric_channel",
        "mapping_first_available_before_event","source_review_and_license",
        ("path_id","proposition_id","event_channel","mechanism_id",
         "macro_variable_id","factor_id","mapping_available_at",
         "first_eligible_capture_at","factor_ingested_at",
         "factor_available_at","evidence_approved",
         "historically_backtest_released","historical_mapping_lookahead"),
        ("reviewer_id","independent_second_reviewer_id","reviewed_at",
         "evidence_source_published_at","evidence_sha256",
         "evidence_license","mapping_valid_from","mapping_valid_to",
         "peer_review_status"),
        ("entity_id","event_action","source_graph_edge_id","graph_asof"),
        "A model-generated economic channel hypothesis is not evidence."),
    Contract(
        "security_rate_beta","lab_security_rate_betas_retro_v1",
        "ticker|factor_id|build_id","derived_beta",
        "asset_log_return_bp_per_1bp_yield","expost_70_30_holdout",
        "price_factor_rights_and_mrm",
        ("ticker","factor_id","market_benchmark","n_observations",
         "n_train","n_test","beta_rate","beta_spy",
         "hac_rate_se","rate_bh_fdr_q","test_r2_vs_spy_only",
         "point_in_time_verified","independent_data_rights_verified",
         "released_for_risk_use","model_status","build_id"),
        ("permanent_security_id","asof_training_cutoff","original_data_vintages",
         "model_risk_approval_id","factor_covariance_id",
         "portfolio_position_asof","clustered_confidence_interval",
         "model_stability_score","residual_exposure_checks"),
        ("rate_ci95_lower","rate_ci95_upper","large_return_observations"),
        "One-yield-plus-SPY coefficient is NOT multivariate portfolio exposure."),
    Contract(
        "event_innovation","lab_event_innovations_v1",
        "event_id|contract_version|announcement_at|horizon","not_loaded",
        "event_surprise_probability_pp","pre_event_consensus_and_cutoff",
        "provider_market_terms",
        ("event_id","announcement_at","contract_version",
         "prior_probability","post_probability","expected_probability_change",
         "event_surprise_pp","pre_event_known_at","model_version"),
        ("provider_announcement_published_at","exchange_quote_published_at",
         "innovation_method_approved","surprise_independent_reviewer"),
        (),
        "No credible event innovation exists merely from same-day delta probability."),
    Contract(
        "asset_factor_model","lab_multifactor_security_betas_v1",
        "permanent_security_id|asof_date|factor_model_version","not_loaded",
        "asset_excess_return_vs_pit_factor_shocks",
        "asof_training_window_rolling_oos","approved_prices_and_factor_rights",
        ("permanent_security_id","asof_date","factor_id","factor_model_version",
         "beta","beta_unit","standard_error","n_effective","trained_through",
         "holdout_through","factor_covariance_version","residual_risk",
         "status","source_digest"),
        ("model_validation_id","calendar_cluster_robust_se",
         "independently_verified_asof","license_use_approved",
         "stress_scenario_coverage"),
        (),
        "Require a licensed market+rates+FX+credit+commodity/style model."),
    Contract(
        "position_exposure","lab_portfolio_positions_v1",
        "portfolio_id|permanent_security_id|asof_timestamp","not_loaded",
        "position_native_currency_and_base_currency",
        "position_and_fx_cutoffs","portfolio_restricted",
        ("portfolio_id","permanent_security_id","asof_timestamp",
         "quantity","price","market_value","native_currency","base_currency",
         "base_fx_rate","base_market_value","position_source_hash"),
        ("position_approved_at","fx_rate_available_at","holdings_license"),
        (),
        "No user portfolio exposures should be inferred without holdings."),
    Contract(
        "factor_scenario","lab_factor_scenarios_v1",
        "scenario_id|horizon|factor_model_version","not_loaded",
        "shock_size_and_beta_unit_consistent",
        "scenario_versioned_before_prediction","governed_model_and_positions",
        ("scenario_id","factor_id","shock_value","shock_unit","horizon",
         "scenario_source","scenario_created_at","risk_model_version",
         "approved_for_use"),
        ("scenario_owner","tail_dependence_model",
         "confidence_interval","liquidity_limit"),
        (),
        "Scenario impact cannot be calculated without asset beta and positions."),
    Contract(
        "source_release_calendar","lab_source_release_vintages_v1",
        "provider|series_id|published_at|revision_id","not_loaded",
        "source_native","official_release_revision_time","provider_terms",
        ("provider","series_id","observation_date",
         "release_published_at","revision_id","reported_value",
         "source_payload_sha256","retrieved_at","timezone","license_class"),
        ("first_publicly_available_at","independent_replay_verified"),
        (),
        "ALFRED date-vintage resolution may be only a day, not intraday hour."),
    Contract(
        "risk_factor_portfolio","lab_style_factor_returns_v1",
        "provider|region|factor_id|date|vintage","not_loaded",
        "simple_total_return_or_excess_return_decimal",
        "provider_historical_revision_calendar","style_provider_rights",
        ("provider","region","factor_id","observed_date",
         "factor_return","unit","currency","benchmark",
         "portfolio_construction_id","vintage_date","downloaded_at"),
        ("original_publication_at","provider_corporate_action_policy",
         "universe_asof","licensed_redistribution"),
        (),
        "Fama/French research factor portfolios can revise historical returns."),
)


def validate_contracts() -> None:
    pairs = set()
    for c in CONTRACTS:
        assert c.dataset not in (p[0] for p in pairs)
        assert c.tier in {"source_capture","catalog","raw_factor","raw_security",
                          "retrospective","derived_security","derived_factor",
                          "semantic_research","derived_beta","not_loaded"}
        fields = c.required_technical + c.required_institutional + c.optional
        assert len(fields)==len(set(fields)), c.dataset
        assert c.dataset and c.source_table and c.grain
        for field in fields:
            assert field.isidentifier() and field.islower(), (c.dataset,field)
        pairs.add((c.dataset,c.source_table))


if __name__=="__main__":
    validate_contracts()
    print("CONTRACT_DATASETS=",len(CONTRACTS))
    print("REQUIRED_FIELDS=",sum(len(c.required_technical)+len(c.required_institutional) for c in CONTRACTS))

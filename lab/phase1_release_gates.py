#!/usr/bin/env python3
"""Materialize auditable Phase I release gates; never self-approve a release."""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
import duckdb

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-gates-v2.2.0"

def main():
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only":
        raise RuntimeError("LAB_RESEARCH_SCOPE must be internal-only")
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("require full source commit SHA")
    code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build_id=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    gates=[
        ("genuine_pit_factor_panel",
         f"SELECT COUNT(*) FROM {P}lab_event_factor_panel_v3 WHERE observed_mode='as_known' AND data_lookahead_warning=FALSE",
         10000,"MIN_COUNT", "Require >=10,000 vintage-correct as-known observations; zero currently"),
        ("reviewed_factor_evidence",
         f"SELECT COUNT(*) FROM {P}lab_relations WHERE status IN ('approved','accepted') AND evidence_id IS NOT NULL",
         1,"MIN_COUNT","Require independently approved factor mappings linked to evidence"),
        ("source_evidence",
         f"SELECT COUNT(*) FROM {P}lab_evidence",
         1,"MIN_COUNT","Evidence records must support signed reviewer decisions"),
        ("independent_mapping_reviews",
         f"SELECT COUNT(*) FROM {P}lab_mapping_review_cases WHERE reviewer IS NOT NULL AND reviewed_at IS NOT NULL AND analyst_decision IS NOT NULL",
         10,"MIN_COUNT","At least 10 analyst-reviewed mapping samples; not an approval by itself"),
        ("real_time_venue_data_recent",
         f"SELECT COALESCE(date_diff('hour',MAX(ts),current_timestamp),999999) FROM {P}market_snapshots WHERE source='realtime'",
         12,"MAX_HOURS","Realtime snapshots must be younger than 12 hours"),
        ("prospective_dual_venue_capture_recent",
         f"SELECT COUNT(*) FROM {P}lab_capture_feed_freshness_v1 WHERE venue IN ('kalshi','polymarket') AND collector_operational_recently",
         2,"MIN_COUNT","Both Kalshi and Polymarket need recently successful, non-empty prospective captures; not exchange quote certification"),
        ("prospective_capture_receipt_provenance",
         f"SELECT COUNT(*) FROM {P}lab_live_market_captures_v1 WHERE capture_time_verified AND source_record_sha256 IS NOT NULL AND LENGTH(source_record_sha256)=64",
         1000,"MIN_COUNT","At least 1,000 independently receipt-timestamped source records with SHA256 hashes; NOT provider publication-time validation"),
        ("provider_quote_freshness_evidence",
         f"SELECT COUNT(*) FROM {P}lab_live_market_captures_v1 WHERE provider_quote_freshness_verified AND provider_quote_at IS NOT NULL",
         1,"MIN_COUNT","Need independently verified original venue quote times; HTTP receipt timestamps alone are insufficient"),
        ("warehouse_asof_prospective_grid_materialized",
         f"SELECT COUNT(*) FROM {P}lab_prospective_event_factor_grid_v1 WHERE factor_warehouse_asof_verified AND NOT historical_backtest_released",
         1000,"MIN_COUNT","Prospective event/factor co-observation grid has at least 1,000 warehouse-as-of rows; this is not independent provider PIT"),
        ("warehouse_asof_temporal_leakage",
         f"SELECT COUNT(*) FROM {P}lab_prospective_event_factor_grid_v1 WHERE factor_ingested_at>event_capture_at OR factor_available_at>event_capture_at",
         0,"MAX_COUNT","Strictly zero factor observations with warehouse ingest or availability after event capture cutoff"),
        ("prospective_mapping_review_queue_prepared",
         f"SELECT COUNT(*) FROM {P}lab_forward_mapping_review_queue_v1 WHERE review_state='pending_human_review' AND NOT released_for_signal_use",
         50,"MIN_COUNT","At least 50 forward-mapping hypotheses in traceable pending-review queue; no analyst decision implied"),
        ("forward_mapping_candidate_temporal_leakage",
         f"SELECT COUNT(*) FROM {P}lab_forward_mapping_hypotheses_v1 WHERE mapping_available_at > first_eligible_capture_at OR graph_asof > first_eligible_capture_at OR factor_ingested_at > first_eligible_capture_at OR factor_available_at > first_eligible_capture_at OR evidence_approved OR historically_backtest_released",
         0,"MAX_COUNT","Forward mapping hypothesis staging must not use post-capture warehouse information or claim approved evidence/release"),
        ("market_controlled_security_rate_research_backfill",
         f"SELECT COUNT(*) FROM {P}lab_security_rate_betas_retro_v1 WHERE model_status='EX_POST_MARKET_CONTROLLED_SENSITIVITY_NOT_PIT' AND NOT released_for_risk_use",
         500,"MIN_COUNT","Backfilled retrospective SPY-controlled security sensitivities; successful calculations do not validate beta release"),
        ("security_prices_original_vintage_certified",
         f"SELECT COUNT(*) FROM {P}lab_security_returns_retro_v1 WHERE source_availability_pit_verified AND corporate_action_vintage_verified",
         10000,"MIN_COUNT","Require verified historic first availability AND price corporate-action-adjustment revision vintages"),
        ("unreviewed_large_price_moves",
         f"SELECT COUNT(*) FROM {P}lab_security_returns_retro_v1 WHERE large_absolute_log_return",
         0,"MAX_COUNT","Outlier adjusted returns require independent corporate-action and market-event investigation before release"),
        ("security_betas_independently_approved",
         f"SELECT COUNT(*) FROM {P}lab_security_rate_betas_retro_v1 WHERE point_in_time_verified AND independent_data_rights_verified AND released_for_risk_use",
         1,"MIN_COUNT","Production model risk approval and data provenance must precede any released security beta"),
        ("institutional_field_contract_inventory",
         f"SELECT COUNT(*) FROM {P}lab_institutional_field_contracts_v1 WHERE build_id=(SELECT build_id FROM {P}lab_institutional_data_contract_builds_v1 ORDER BY built_at DESC LIMIT 1)",
         250,"MIN_COUNT","All risk data products have versioned source fields, units, time and licensing expectations; does NOT mean populated or approved"),
        ("institutional_required_field_certification",
         f"SELECT COUNT(*) FROM {P}lab_institutional_dataset_audit_v1 WHERE build_id=(SELECT build_id FROM {P}lab_institutional_data_contract_builds_v1 ORDER BY built_at DESC LIMIT 1) AND source_certification_complete",
         16,"MIN_COUNT","Require all 16 source domains including portfolio and event innovations to have independently certified complete fields"),
        ("rate_factor_covariance_collinearity_report",
         f"SELECT COUNT(*) FROM {P}lab_factor_collinearity_pairs_v1 WHERE build_id=(SELECT build_id FROM {P}lab_factor_diagnostics_builds_v1 ORDER BY built_at DESC LIMIT 1)",
         150,"MIN_COUNT","Computed pairwise risk-factor correlations with actual unit-preserving source returns; this is NOT a release approval"),
        ("independent_rate_factor_vintage_certification",
         f"SELECT COUNT(*) FROM {P}lab_factor_exposure_specifications_v1 WHERE build_id=(SELECT build_id FROM {P}lab_factor_diagnostics_builds_v1 ORDER BY built_at DESC LIMIT 1) AND independently_verified_source_vintage AND eligible_for_independent_production_model",
         18,"MIN_COUNT","Release requires independent source/rights and as-of vintage verification, plus collinearity-safe multi-factor selection"),
        ("us_equity_style_source_archive_research_backfill",
         f"SELECT COUNT(*) FROM {P}lab_style_factor_returns_v1 WHERE research_status='EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED' AND NOT approved_for_institutional_risk_use",
         100000,"MIN_COUNT","Official daily US FF5/MOM source snapshots backfilled with original file checksums; NO historical PIT or redistribution rights implied"),
        ("us_equity_style_vintages_and_rights_certified",
         f"SELECT COUNT(DISTINCT factor_id) FROM {P}lab_style_factor_returns_v1 WHERE source_publication_time_independently_verified AND historical_point_in_time_verified AND licensed_for_distribution AND approved_for_institutional_risk_use",
         7,"MIN_COUNT","Require source revision/publication vintage audit, permitted-use license and independent model approval for all 7 research US factor labels"),
        ("official_ecb_eur_fx_research_loaded",
         f"SELECT COUNT(*) FROM {P}lab_fx_reference_rates_retro_v1 WHERE research_only AND NOT historical_point_in_time_verified AND NOT is_executable_spot_fx_quote",
         30000,"MIN_COUNT","Loaded source-hashed ECB EUR-base reference prices; information only, not executable FX quotes"),
        ("cross_asset_factor_covariance_research_diagnostic",
         f"SELECT COUNT(*) FROM {P}lab_cross_asset_factor_covariance_v1 WHERE build_id=(SELECT build_id FROM {P}lab_cross_asset_risk_diagnostics_v1 ORDER BY built_at DESC LIMIT 1) AND NOT approved_portfolio_risk_covariance",
         49,"MIN_COUNT","Seven-factor unit-standardized covariance study exists; holdout drift/rights and PIT release stay separate"),
        ("ecb_original_provider_vintage_and_source_rights_certification",
         f"SELECT COUNT(DISTINCT quote_currency) FROM {P}lab_fx_reference_rates_retro_v1 WHERE provider_publish_time_independently_verified AND rights_for_risk_redistribution_verified AND historical_point_in_time_verified",
         7,"MIN_COUNT","Require original per-observation source publication and rights certification before FX risk input use; ECB prices remain informational"),
        ("nyfed_sofr_effr_reference_research_loaded",
         f"SELECT COUNT(*) FROM {P}lab_nyfed_rate_observations_retro_v1 WHERE research_only AND NOT production_risk_input_approved",
         500,"MIN_COUNT","Two publisher-sourced SOFR/EFFR annual rate percent histories are archived as internal research snapshots; effective date is not original publication"),
        ("nyfed_funding_provider_vintages_rights_verified",
         f"SELECT COUNT(DISTINCT series_id) FROM {P}lab_nyfed_rate_observations_retro_v1 WHERE provider_historical_revision_asof_verified AND first_published_timestamp_verified AND downstream_license_approved AND production_risk_input_approved",
         2,"MIN_COUNT","Independent original NY Fed rate first-publication/revision times and data-use approval required; percent-rate deltas are not surprises"),
        ("rolling_crossasset_covariance_diagnostics_materialized",
         f"SELECT COUNT(*) FROM {P}lab_cross_asset_rolling_windows_v1 WHERE build_id=(SELECT build_id FROM {P}lab_cross_asset_rolling_builds_v1 ORDER BY created_at DESC LIMIT 1)",
         15,"MIN_COUNT","252 day train and 63-day forward test regime screens with 21-day steps built; not a validated risk product"),
        ("rolling_crossasset_covariance_regime_stability_screen",
         f"SELECT COUNT(*) FROM {P}lab_cross_asset_rolling_windows_v1 WHERE build_id=(SELECT build_id FROM {P}lab_cross_asset_rolling_builds_v1 ORDER BY created_at DESC LIMIT 1) AND requires_independent_regime_review",
         0,"MAX_COUNT","No rolling covariance regime drift flags under preregistered materiality threshold; independent risk and source rights still separate"),
        ("institutional_source_family_evidence_inventory",
         f"SELECT COUNT(*) FROM {P}lab_source_family_evidence_v1 WHERE build_id=(SELECT build_id FROM {P}lab_source_family_evidence_builds_v1 ORDER BY created_at DESC LIMIT 1)",
         16,"MIN_COUNT","Source-count, temporal-grain and independent-certification gap ledger across 16 institutional source families"),
        ("institutional_source_family_rights_and_pit_certification",
         f"SELECT COUNT(DISTINCT domain) FROM {P}lab_source_family_evidence_v1 WHERE build_id=(SELECT build_id FROM {P}lab_source_family_evidence_builds_v1 ORDER BY created_at DESC LIMIT 1) AND provider_original_publication_verified AND commercial_reuse_approved AND institutional_factor_model_approved",
         16,"MIN_COUNT","All 16 source families require real original source time, permitted-use evidence and independent model-risk signoff; scripts cannot self-certify"),
        ("rolling_security_six_factor_beta_stability_research",
         f"SELECT COUNT(*) FROM {P}lab_ff6_rolling_beta_windows_v1 WHERE build_id=(SELECT build_id FROM {P}lab_ff6_rolling_beta_builds_v1 ORDER BY built_at DESC LIMIT 1)",
         900,"MIN_COUNT","Require 378 train/63 holdout/63 step rolling six-factor security beta diagnostics before any stability review"),
        ("rolling_security_six_factor_beta_stability_certification",
         f"SELECT COUNT(*) FROM {P}lab_ff6_rolling_beta_windows_v1 WHERE build_id=(SELECT build_id FROM {P}lab_ff6_rolling_beta_builds_v1 ORDER BY built_at DESC LIMIT 1) AND (adjacent_beta_change_requires_review OR poor_holdout_relative_error_requires_review)",
         0,"MAX_COUNT","No unresolved rolling beta coefficient instability or weak holdout windows under frozen accepted thresholds; independent model risk still required"),
        ("independent_security_mapping_evidence_worklist",
         f"SELECT COUNT(*) FROM {P}lab_independent_evidence_requirements_v1 WHERE build_id=(SELECT build_id FROM {P}lab_independent_evidence_builds_v1 ORDER BY built_at DESC LIMIT 1) AND NOT factual_evidence_verified",
         400,"MIN_COUNT","Every flagged price/FX/mapping case has original source and second-review request ledger; not independent approval"),
        ("original_source_evidence_and_second_signoffs",
         f"SELECT COUNT(*) FROM {P}lab_independent_evidence_requirements_v1 WHERE build_id=(SELECT build_id FROM {P}lab_independent_evidence_builds_v1 ORDER BY built_at DESC LIMIT 1) AND factual_evidence_verified AND independent_review_complete AND institutional_risk_use_approved AND original_source_uri IS NOT NULL AND source_archived_sha256 IS NOT NULL AND reviewer_id IS NOT NULL AND independent_second_reviewer_id IS NOT NULL",
         10,"MIN_COUNT","Require at least 10 complete original-source archived evidence records with attributable dual reviews; no automated approval"),
        ("security_vendor_adjustment_ratio_reconciliation",
         f"SELECT COUNT(*) FROM {P}lab_security_adjustment_ratio_changes_v1 WHERE build_id=(SELECT build_id FROM {P}lab_security_adjustment_audit_builds_v1 ORDER BY created_at DESC LIMIT 1) AND NOT original_issuer_action_verified",
         250,"MIN_COUNT","Audit daily vendor adjusted-close over close ratios for source-meaningful jumps, reconcile large-return cases, do not assert corporate action causes"),
        ("verified_security_corporate_action_vintages",
         f"SELECT COUNT(*) FROM {P}lab_security_adjustment_ratio_changes_v1 WHERE original_issuer_action_verified AND original_vendor_revision_asof_verified AND external_data_rights_approved AND approved_for_institutional_beta",
         10,"MIN_COUNT","Original issuer action, exchange reference and time-vintage must be verified with independent rights and signoffs"),
        ("cross_asset_covariance_shrinkage_stress_research",
         f"SELECT COUNT(*) FROM {P}lab_factor_covariance_shrinkage_tests_v1 WHERE build_id=(SELECT build_id FROM {P}lab_factor_covariance_shrinkage_builds_v1 ORDER BY built_at DESC LIMIT 1) AND hindsight_selection_prohibited",
         6,"MIN_COUNT","Six preregistered shrinkages have retrospective holdout diagnostics; do not select from holdout for production"),
        ("cross_asset_covariance_stress_robustness_certification",
         f"SELECT COUNT(*) FROM {P}lab_factor_covariance_shrinkage_tests_v1 WHERE build_id=(SELECT build_id FROM {P}lab_factor_covariance_shrinkage_builds_v1 ORDER BY built_at DESC LIMIT 1) AND relative_holdout_covariance_distance>0.50",
         0,"MAX_COUNT","No prespecified shrinkage candidate breaches 50% covariance holdout drift, source PIT/rights and independent model-risk review remain distinct"),
        ("walkforward_regime_covariance_scores_research",
         f"SELECT COUNT(*) FROM {P}lab_regime_cov_daily_scores_v1 WHERE build_id=(SELECT build_id FROM {P}lab_regime_cov_research_builds_v1 ORDER BY created_at DESC LIMIT 1) AND training_only_factor_standardization AND NOT approved_institutional_risk_model",
         600,"MIN_COUNT","Compare four predeclared daily one-step fixed and EWMA covariance estimators on a strictly chronological last-25-percent research holdout without selecting a hindsight winner"),
        ("walkforward_regime_covariance_source_rights_and_model_validation",
         f"SELECT COUNT(*) FROM {P}lab_regime_cov_model_comparisons_v1 WHERE source_historic_publication_asof_verified AND risk_model_independently_validated AND licensed_risk_use_approved AND NOT posthoc_winner_selection_for_production",
         1,"MIN_COUNT","Original provider revisions, approved distribution rights, independent model committee and prospective untouched test are required regardless of statistical scores"),
        ("security_extreme_return_beta_sensitivity_research",
         f"SELECT COUNT(*) FROM {P}lab_ff6_price_extreme_sensitivity_v1 WHERE build_id=(SELECT build_id FROM {P}lab_ff6_price_extreme_builds_v1 ORDER BY built_at DESC LIMIT 1) AND NOT licensed_institutional_beta_approved",
         45,"MIN_COUNT","Research-only, same-holdout FF6 beta sensitivity tests that remove flagged source observations from the fitting TRAIN only and never delete source prices"),
        ("security_extreme_return_beta_source_robustness_certification",
         f"SELECT COUNT(*) FROM {P}lab_ff6_price_extreme_sensitivity_v1 WHERE build_id=(SELECT build_id FROM {P}lab_ff6_price_extreme_builds_v1 ORDER BY built_at DESC LIMIT 1) AND beta_shift_review_threshold_exceeded",
         0,"MAX_COUNT","No unresolved relative beta shifts over 10% when extreme vendor adjusted returns are excluded from training; original corporate action evidence and rights separately required"),
        ("historical_quote_pit_fraction",
         f"SELECT 100.0 * COALESCE(AVG(CASE WHEN point_in_time_verified THEN 1.0 ELSE 0.0 END),0) FROM {P}lab_market_daily_historical_v1",
         80,"MIN_PERCENT","At least 80% of eligible history must have independently verified capture provenance"),
        ("independent_oos_candidate_signals",
         f"SELECT COUNT(*) FROM {P}lab_robust_regressions_v2 WHERE benjamini_hochberg_q < 0.05 AND oos_r2_vs_train_mean > 0 AND point_in_time_verified = TRUE",
         1,"MIN_COUNT","Pre-specified PIT holdout candidate; exploratory fits cannot satisfy this gate"),
        ("historical_research_pipeline_built",
         f"SELECT COUNT(*) FROM {P}lab_history_build_runs_v1",
         1,"MIN_COUNT","Historical research materialization exists; not PIT validity"),
        ("robust_diagnostics_pipeline_built",
         f"SELECT COUNT(*) FROM {P}lab_robust_regression_builds_v2",
         1,"MIN_COUNT","HAC/holdout/FDR diagnostic build exists; not causal approval")
    ]
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_release_gate_history_v1 (
      build_id VARCHAR NOT NULL,
      gate_id VARCHAR NOT NULL,
      measured_value DOUBLE,
      threshold DOUBLE,
      rule VARCHAR NOT NULL,
      gate_state VARCHAR NOT NULL,
      explanation VARCHAR NOT NULL,
      asof_utc TIMESTAMPTZ NOT NULL,
      source_commit VARCHAR NOT NULL,
      source_script_sha256 VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_release_gate_summary_v1 (
      build_id VARCHAR NOT NULL,
      asof_utc TIMESTAMPTZ NOT NULL,
      computed_gates BIGINT NOT NULL,
      passed_gates BIGINT NOT NULL,
      blocked_gates BIGINT NOT NULL,
      external_manual_gates BIGINT NOT NULL,
      released_to_institutional_production BOOLEAN NOT NULL,
      release_state VARCHAR NOT NULL
    )""")
    rows=[]
    for gate_id,sql,threshold,rule,explanation in gates:
        value=con.execute(sql).fetchone()[0]
        value=float(value) if value is not None else None
        passed = value is not None and (
            (rule=="MIN_COUNT" and value>=threshold) or
            (rule=="MAX_HOURS" and 0 <= value <= threshold) or
            (rule=="MAX_COUNT" and 0 <= value <= threshold) or
            (rule=="MIN_PERCENT" and value>=threshold)
        )
        rows.append((build_id,gate_id,value,float(threshold),rule,
                     "PASS" if passed else "BLOCKED",explanation,
                     datetime.now(timezone.utc),commit,code_sha))
    manual=[
        ("railway_service_data_rights", "Requires owner-confirmed Railway LAB_DATA_RIGHTS_ACK, scoped token and API keys"),
        ("independent_research_signoff", "Requires independent statistical and governance approval, not automatic data metrics"),
        ("licensed_market_data_review", "Review redistribution and credit licenses before external serving"),
        ("institutional_access_controls", "Requires verified authentication, monitoring, alerting and rollback"),
    ]
    for name,why in manual:
        rows.append((build_id,name,None,None,"MANUAL_EXTERNAL",
                     "BLOCKED_MANUAL",why,datetime.now(timezone.utc),commit,code_sha))
    n_pass=sum(row[5]=="PASS" for row in rows)
    con.execute("BEGIN TRANSACTION")
    try:
        con.executemany(f"INSERT INTO {P}lab_release_gate_history_v1 VALUES (?,?,?,?,?,?,?,?,?,?)",rows)
        con.execute(f"""INSERT INTO {P}lab_release_gate_summary_v1
            VALUES (?,current_timestamp,?,?,?, ?,FALSE,'BLOCKED_NOT_INSTITUTIONALLY_APPROVED')""",
            [build_id,len(gates),n_pass,len(gates)-n_pass,len(manual)])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    print(f"BUILD_ID={build_id}")
    print(f"AUTOMATIC_GATES={len(gates)} PASS={n_pass} BLOCKED={len(gates)-n_pass}")
    print(f"MANUAL_RELEASE_GATES_BLOCKED={len(manual)}")
    print("INSTITUTIONAL_RELEASE=BLOCKED")


if __name__=="__main__":
    main()

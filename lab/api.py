"""Read-only, fail-closed EventRisk Factor Lab research API.

The quantitative factor laboratory is not the independently reviewed Factors
catalog. It does not publish estimated betas, trade signals, or approved links.
"""
from __future__ import annotations

import hmac
import logging
import os
from datetime import date
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
app = FastAPI(title="EventRisk Factor Lab (research only)", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)

DATABASE = "eventrisk_factor_lab"  # Fixed allowlist, never interpolate a request value.
MAX_PAGE = 100


@app.middleware("http")
async def security_headers(request, call_next):
    result = await call_next(request)
    result.headers["Cache-Control"] = "no-store"
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["X-Frame-Options"] = "DENY"
    return result


def _valid_credentials() -> bool:
    # An API without explicitly provisioned auth credentials must never serve data.
    return bool(os.environ.get("LAB_API_KEYS", "").strip())


def _allowed_backend() -> bool:
    return (
        os.environ.get("LAB_DB", "") in (DATABASE, "md:" + DATABASE)
        and bool(os.environ.get("MOTHERDUCK_TOKEN", "").strip())
        and os.environ.get("LAB_DATA_RIGHTS_ACK", "").lower() in ("true", "acknowledged")
        and _valid_credentials()
    )


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    keys = [key.strip() for key in os.environ.get("LAB_API_KEYS", "").split(",") if key.strip()]
    if not keys or not x_api_key or not any(hmac.compare_digest(x_api_key, key) for key in keys):
        raise HTTPException(401, detail="API key required", headers={"WWW-Authenticate": "APIKey"})
    if not _allowed_backend():
        raise HTTPException(503, detail="Research API is not configured for serving")


def _query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Only SQL text authored in this module is executed. Parameters are bound."""
    # Dependency seam for offline contract tests; never exposed via an endpoint.
    injected = getattr(app.state, "query_fn", None)
    if injected is not None:
        return injected(sql, params)
    try:
        import duckdb
        conn = duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
        try:
            cursor = conn.execute(sql, params)
            names = [description[0] for description in cursor.description]
            return [dict(zip(names, values)) for values in cursor.fetchall()]
        finally:
            conn.close()
    except Exception:
        log.warning("Lab read-only backend query failed")
        raise HTTPException(503, detail="Research datastore unavailable") from None


@app.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
def ready(response: Response) -> dict[str, str]:
    # Readiness is deliberately negative unless credentials, rights and database are available.
    if not _allowed_backend():
        raise HTTPException(503, detail="not ready")
    try:
        rows = _query("SELECT 1 AS ok")
        if not rows or rows[0].get("ok") != 1:
            raise ValueError("readiness probe failed")
    except Exception:
        raise HTTPException(503, detail="not ready") from None
    return {"status": "ready"}


@app.get("/v1/research/status", dependencies=[Depends(require_api_key)])
def status() -> dict[str, Any]:
    rows = _query(
        "SELECT COUNT(*) AS rows_total, COUNT(DISTINCT proposition_id) AS propositions, "
        "COUNT(DISTINCT factor_id) AS factors, MIN(observed_date) AS first_event_date, "
        "MAX(observed_date) AS last_event_date, "
        "COUNT(*) FILTER (WHERE data_lookahead_warning OR mode <> 'as_known') AS blocked_pit_rows "
        "FROM eventrisk_factor_lab.main.lab_event_factor_panel_v2"
    )
    out = rows[0] if rows else {}
    # Reflect actual readiness, not the build status string.
    return {"research_only": True, "point_in_time_released": False,
            "mapping_approved": False, "panel_version": "v2", "metrics": out}


@app.get("/v1/factors", dependencies=[Depends(require_api_key)])
def factors(
    family: str | None = Query(None, max_length=80),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    rows = _query(
        "SELECT factor_id, name, family, unit, provider, provider_series, license_class "
        "FROM eventrisk_factor_lab.main.lab_factor_catalog "
        "WHERE active = TRUE AND license_class IN ('government_source_via_treasury', 'government_source_via_fred', 'derived_not_true_breakeven') "
        "AND (? IS NULL OR family = ?) "
        "ORDER BY factor_id LIMIT ? OFFSET ?", (family, family, limit, offset)
    )
    return {"items": rows, "limit": limit, "offset": offset, "research_only": True}


@app.get("/v1/research/panel", dependencies=[Depends(require_api_key)])
def panel(
    mode: str = Query("as_known", pattern="^(as_known|retrospective)$"),
    research_use: bool = False,
    proposition_id: str | None = Query(None, min_length=2, max_length=200),
    factor_id: str | None = Query(None, min_length=2, max_length=100),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    if mode == "as_known":
        raise HTTPException(409, detail="Point-in-time panel has not passed independent release gates")
    if not research_use or os.environ.get("LAB_ENABLE_RETROSPECTIVE_READ") != "true":
        raise HTTPException(403, detail="Retrospective research data are disabled")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, detail="date_from must not exceed date_to")
    rows = _query(
        "SELECT proposition_id, factor_id, observed_date, event_cutoff_at, mode, "
        "probability, event_delta_pp, factor_observed_date, factor_value, "
        "factor_daily_change, factor_change_unit, factor_carried_forward, "
        "factor_available_at, factor_source_provider, factor_source_sha256, "
        "data_lookahead_warning, research_run_id "
        "FROM eventrisk_factor_lab.main.lab_event_factor_panel_v2 "
        "WHERE mode = 'retrospective' "
        "AND (? IS NULL OR proposition_id = ?) AND (? IS NULL OR factor_id = ?) "
        "AND (? IS NULL OR observed_date >= ?) AND (? IS NULL OR observed_date <= ?) "
        "ORDER BY observed_date DESC, proposition_id, factor_id LIMIT ? OFFSET ?",
        (proposition_id, proposition_id, factor_id, factor_id,
         date_from, date_from, date_to, date_to, limit, offset)
    )
    return {"items": rows, "limit": limit, "offset": offset,
            "mode": "retrospective", "research_only": True,
            "point_in_time_released": False,
            "warning": "RETROSPECTIVE_LOOKAHEAD_NOT_BACKTEST_SAFE"}


@app.get("/v1/research/mappings/readiness", dependencies=[Depends(require_api_key)])
def mapping_readiness() -> dict[str, Any]:
    rows = _query(
        "SELECT (SELECT COUNT(*) FROM eventrisk_factor_lab.main.lab_event_factor_candidate_paths) AS candidates, "
        "(SELECT COUNT(*) FROM eventrisk_factor_lab.main.lab_mapping_review_cases "
        " WHERE analyst_decision IS NOT NULL AND reviewed_at IS NOT NULL AND reviewer IS NOT NULL) AS reviewed_cases, "
        "(SELECT COUNT(*) FROM eventrisk_factor_lab.main.lab_relations "
        " WHERE status IN ('approved','accepted') AND evidence_id IS NOT NULL) AS approved_evidenced_relations"
    )
    # Do not present potential links as actual approved links.
    return {"approved_for_research": False, "status": "BLOCKED_UNREVIEWED_MAPPING", "metrics": rows[0] if rows else {}}


@app.get("/v1/research/v3/builds", dependencies=[Depends(require_api_key)])
def builds_v3(limit: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
    """Published build manifests, NOT a production-ready release assertion."""
    rows = _query(
        "SELECT build_id, pipeline_version, source_commit, source_sha256, "
        "started_at, finished_at, first_event_date, last_event_date, "
        "retrospective_rows, as_known_rows, released_for_backtesting, "
        "execution_status FROM eventrisk_factor_lab.main.lab_phase1_build_runs_v3 "
        "ORDER BY finished_at DESC LIMIT ?", (limit,)
    )
    return {"builds": rows, "dataset_version": "v3", "research_only": True,
            "released_for_backtesting": False}


@app.get("/v1/research/v3/summary", dependencies=[Depends(require_api_key)])
def summary_v3() -> dict[str, Any]:
    rows = _query(
        "SELECT COUNT(*) AS rows_total, "
        "COUNT(*) FILTER (WHERE observed_mode='retrospective') AS retrospective_rows, "
        "COUNT(*) FILTER (WHERE observed_mode='as_known') AS as_known_rows, "
        "COUNT(DISTINCT proposition_id) AS distinct_propositions, "
        "COUNT(DISTINCT factor_id) AS observed_factors, "
        "MIN(observed_date) AS first_date, MAX(observed_date) AS last_date, "
        "COUNT(*) FILTER (WHERE data_lookahead_warning) AS lookahead_rows, "
        "COUNT(*) FILTER (WHERE relation_status='unreviewed_research_grid') AS unreviewed_rows "
        "FROM eventrisk_factor_lab.main.lab_event_factor_panel_v3"
    )
    return {"panel_version": "v3", "metrics": rows[0] if rows else {},
            "data_use": "internal_research_only",
            "released_for_backtesting": False, "independently_reviewed": False}


@app.get("/v1/research/v3/panel", dependencies=[Depends(require_api_key)])
def panel_v3(
    mode: str = Query("as_known", pattern="^(as_known|retrospective)$"),
    research_use: bool = False,
    proposition_id: str | None = Query(None, min_length=2, max_length=200),
    factor_id: str | None = Query(None, min_length=2, max_length=100),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    # The existence of an as-known row does not authorize treating the whole
    # dataset as an independently audited and licensed quantitative model.
    if mode == "as_known":
        raise HTTPException(409, detail="As-known v3 panel remains under independent release review")
    if not research_use or os.environ.get("LAB_ENABLE_RETROSPECTIVE_READ") != "true":
        raise HTTPException(403, detail="Retrospective research data are disabled")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, detail="date_from must not exceed date_to")
    rows = _query(
        "SELECT proposition_id, factor_id, observed_date, event_cutoff_at, "
        "event_known_at, event_last_quote_at, event_probability, event_delta_pp, "
        "factor_observed_date, factor_value, factor_unit, "
        "previous_aligned_factor_value, factor_change_bps, "
        "factor_carried_forward, factor_available_at, factor_ingested_at, "
        "factor_provider, factor_source_sha256, event_source_run, factor_source_run, "
        "observed_mode, data_lookahead_warning, relation_status, data_use_class, "
        "pipeline_version, build_id "
        "FROM eventrisk_factor_lab.main.lab_event_factor_panel_v3 "
        "WHERE observed_mode = 'retrospective' "
        "AND (? IS NULL OR proposition_id = ?) AND (? IS NULL OR factor_id = ?) "
        "AND (? IS NULL OR observed_date >= ?) AND (? IS NULL OR observed_date <= ?) "
        "ORDER BY observed_date DESC, proposition_id, factor_id LIMIT ? OFFSET ?",
        (proposition_id, proposition_id, factor_id, factor_id,
         date_from, date_from, date_to, date_to, limit, offset)
    )
    return {"items": rows, "limit": limit, "offset": offset,
            "mode": "retrospective", "research_only": True,
            "released_for_backtesting": False,
            "warning": "RETROSPECTIVE_AND_UNREVIEWED_NOT_CAUSAL_OR_BACKTEST_SAFE"}


@app.get("/v1/research/history/coverage", dependencies=[Depends(require_api_key)])
def history_coverage() -> dict[str, Any]:
    rows = _query(
        "SELECT COUNT(*) AS market_days, MIN(observed_date) AS first_date, "
        "MAX(observed_date) AS last_date, COUNT(DISTINCT observed_date) AS distinct_days, "
        "COUNT(*) FILTER (WHERE snapshot_source='backfill') AS backfilled_rows "
        "FROM eventrisk_factor_lab.main.lab_market_daily_historical_v1"
    )
    return {"metrics": rows[0] if rows else {},
            "source_availability_verified": False, "research_only": True,
            "warning": "BACKFILLED_EVENT_TIME_IS_NOT_POINT_IN_TIME_AVAILABILITY"}


@app.get("/v1/research/regressions", dependencies=[Depends(require_api_key)])
def exploratory_regressions(
    research_use: bool = False,
    factor_id: str | None = Query(None, min_length=2, max_length=100),
    venue: str | None = Query(None, max_length=50),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000)
) -> dict[str, Any]:
    # Associations are explicitly noncausal, retrospective and potentially
    # revision/measurement-biased. No unauthorized public release.
    if not research_use or os.environ.get("LAB_ENABLE_RETROSPECTIVE_READ") != "true":
        raise HTTPException(403, detail="Exploratory regressions are disabled")
    rows = _query(
        "SELECT factor_id, factor_unit, venue, predictor, response, "
        "n_sessions, distinct_months, first_date, last_date, "
        "slope, intercept, r_squared, correlation, model_class, "
        "point_in_time_verified, approved_for_decision_use, "
        "interpretation_warning, build_id "
        "FROM eventrisk_factor_lab.main.lab_exploratory_regressions_v1 "
        "WHERE (? IS NULL OR factor_id=?) AND (? IS NULL OR venue=?) "
        "ORDER BY factor_id,venue LIMIT ? OFFSET ?",
        (factor_id, factor_id, venue, venue, limit, offset)
    )
    return {"items": rows, "limit": limit, "offset": offset,
            "research_only": True, "point_in_time_verified": False,
            "approved_for_decision_use": False,
            "warning": "NO_CAUSAL_INFERENCE_NO_PVALUES_NO_TRADABLE_SIGNALS"}


@app.get("/v1/research/v2/robust-regressions", dependencies=[Depends(require_api_key)])
def robust_regressions(
    research_use: bool = False,
    factor_id: str | None = Query(None, min_length=2, max_length=100),
    venue: str | None = Query(None, max_length=50),
    predictor_timing: str | None = Query(None, pattern="^(contemporaneous|previous_venue_day)$"),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    """Exploratory HAC/holdout/FDR; no PIT provenance or signal approval."""
    if not research_use or os.environ.get("LAB_ENABLE_RETROSPECTIVE_READ") != "true":
        raise HTTPException(403, detail="Retrospective diagnostics are disabled")
    rows = _query(
        "SELECT factor_id, factor_unit, venue, predictor_timing, "
        "n_total, n_train, n_test, start_date, end_date, slope, intercept, "
        "in_sample_r2, newey_west_lags, hac_slope_se, z_approx, "
        "two_sided_normal_p, benjamini_hochberg_q, oos_r2_vs_train_mean, "
        "oos_rmse, baseline_rmse, research_label, point_in_time_verified, "
        "approved_for_decision_use, build_id "
        "FROM eventrisk_factor_lab.main.lab_robust_regressions_v2 "
        "WHERE (? IS NULL OR factor_id=?) AND (? IS NULL OR venue=?) "
        "AND (? IS NULL OR predictor_timing=?) "
        "ORDER BY factor_id, venue, predictor_timing LIMIT ? OFFSET ?",
        (factor_id, factor_id, venue, venue,
         predictor_timing, predictor_timing, limit, offset)
    )
    return {"items": rows, "limit": limit, "offset": offset,
            "research_only": True, "point_in_time_verified": False,
            "approved_for_decision_use": False,
            "warning": "EXPLORATORY_RETROSPECTIVE_ASSOCIATION_NOT_A_PREDICTIVE_SIGNAL"}


@app.get("/v1/research/production-gates", dependencies=[Depends(require_api_key)])
def production_gates() -> dict[str, Any]:
    """Latest materialized release assessment, including manual blockers."""
    latest = _query(
        "SELECT build_id, asof_utc, computed_gates, passed_gates, "
        "blocked_gates, external_manual_gates, "
        "released_to_institutional_production, release_state "
        "FROM eventrisk_factor_lab.main.lab_release_gate_summary_v1 "
        "ORDER BY asof_utc DESC LIMIT 1"
    )
    if not latest:
        raise HTTPException(503, detail="Release-gate report has not been materialized")
    identifier = latest[0]["build_id"]
    gates = _query(
        "SELECT gate_id, measured_value, threshold, rule, gate_state, explanation "
        "FROM eventrisk_factor_lab.main.lab_release_gate_history_v1 "
        "WHERE build_id=? ORDER BY gate_id", (identifier,)
    )
    # No self-approval: the materializer always records release_state=BLOCKED.
    return {"summary": latest[0], "gates": gates,
            "released_to_institutional_production": False,
            "research_only": True}


@app.get("/v1/research/live/overview", dependencies=[Depends(require_api_key)])
def prospective_capture_overview() -> dict[str, Any]:
    """Live capture provenance and per-venue operational status, not trading readiness."""
    totals = _query(
        "SELECT COUNT(*) AS capture_rows, COUNT(DISTINCT market_id) AS markets, "
        "COUNT(DISTINCT run_id) AS capture_runs, "
        "MIN(capture_received_at) AS first_capture_at, "
        "MAX(capture_received_at) AS latest_capture_at, "
        "COUNT(*) FILTER (WHERE historical_point_in_time_released) AS released_history_rows, "
        "COUNT(*) FILTER (WHERE provider_quote_freshness_verified) AS source_quote_verified "
        "FROM eventrisk_factor_lab.main.lab_live_market_captures_v1"
    )
    streams = _query(
        "SELECT venue, last_run_at, venue_state, reported_capture_count, age_minutes, "
        "collector_operational_recently, institutional_quote_freshness_certified "
        "FROM eventrisk_factor_lab.main.lab_capture_feed_freshness_v1 ORDER BY venue"
    )
    return {"metrics": totals[0] if totals else {}, "sources": streams,
            "source_quote_freshness_certified": False,
            "released_for_historical_backtesting": False,
            "research_only": True}


@app.get("/v1/research/live/changes", dependencies=[Depends(require_api_key)])
def prospective_changes(
    research_use: bool = False,
    venue: str | None = Query(None, pattern="^(kalshi|polymarket)$"),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    if not research_use or os.environ.get("LAB_ENABLE_PROSPECTIVE_READ") != "true":
        raise HTTPException(403, detail="Prospective market research is disabled")
    rows = _query(
        "SELECT proposition_id,venue,market_id,event_id, "
        "observed_date_utc,known_at,probability,previous_probability, "
        "previous_capture_at,probability_delta_pp,quote_basis, "
        "capture_time_verified,provider_quote_freshness_verified, "
        "historical_point_in_time_released,capture_provenance, "
        "released_for_historical_backtesting,run_id "
        "FROM eventrisk_factor_lab.main.lab_live_market_latest_v1 "
        "WHERE (? IS NULL OR venue = ?) "
        "ORDER BY known_at DESC,proposition_id LIMIT ? OFFSET ?",
        (venue,venue,limit,offset)
    )
    return {"items": rows, "limit": limit, "offset": offset,
            "research_only": True,
            "quote_freshness_certified": False,
            "released_for_historical_backtesting": False}


@app.get("/v1/research/forward/asof-coverage", dependencies=[Depends(require_api_key)])
def warehouse_asof_coverage() -> dict[str, Any]:
    """Warehouse as-of eligibility is NOT independent publication-time verification."""
    ledger = _query(
        "SELECT COUNT(*) AS factor_warehouse_vintages, "
        "COUNT(DISTINCT factor_id) AS factor_series, "
        "MIN(source_ingested_at) AS earliest_recorded_ingest, "
        "MAX(source_ingested_at) AS latest_recorded_ingest, "
        "COUNT(*) FILTER (WHERE independent_release_time_verified) "
        "AS independently_verified_release_records "
        "FROM eventrisk_factor_lab.main.lab_factor_warehouse_vintages_v1"
    )
    pairs = _query(
        "SELECT COUNT(*) AS event_factor_pairs, "
        "COUNT(DISTINCT proposition_id) AS market_propositions, "
        "COUNT(DISTINCT factor_id) AS related_factor_series, "
        "COUNT(*) FILTER (WHERE factor_ingested_at > event_capture_at "
        "OR factor_available_at > event_capture_at) AS future_warehouse_factor_pairs, "
        "COUNT(*) FILTER (WHERE historical_backtest_released) "
        "AS historical_backtest_released_pairs, "
        "MIN(event_capture_at) AS first_capture, "
        "MAX(event_capture_at) AS latest_capture "
        "FROM eventrisk_factor_lab.main.lab_prospective_event_factor_grid_v1"
    )
    return {"vintages": ledger[0] if ledger else {},
            "co_observations": pairs[0] if pairs else {},
            "research_only": True,
            "provider_publication_times_independently_verified": False,
            "exchange_quote_times_independently_verified": False,
            "reviewed_event_factor_relationships": False,
            "historical_backtest_released": False,
            "notice": "WAREHOUSE_ASOF_ONLY_NOT_INDEPENDENT_SOURCE_PIT"}


@app.get("/v1/research/forward/grid", dependencies=[Depends(require_api_key)])
def warehouse_asof_grid(
    research_use: bool = False,
    venue: str | None = Query(None, pattern="^(kalshi|polymarket)$"),
    factor_id: str | None = Query(None, min_length=2, max_length=100),
    proposition_id: str | None = Query(None, min_length=2, max_length=200),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000)
) -> dict[str, Any]:
    if not research_use or os.environ.get("LAB_ENABLE_PROSPECTIVE_READ") != "true":
        raise HTTPException(403, detail="Prospective research grid is disabled")
    rows = _query(
        "SELECT proposition_id, venue, market_id, event_run_id, "
        "event_capture_at, previous_event_capture_at, "
        "event_probability, event_delta_pp, event_quote_basis, "
        "factor_id, factor_observed_date, factor_value, factor_unit, "
        "factor_available_at, factor_ingested_at, factor_provider, "
        "factor_source_sha256, factor_license_class, "
        "event_receipt_time_verified, factor_warehouse_asof_verified, "
        "exchange_quote_time_independently_verified, "
        "factor_publication_time_independently_verified, "
        "event_to_factor_mapping_approved, historical_backtest_released, "
        "relation_status, data_use_class, source_build_id "
        "FROM eventrisk_factor_lab.main.lab_prospective_event_factor_grid_v1 "
        "WHERE (? IS NULL OR venue=?) AND (? IS NULL OR factor_id=?) "
        "AND (? IS NULL OR proposition_id=?) "
        "ORDER BY event_capture_at DESC, proposition_id, factor_id "
        "LIMIT ? OFFSET ?",
        (venue,venue,factor_id,factor_id,proposition_id,proposition_id,limit,offset)
    )
    return {"items": rows, "limit": limit, "offset": offset,
            "research_only": True, "warehouse_asof_only": True,
            "independent_provider_time_verified": False,
            "approved_mapping": False, "historical_backtest_released": False}


@app.get("/v1/research/mappings/forward/summary", dependencies=[Depends(require_api_key)])
def forward_mapping_summary() -> dict[str, Any]:
    hypotheses = _query(
        "SELECT COUNT(*) AS path_hypotheses, "
        "COUNT(DISTINCT proposition_id) AS covered_markets, "
        "COUNT(DISTINCT factor_id) AS eligible_factor_series, "
        "COUNT(*) FILTER (WHERE mapping_available_at > first_eligible_capture_at "
        "OR graph_asof > first_eligible_capture_at "
        "OR factor_ingested_at > first_eligible_capture_at "
        "OR factor_available_at > first_eligible_capture_at) AS asof_leakage_rows, "
        "COUNT(*) FILTER (WHERE evidence_approved OR historically_backtest_released) "
        "AS incorrectly_released_rows "
        "FROM eventrisk_factor_lab.main.lab_forward_mapping_hypotheses_v1"
    )
    reviews = _query(
        "SELECT COUNT(*) AS review_items, COUNT(DISTINCT venue) AS venues, "
        "COUNT(DISTINCT event_channel) AS channels, "
        "COUNT(*) FILTER (WHERE review_state='pending_human_review') AS pending, "
        "COUNT(*) FILTER (WHERE reviewer IS NOT NULL) AS attributed_reviews, "
        "COUNT(*) FILTER (WHERE released_for_signal_use) AS signals_released "
        "FROM eventrisk_factor_lab.main.lab_forward_mapping_review_queue_v1"
    )
    return {"hypotheses":hypotheses[0] if hypotheses else {},
            "review_queue":reviews[0] if reviews else {},
            "research_only": True, "mapping_approved": False,
            "approved_for_historical_backtests": False,
            "historical_graph_snapshot_lookahead": True}


@app.get("/v1/research/mappings/forward/queue", dependencies=[Depends(require_api_key)])
def forward_mapping_queue(
    review_state: str = Query("pending_human_review", pattern="^(pending_human_review)$"),
    venue: str | None = Query(None, pattern="^(kalshi|polymarket)$"),
    factor_id: str | None = Query(None, min_length=2, max_length=80),
    event_channel: str | None = Query(None, min_length=2, max_length=80),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    rows=_query(
        "SELECT review_id,proposition_id,venue,market_id,question, "
        "event_channel,factor_id,proposed_path_count,first_eligible_capture_at, "
        "earliest_mapping_available_at,retrospective_hindsight_paths, "
        "independently_verified_evidence_count,review_state,reviewer, "
        "reviewed_at,analyst_decision,analyst_rationale,evidence_url, "
        "review_batch,sampling_method,released_for_signal_use "
        "FROM eventrisk_factor_lab.main.lab_forward_mapping_review_queue_v1 "
        "WHERE review_state=? AND (? IS NULL OR venue=?) "
        "AND (? IS NULL OR factor_id=?) "
        "AND (? IS NULL OR event_channel=?) "
        "ORDER BY venue,event_channel,factor_id,review_id LIMIT ? OFFSET ?",
        (review_state,venue,venue,factor_id,factor_id,
         event_channel,event_channel,limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "review_only": True,"hypotheses_not_evidence":True,
            "analyst_approval_required":True,"signals_released":False}


@app.get("/v1/research/security-betas/coverage", dependencies=[Depends(require_api_key)])
def retrospective_security_beta_coverage() -> dict[str, Any]:
    """These rate sensitivities are historically computed, NOT PIT/approved betas."""
    models=_query(
        "SELECT COUNT(*) AS fitted_research_models, "
        "COUNT(DISTINCT ticker) AS usd_instruments, "
        "COUNT(DISTINCT factor_id) AS treasury_rate_factors, "
        "MIN(n_observations) AS min_matched_days, "
        "MAX(n_observations) AS max_matched_days, "
        "COUNT(*) FILTER (WHERE rate_bh_fdr_q < 0.05) AS fdr_candidates, "
        "COUNT(*) FILTER (WHERE test_r2_vs_spy_only > 0) AS positive_holdout, "
        "COUNT(*) FILTER (WHERE rate_bh_fdr_q < 0.05 "
        "AND test_r2_vs_spy_only > 0) AS double_screen_research_candidates, "
        "COUNT(*) FILTER (WHERE point_in_time_verified "
        "OR independent_data_rights_verified OR released_for_risk_use) "
        "AS incorrectly_released_rows "
        "FROM eventrisk_factor_lab.main.lab_security_rate_betas_retro_v1"
    )
    sources=_query(
        "SELECT COUNT(*) AS usd_adjusted_return_days, "
        "COUNT(DISTINCT ticker) AS usd_adjusted_return_instruments, "
        "COUNT(*) FILTER(WHERE large_absolute_log_return) "
        "AS suspicious_large_return_days "
        "FROM eventrisk_factor_lab.main.lab_security_returns_retro_v1"
    )
    return {"models":models[0] if models else {},
            "inputs":sources[0] if sources else {},
            "estimation_type":"retrospective_market_controlled_rate_sensitivity",
            "factor_shock_unit":"yield_basis_points",
            "security_return_unit":"log_return_basis_points",
            "model_benchmark":"SPY_adjusted_close",
            "research_only":True,
            "independent_historical_vintage_verified":False,
            "authorized_security_beta_release":False}


@app.get("/v1/research/security-betas/retrospective", dependencies=[Depends(require_api_key)])
def retrospective_security_betas(
    research_use: bool = False,
    ticker: str | None = Query(None, min_length=1, max_length=24),
    factor_id: str | None = Query(None, min_length=2, max_length=100),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    if not research_use or os.environ.get("LAB_ENABLE_RETROSPECTIVE_READ") != "true":
        raise HTTPException(403, detail="Retrospective security factor estimates are disabled")
    rows=_query(
        "SELECT ticker,market_benchmark,factor_id,response_unit,predictor_unit, "
        "beta_unit,n_observations,n_train,n_test,first_date,last_date, "
        "beta_rate,beta_spy,intercept,train_r_squared,hac_lags, "
        "hac_rate_se,rate_z_approx,rate_p_normal,rate_bh_fdr_q, "
        "rate_ci95_lower,rate_ci95_upper,test_r2_vs_spy_only, "
        "test_rmse_bps,baseline_spy_only_rmse_bps, "
        "large_return_observations,point_in_time_verified, "
        "independent_data_rights_verified,released_for_risk_use,model_status,build_id "
        "FROM eventrisk_factor_lab.main.lab_security_rate_betas_retro_v1 "
        "WHERE (? IS NULL OR ticker=?) AND (? IS NULL OR factor_id=?) "
        "ORDER BY ticker,factor_id LIMIT ? OFFSET ?",
        (ticker,ticker,factor_id,factor_id,limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "status":"RETROSPECTIVE_RESEARCH_UNAPPROVED",
            "independent_point_in_time_verified":False,
            "released_for_risk_use":False,
            "warning":"EX_POST_ADJUSTED_PRICES_AND_FACTOR_VALUES_NOT_PRODUCTION_BETAS"}


@app.get("/v1/research/data-contracts/summary", dependencies=[Depends(require_api_key)])
def institutional_data_contract_summary() -> dict[str, Any]:
    """Field presence is not independent source, rights or MRM certification."""
    build=_query(
        "SELECT build_id,built_at,contracts_defined,field_rules_defined, "
        "required_fields_missing,required_fields_unpopulated, "
        "uncertified_required_fields,institutional_release_approved,release_state "
        "FROM eventrisk_factor_lab.main.lab_institutional_data_contract_builds_v1 "
        "ORDER BY built_at DESC LIMIT 1"
    )
    if not build:
        raise HTTPException(503, detail="Institutional data contracts not yet materialized")
    dataset_rows=_query(
        "SELECT dataset_id,source_table,grain,table_exists,source_row_count, "
        "total_fields_required,required_fields_missing, "
        "required_fields_unpopulated,populated_required_fields, "
        "source_certification_complete,data_class,status "
        "FROM eventrisk_factor_lab.main.lab_institutional_dataset_audit_v1 "
        "WHERE build_id=? ORDER BY dataset_id", (build[0]["build_id"],)
    )
    return {"audit":build[0],"datasets":dataset_rows,
            "source_certification_complete":False,
            "production_beta_authorized":False,
            "warning":"FIELD_PRESENCE_IS_NOT_DATA_RIGHTS_OR_POINT_IN_TIME_CERTIFICATION"}


@app.get("/v1/research/data-contracts/fields", dependencies=[Depends(require_api_key)])
def institutional_data_contract_fields(
    dataset_id: str | None = Query(None, min_length=2, max_length=100),
    status: str | None = Query(None, pattern="^(MISSING_DATASET|MISSING_FIELD|TYPE_MISMATCH|EMPTY|PARTIALLY_POPULATED|POPULATED_NOT_CERTIFIED)$"),
    limit: int = Query(100, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    rows=_query(
        "SELECT dataset_id,source_table,field_name,requirement_level, "
        "source_table_exists,actual_source_type,expected_type_class, "
        "type_class_pass,source_table_rows,nonnull_field_rows,nonnull_rate, "
        "inventory_status,independently_certified_for_production "
        "FROM eventrisk_factor_lab.main.lab_institutional_field_audit_v1 "
        "WHERE build_id=(SELECT build_id FROM "
        "eventrisk_factor_lab.main.lab_institutional_data_contract_builds_v1 "
        "ORDER BY built_at DESC LIMIT 1) "
        "AND (? IS NULL OR dataset_id=?) AND (? IS NULL OR inventory_status=?) "
        "ORDER BY dataset_id,requirement_level,field_name LIMIT ? OFFSET ?",
        (dataset_id,dataset_id,status,status,limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "certified_for_production":False, "research_only":True}


@app.get("/v1/research/factors/collinearity", dependencies=[Depends(require_api_key)])
def retrospective_rate_factor_collinearity(
    strong_only: bool = True,
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    rows=_query(
        "SELECT factor_a,factor_b,factor_a_family,factor_b_family, "
        "matched_dates,observed_date_min,observed_date_max, "
        "pearson_daily_shock_corr,abs_corr_gt_095, "
        "derived_identity_component_risk,inference_status "
        "FROM eventrisk_factor_lab.main.lab_factor_collinearity_pairs_v1 "
        "WHERE build_id=(SELECT build_id FROM "
        "eventrisk_factor_lab.main.lab_factor_diagnostics_builds_v1 "
        "ORDER BY built_at DESC LIMIT 1) "
        "AND (?=FALSE OR abs_corr_gt_095=TRUE) "
        "ORDER BY ABS(pearson_daily_shock_corr) DESC LIMIT ? OFFSET ?",
        (strong_only,limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "source_vintage_verified":False,
            "independent_factor_model_approved":False,
            "notice":"HIGH_CORRELATION_REQUIRES_KEY_RATE_OR_PCA_TRAINING_WINDOW_POLICY"}

@app.get("/v1/research/production/workstream-gates", dependencies=[Depends(require_api_key)])
def production_workstream_gates() -> dict[str, Any]:
    rows = _query(
        "SELECT workstream,n_gates,n_passed,n_blocked,percent_gates_passed,"
        "p0_blockers,external_approval_remaining,gate_build_id "
        "FROM eventrisk_factor_lab.main.lab_release_workstream_metrics_v1 "
        "WHERE build_id=(SELECT build_id FROM "
        "eventrisk_factor_lab.main.lab_release_workstream_metrics_v1 "
        "ORDER BY build_id DESC LIMIT 1) ORDER BY workstream"
    )
    return {"items":rows,"measurement":"share_of_applicable_gates_passed",
            "is_project_completion_percent":False,
            "institutional_release_approved":False}


@app.get("/v1/research/production/action-register", dependencies=[Depends(require_api_key)])
def production_action_register(
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    rows = _query(
        "SELECT gate_id,workstream,priority,accountable_role,gate_state,"
        "required_action,acceptance_evidence,requires_external_decision "
        "FROM eventrisk_factor_lab.main.lab_release_unblock_register_v1 "
        "WHERE build_id=(SELECT build_id FROM "
        "eventrisk_factor_lab.main.lab_release_unblock_register_v1 "
        "ORDER BY build_id DESC LIMIT 1) "
        "ORDER BY gate_state,priority,gate_id LIMIT ? OFFSET ?",
        (limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "institutional_release_approved":False}

@app.get("/v1/research/data-quality/security-prices/summary", dependencies=[Depends(require_api_key)])
def security_price_quality_summary() -> dict[str, Any]:
    rows = _query(
        "SELECT build_id,built_at,source_exception_rows,"
        "duplicated_security_date_keys,beta_sensitivity_models,"
        "models_with_beta_shift_ge_20pct,source_reconciled_exceptions,"
        "research_use_only "
        "FROM eventrisk_factor_lab.main.lab_security_price_exception_builds_v1 "
        "ORDER BY built_at DESC LIMIT 1"
    )
    if not rows:
        raise HTTPException(503, detail="Security price QA not materialized")
    return {"quality":rows[0],"source_quality_independently_approved":False,
            "corporate_action_vintage_verified":False,
            "production_betas_approved":False,
            "notice":"LARGE_RETURNS_MAY_BE_REAL_NOT_AUTOMATIC_VENDOR_ERRORS"}


@app.get("/v1/research/data-quality/security-prices/exceptions", dependencies=[Depends(require_api_key)])
def security_price_exception_cases(
    ticker: str | None = Query(None, min_length=1, max_length=24),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    rows = _query(
        "SELECT ticker,observed_date,previous_observed_date,"
        "previous_adjusted_close,adjusted_close,log_return_bps,"
        "source_unadjusted_close,source_adjusted_close,source_volume,"
        "source_currency,source_vendor,source_retrieved_at,source_run_id,"
        "other_symbols_same_move_day,exception_category,review_state,"
        "original_price_quote_time_verified,adjustment_vintage_verified,"
        "external_data_rights_approved,eligible_for_production_release "
        "FROM eventrisk_factor_lab.main.lab_security_price_exception_cases_v1 "
        "WHERE build_id=(SELECT build_id FROM "
        "eventrisk_factor_lab.main.lab_security_price_exception_builds_v1 "
        "ORDER BY built_at DESC LIMIT 1) "
        "AND (? IS NULL OR ticker=?) "
        "ORDER BY observed_date DESC,ticker LIMIT ? OFFSET ?",
        (ticker,ticker,limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "unverified_evidence_not_false_data":True,"research_only":True}


@app.get("/v1/research/data-quality/security-prices/beta-sensitivity", dependencies=[Depends(require_api_key)])
def security_price_beta_sensitivity(
    ticker: str | None = Query(None, min_length=1, max_length=24),
    factor_id: str | None = Query(None, min_length=2, max_length=100),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    rows = _query(
        "SELECT ticker,factor_id,original_beta_rate,"
        "baseline_recomputed_beta_rate,without_flagged_days_beta_rate,"
        "absolute_delta_beta,relative_delta_beta,original_train_n,"
        "research_exclusion_train_n,flagged_joint_observations,"
        "original_q_value,original_holdout_r2,sensitivity_state,"
        "source_pit_verified,production_beta_release "
        "FROM eventrisk_factor_lab.main.lab_beta_price_exception_sensitivity_v1 "
        "WHERE build_id=(SELECT build_id FROM "
        "eventrisk_factor_lab.main.lab_security_price_exception_builds_v1 "
        "ORDER BY built_at DESC LIMIT 1) "
        "AND (? IS NULL OR ticker=?) AND (? IS NULL OR factor_id=?) "
        "ORDER BY relative_delta_beta DESC,ticker,factor_id LIMIT ? OFFSET ?",
        (ticker,ticker,factor_id,factor_id,limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "sensitivity_only":True,
            "without_flagged_days_is_not_primary_model":True,
            "production_beta_release":False}


@app.get("/v1/research/curve-factor/coverage", dependencies=[Depends(require_api_key)])
def research_curve_factor_coverage() -> dict[str, Any]:
    rows=_query(
        "SELECT build_id,created_at,curve_factor_days,security_models,"
        "model_coefficients,q_below_05,holdout_improved_vs_spy,"
        "flagged_outlier_exposed_models,max_standardized_condition,"
        "independently_verified_models,release_state "
        "FROM eventrisk_factor_lab.main.lab_security_curve_builds_retro_v1 "
        "ORDER BY created_at DESC LIMIT 1"
    )
    if not rows:
        raise HTTPException(503,detail="Research curve factor model not materialized")
    return {"build":rows[0],
            "factor_components":["LEVEL","SLOPE","CURVATURE"],
            "rate_source":["DGS2","DGS5","DGS10"],
            "estimation_type":"ex_post_market_controlled_treasury_curve",
            "source_time_certified":False,"risk_model_approved":False,
            "deployable_security_beta":False,
            "notice":"RESEARCH_HAC_COEFFICIENTS_NOT_CAUSAL_EVENT_IMPACTS"}


@app.get("/v1/research/curve-factor/coefficients", dependencies=[Depends(require_api_key)])
def research_curve_coefficients(
    research_use: bool = False,
    ticker: str | None = Query(None,min_length=1,max_length=24),
    component: str | None = Query(None,pattern="^(LEVEL|SLOPE|CURVATURE)$"),
    limit: int = Query(50,ge=1,le=MAX_PAGE),
    offset: int = Query(0,ge=0,le=100000),
) -> dict[str,Any]:
    if not research_use or os.environ.get("LAB_ENABLE_RETROSPECTIVE_READ") != "true":
        raise HTTPException(403,detail="Retrospective curve research disabled")
    rows=_query(
        "SELECT ticker,curve_component,coefficient_bps_per_bp,"
        "hac_se,normal_approx_z,p_normal,bh_family_q,"
        "ci95_lower,ci95_upper,response_unit,predictor_unit,"
        "independently_validated,released_as_institutional_beta,build_id "
        "FROM eventrisk_factor_lab.main.lab_security_curve_coefficients_retro_v1 "
        "WHERE build_id=(SELECT build_id FROM "
        "eventrisk_factor_lab.main.lab_security_curve_builds_retro_v1 "
        "ORDER BY created_at DESC LIMIT 1) "
        "AND (? IS NULL OR ticker=?) "
        "AND (? IS NULL OR curve_component=?) "
        "ORDER BY ticker,curve_component LIMIT ? OFFSET ?",
        (ticker,ticker,component,component,limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "ex_post_research_only":True,
            "no_tradable_forward_prediction":True,
            "production_risk_beta_approved":False}


@app.get("/v1/research/curve-factor/model-quality", dependencies=[Depends(require_api_key)])
def research_curve_model_quality(
    ticker: str | None = Query(None,min_length=1,max_length=24),
    limit: int = Query(50,ge=1,le=MAX_PAGE),
    offset: int = Query(0,ge=0,le=100000),
) -> dict[str,Any]:
    rows=_query(
        "SELECT ticker,benchmark,first_date,last_date,train_through,test_from,"
        "n_observations,n_train,n_test,standardized_train_condition,"
        "beta_spy,train_r_squared,test_r2_vs_spy_only,test_rmse_bps,"
        "spy_baseline_rmse_bps,flagged_large_return_days,"
        "source_security_adjustments_pit_verified,source_factors_pit_verified,"
        "source_rights_verified,authorized_institutional_release,model_status "
        "FROM eventrisk_factor_lab.main.lab_security_curve_model_retro_v1 "
        "WHERE build_id=(SELECT build_id FROM "
        "eventrisk_factor_lab.main.lab_security_curve_builds_retro_v1 "
        "ORDER BY created_at DESC LIMIT 1) "
        "AND (? IS NULL OR ticker=?) "
        "ORDER BY ticker LIMIT ? OFFSET ?",
        (ticker,ticker,limit,offset)
    )
    return {"items":rows,"limit":limit,"offset":offset,
            "research_only":True,"risk_model_approved":False}


@app.get("/v1/research/style-factors/coverage", dependencies=[Depends(require_api_key)])
def style_factor_research_coverage() -> dict[str,Any]:
    """Summary counts ONLY. No factor returns may be served without rights signoff."""
    builds=_query(
        "SELECT build_id,built_at,provider_archives_checked,archives_new,"
        "rows_downloaded,rows_appended,distinct_style_series,"
        "oldest_factor_date,newest_factor_date,"
        "source_publication_vintages_verified,"
        "production_risk_factors_approved,release_state "
        "FROM eventrisk_factor_lab.main.lab_style_factor_ingest_builds_v1 "
        "ORDER BY built_at DESC LIMIT 1"
    )
    if not builds:
        raise HTTPException(503, detail="Style factor research sources not loaded")
    series=_query(
        "SELECT factor_id,COUNT(*) AS research_rows,"
        "MIN(observed_date) AS first_date,MAX(observed_date) AS last_date,"
        "COUNT(*) FILTER (WHERE licensed_for_distribution OR "
        "approved_for_institutional_risk_use OR historical_point_in_time_verified) "
        "AS prohibited_release_claims "
        "FROM eventrisk_factor_lab.main.lab_style_factor_returns_v1 "
        "GROUP BY factor_id ORDER BY factor_id"
    )
    return {"build":builds[0],"series":series,
            "research_only":True,"downloaded_original_files_sha256_recorded":True,
            "historical_publication_vintage_independently_verified":False,
            "source_redistribution_rights_verified":False,
            "raw_factor_return_api_enabled":False,
            "approved_for_institutional_risk_use":False}

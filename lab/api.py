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

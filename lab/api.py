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
        conn = duckdb.connect("md:")
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
        "WHERE active = TRUE AND license_class NOT LIKE 'restricted%' "
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

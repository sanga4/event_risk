#!/usr/bin/env python3
"""Independent effective-information gate for the prospective event-factor grid.

The grid may contain 18 factor observations per capture-market pair, but
those are NOT 18 independent event-factor responses. Repeated collection of
the same market and same rate vintage is NOT a time-series innovation.

SELECT-only. A blocked estimability gate does not block subsequent lawful
source collection, only attempts to describe data as fitted prospective
event-to-factor betas or an approved backtest.
"""
from __future__ import annotations

import json
import sys
import duckdb

P = "eventrisk_factor_lab.main."
MIN_PROSPECTIVE_CAPTURE_DAYS = 60
MIN_FACTOR_OBSERVED_DAYS = 30
MIN_CAPTURE_RUNS = 60
MIN_DISTINCT_FACTOR_VALUES = 2

def evaluate(grid, source, factors):
    """Pure deterministic metrics; rejects approval claims and sample inflation.

    grid: rows, runs, capture_days, capture_markets, capture_propositions,
          capture_market_keys, factor_ids, observed_factor_days,
          factor_source_versions, market_revisions, previously_captured,
          false_approval_rows, earliest, latest.
    source: warehouse vintage rows, factor IDs, observed days.
    factors: id, persisted rows, unique runs, observed days, distinct source
             SHA, distinct factor levels, source archived days.
    """
    if len(grid) != 14 or len(source) != 3:
        raise ValueError("Unsupported prospective empirical information ledger")
    (rows, runs, days, markets, propositions, keys, n_factors, factor_days,
     vintages, changes, paired, false_claims, first, last) = grid
    (source_rows, source_factors, source_days) = source
    numerical=(rows,runs,days,markets,propositions,keys,n_factors,factor_days,
               vintages,changes,paired,false_claims,source_rows,
               source_factors,source_days)
    if any(type(x) is not int or x < 0 for x in numerical):
        raise ValueError("Invalid effective-information source counters")
    if (rows == 0 or runs == 0 or keys == 0 or n_factors == 0
        or first is None or last is None or first > last):
        raise ValueError("Empty or inconsistent captured prospective source")
    if (rows != keys*n_factors or changes>paired or paired>keys
        or markets>keys or propositions>markets or
        factor_days>source_days or vintages>source_rows
        or n_factors!=source_factors or len(factors)!=n_factors
        or false_claims != 0):
        raise ValueError("Incomplete factor rectangle, false release, or inconsistent inventory")
    all_factor_rows=0
    audit=[]
    seen=set()
    for row in factors:
        if len(row)!=7:
            raise ValueError("Changed factor information contract")
        (factor,n_rows,n_runs,n_days,n_versions,n_levels,n_archive_days)=row
        if (not isinstance(factor,str) or not factor
            or factor in seen or
            any(type(x) is not int or x<=0 for x in
                (n_rows,n_runs,n_days,n_versions,n_levels,n_archive_days))
            or n_runs>runs or n_days>factor_days
            or n_versions>vintages or n_archive_days>source_days
            or n_rows!=keys):
            raise ValueError("Missing or inconsistent factor-date support")
        seen.add(factor)
        all_factor_rows+=n_rows
        audit.append({
            "factor_id":factor,
            "prospective_rows":n_rows,
            "distinct_capture_runs":n_runs,
            "prospective_observation_dates":n_days,
            "prospective_source_versions":n_versions,
            "distinct_factor_values":n_levels,
            "archived_observation_dates":n_archive_days,
            "factor_held_constant_across_all_captures":n_levels==1,
            "eligible_for_prospective_time_series_screen": (
                n_days>=MIN_FACTOR_OBSERVED_DAYS and
                n_levels>=MIN_DISTINCT_FACTOR_VALUES
            ),
        })
    if all_factor_rows!=rows:
        raise ValueError("Mismatched research row and per-factor populations")

    eligible=sum(f["eligible_for_prospective_time_series_screen"] for f in audit)
    original_clock_claims={"source_first_published_pit_approved":False,
        "identified_event_innovations_approved":False,
        "causal_event_to_factor_beta_approved":False,
        "institutional_risk_factor_model_approved":False}
    overall_ok=(days>=MIN_PROSPECTIVE_CAPTURE_DAYS
                 and runs>=MIN_CAPTURE_RUNS
                 and eligible==n_factors)
    return {
        "status": ("PROSPECTIVE_VARIATION_SCREEN_ELIGIBLE_RESEARCH_ONLY"
                   if overall_ok else
                   "BLOCKED_PROSPECTIVE_FACTOR_STATISTICAL_ESTIMATION"),
        "research_data_integrity_scope":"REPEATED_ASOF_CAPTURE_CROSS_SECTION_NOT_IID_EVENT_SHOCKS",
        "stored_event_factor_rows":rows,
        "distinct_capture_runs":runs,
        "capture_calendar_days":days,
        "source_market_contracts":markets,
        "source_proposition_ids":propositions,
        "unique_capture_market_keys":keys,
        "distinct_research_factors":n_factors,
        "prospective_factor_observed_dates":factor_days,
        "prospective_source_factor_vintages":vintages,
        "factor_warehouse_archived_vintage_rows":source_rows,
        "factor_warehouse_archived_observation_dates":source_days,
        "source_market_capture_keys_with_prior":paired,
        "market_capture_keys_with_nonzero_probability_revision":changes,
        "max_independent_factor_source_days":factor_days,
        "factor_source_records_per_capture_market_row":
            float(rows)/keys,
        "repeat_ratio_to_unique_factor_vintages":
            float(rows)/vintages,
        "research_factors_with_estimable_time_series_variation":eligible,
        "research_factor_thresholds":{
            "minimum_capture_calendar_days":MIN_PROSPECTIVE_CAPTURE_DAYS,
            "minimum_capture_runs":MIN_CAPTURE_RUNS,
            "minimum_factor_observed_days_each":MIN_FACTOR_OBSERVED_DAYS,
            "minimum_distinct_factor_values_each":MIN_DISTINCT_FACTOR_VALUES,
        },
        "first_capture_at":str(first),
        "latest_capture_at":str(last),
        "per_factor":sorted(audit,key=lambda f:f["factor_id"]),
        "backfill_implication":(
            "Archive older factor levels exist, but cannot be retroactively "
            "promoted into point-in-time event captures. Obtain new genuinely "
            "as-received venue records across many original factor publication "
            "dates and independently verify publisher first-available clocks."
        ),
        **original_clock_claims,
    }


def inspect(con,prefix=P):
    # Capture-to-factor rectangularity and source release claims are audited
    # explicitly; no source history is mutated to make this test pass.
    g=con.execute(f"""
      SELECT COUNT(*),
             COUNT(DISTINCT event_run_id),
             COUNT(DISTINCT CAST(event_capture_at AS DATE)),
             COUNT(DISTINCT venue || ':' || market_id),
             COUNT(DISTINCT proposition_id),
             COUNT(DISTINCT event_run_id || ':' || venue || ':' || market_id),
             COUNT(DISTINCT factor_id),
             COUNT(DISTINCT factor_observed_date),
             COUNT(DISTINCT factor_source_sha256),
             COUNT(DISTINCT event_run_id || ':' || venue || ':' || market_id)
                 FILTER (WHERE event_delta_pp IS NOT NULL
                         AND event_delta_pp <> 0),
             COUNT(DISTINCT event_run_id || ':' || venue || ':' || market_id)
                 FILTER (WHERE previous_event_capture_at IS NOT NULL),
             COUNT(*) FILTER (WHERE
                  exchange_quote_time_independently_verified IS DISTINCT FROM FALSE
               OR factor_publication_time_independently_verified IS DISTINCT FROM FALSE
               OR event_to_factor_mapping_approved IS DISTINCT FROM FALSE
               OR historical_backtest_released IS DISTINCT FROM FALSE
               OR data_use_class IS DISTINCT FROM 'internal_research_only'
               OR relation_status IS DISTINCT FROM 'unreviewed_factor_coobservation_grid'),
             MIN(event_capture_at),MAX(event_capture_at)
      FROM {prefix}lab_prospective_event_factor_grid_v1
    """).fetchone()
    s=con.execute(f"""
      SELECT COUNT(*),COUNT(DISTINCT factor_id),
             COUNT(DISTINCT factor_observed_date)
      FROM {prefix}lab_factor_warehouse_vintages_v1
    """).fetchone()
    f=con.execute(f"""
      WITH archive AS (
        SELECT factor_id,COUNT(DISTINCT factor_observed_date) source_days
        FROM {prefix}lab_factor_warehouse_vintages_v1 GROUP BY 1
      ),
      prospective AS (
        SELECT factor_id,COUNT(*) AS n_rows,
           COUNT(DISTINCT event_run_id) capture_runs,
           COUNT(DISTINCT factor_observed_date) observed_days,
           COUNT(DISTINCT factor_source_sha256) vintages,
           COUNT(DISTINCT factor_value) distinct_values
        FROM {prefix}lab_prospective_event_factor_grid_v1
        GROUP BY 1
      )
      SELECT p.factor_id,p.n_rows,p.capture_runs,p.observed_days,
             p.vintages,p.distinct_values,a.source_days
      FROM prospective p LEFT JOIN archive a USING (factor_id)
      ORDER BY p.factor_id
    """).fetchall()
    return evaluate(g,s,f)


def main():
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        report=inspect(con)
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if report["status"].startswith("PROSPECTIVE_VARIATION_SCREEN_ELIGIBLE") else 2


if __name__=="__main__":
    sys.exit(main())

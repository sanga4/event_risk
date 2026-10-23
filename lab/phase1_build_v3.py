#!/usr/bin/env python3
"""EventRisk Phase I v3 — source-controlled, idempotent MotherDuck ELT.

Inputs: read-only laboratory event features, observed factor versions and license catalog.
Output: separately versioned daily panel; never edits source or legacy panels.
Retrospective rows are NOT safe for backtesting; only genuine as-known versions
can qualify, and public serving is a different release gate.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone

import duckdb

DB = "eventrisk_factor_lab"
VERSION = "phase1-v3.0.0"
PREFIX = f"{DB}.main."


def execute(con, sql):
    con.execute(sql)


def main():
    if os.environ.get("LAB_RESEARCH_SCOPE", "") != "internal-only":
        raise SystemExit("LAB_RESEARCH_SCOPE must be internal-only")
    source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    source_commit = os.environ.get("LAB_PIPELINE_COMMIT", "")
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise SystemExit("LAB_PIPELINE_COMMIT must be an immutable full Git SHA")
    con = duckdb.connect(f"md:{DB}?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    build_id = f"{VERSION}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    try:
        # Forward-only schema creation. Legacy lab_event_factor_panel[_v2] stays untouched.
        execute(con, f"""
        CREATE TABLE IF NOT EXISTS {PREFIX}lab_phase1_build_runs_v3 (
            build_id VARCHAR PRIMARY KEY,
            pipeline_version VARCHAR NOT NULL,
            source_commit VARCHAR NOT NULL,
            source_sha256 VARCHAR NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            finished_at TIMESTAMPTZ,
            first_event_date DATE,
            last_event_date DATE,
            retrospective_rows BIGINT,
            as_known_rows BIGINT,
            released_for_backtesting BOOLEAN NOT NULL,
            execution_status VARCHAR NOT NULL,
            notes VARCHAR
        )
        """)
        execute(con, f"""
        CREATE TABLE IF NOT EXISTS {PREFIX}lab_event_factor_panel_v3 (
            proposition_id VARCHAR NOT NULL,
            factor_id VARCHAR NOT NULL,
            observed_date DATE NOT NULL,
            event_cutoff_at TIMESTAMPTZ NOT NULL,
            event_known_at TIMESTAMPTZ NOT NULL,
            event_last_quote_at TIMESTAMPTZ NOT NULL,
            event_probability DOUBLE NOT NULL,
            event_delta_pp DOUBLE,
            factor_observed_date DATE NOT NULL,
            factor_value DOUBLE NOT NULL,
            factor_unit VARCHAR NOT NULL,
            previous_aligned_factor_value DOUBLE,
            factor_change_bps DOUBLE,
            factor_carried_forward BOOLEAN NOT NULL,
            factor_available_at TIMESTAMPTZ NOT NULL,
            factor_ingested_at TIMESTAMPTZ NOT NULL,
            factor_provider VARCHAR NOT NULL,
            factor_source_sha256 VARCHAR NOT NULL,
            event_source_run VARCHAR NOT NULL,
            factor_source_run VARCHAR NOT NULL,
            observed_mode VARCHAR NOT NULL,
            data_lookahead_warning BOOLEAN NOT NULL,
            relation_status VARCHAR NOT NULL,
            data_use_class VARCHAR NOT NULL,
            pipeline_version VARCHAR NOT NULL,
            build_id VARCHAR NOT NULL,
            built_at TIMESTAMPTZ NOT NULL
        )
        """)
        execute(con, f"""
        CREATE TABLE IF NOT EXISTS {PREFIX}lab_phase1_build_sources_v3 (
            build_id VARCHAR NOT NULL,
            input_name VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            digest_method VARCHAR NOT NULL,
            input_scope VARCHAR NOT NULL,
            captured_at TIMESTAMPTZ NOT NULL
        )
        """)
        execute(con, f"""
        CREATE TABLE IF NOT EXISTS {PREFIX}lab_phase1_mapping_decisions_v3 (
            decision_id VARCHAR NOT NULL,
            path_id VARCHAR NOT NULL,
            decision VARCHAR NOT NULL,
            reviewer VARCHAR NOT NULL,
            evidence_uri VARCHAR NOT NULL,
            rationale VARCHAR NOT NULL,
            reviewed_at TIMESTAMPTZ NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            source_commit VARCHAR NOT NULL
        )
        """)
        # Latest retrospective factor corrections may legitimately be known only
        # today; never pretend that their values were known at past cutoffs.
        execute(con, f"""
        CREATE OR REPLACE TEMP TABLE phase1_dates AS
        SELECT DISTINCT observed_date, cutoff_at
        FROM {PREFIX}lab_event_features
        WHERE known_at <= cutoff_at AND last_quote_at <= cutoff_at
          AND isfinite(probability) AND probability BETWEEN 0 AND 1
        """)
        execute(con, f"""
        CREATE OR REPLACE TEMP TABLE phase1_factors AS
        SELECT f.factor_id, f.observed_date, f.value, f.unit, f.availability_at,
               f.ingested_at, f.provider, f.record_sha256, f.run_id
        FROM {PREFIX}lab_factor_observations AS f
        JOIN {PREFIX}lab_factor_catalog AS c USING (factor_id)
        WHERE c.active = TRUE
          AND c.license_class NOT LIKE 'restricted%'
          AND f.unit = c.unit
          AND isfinite(f.value)
        """)
        execute(con, """
        CREATE OR REPLACE TEMP TABLE phase1_retro_curve AS
        WITH ranked AS (
            SELECT d.observed_date, d.cutoff_at, f.*,
                   row_number() OVER (
                       PARTITION BY d.observed_date, d.cutoff_at, f.factor_id
                       ORDER BY f.observed_date DESC,
                                f.ingested_at DESC, f.record_sha256 DESC
                   ) AS rk
            FROM phase1_dates AS d
            JOIN phase1_factors AS f ON f.observed_date <= d.observed_date
        )
        SELECT * EXCLUDE(rk)
        FROM ranked WHERE rk = 1
        """)
        execute(con, """
        CREATE OR REPLACE TEMP TABLE phase1_known_curve AS
        WITH ranked AS (
            SELECT d.observed_date, d.cutoff_at, f.*,
                   row_number() OVER (
                       PARTITION BY d.observed_date, d.cutoff_at, f.factor_id
                       ORDER BY f.observed_date DESC,
                                f.ingested_at DESC, f.record_sha256 DESC
                   ) AS rk
            FROM phase1_dates AS d
            JOIN phase1_factors AS f ON f.observed_date <= d.observed_date
              AND f.availability_at <= d.cutoff_at
              AND f.ingested_at <= d.cutoff_at
        )
        SELECT * EXCLUDE(rk)
        FROM ranked WHERE rk = 1
        """)
        execute(con, """
        CREATE OR REPLACE TEMP TABLE phase1_daily_curve AS
        WITH joined AS (
            SELECT 'retrospective'::VARCHAR AS observed_mode, * FROM phase1_retro_curve
            UNION ALL BY NAME
            SELECT 'as_known'::VARCHAR AS observed_mode, * FROM phase1_known_curve
        )
        SELECT *,
          lag(value) OVER (
              PARTITION BY observed_mode, factor_id ORDER BY observed_date, cutoff_at
          ) AS previous_aligned_factor_value
        FROM joined
        """)
        # Grouped calendar alignment avoids cross joining every event with
        # all 2024–2026 factor versions. The last observed vintage and release
        # availability are retained independently for each source.
        con.execute(f"""
        CREATE OR REPLACE TEMP TABLE phase1_new_panel AS
        SELECT
            e.proposition_id, c.factor_id, e.observed_date,
            e.cutoff_at AS event_cutoff_at, e.known_at AS event_known_at,
            e.last_quote_at AS event_last_quote_at, e.probability AS event_probability,
            e.delta_pp AS event_delta_pp,
            c.observed_date AS factor_observed_date,
            c.value AS factor_value, c.unit AS factor_unit,
            c.previous_aligned_factor_value,
            CASE WHEN c.previous_aligned_factor_value IS NULL THEN NULL
                 ELSE 100.0 * (c.value - c.previous_aligned_factor_value)
            END AS factor_change_bps,
            (c.observed_date < e.observed_date) AS factor_carried_forward,
            c.availability_at AS factor_available_at,
            c.ingested_at AS factor_ingested_at,
            c.provider AS factor_provider,
            c.record_sha256 AS factor_source_sha256,
            e.source_run AS event_source_run,
            c.run_id AS factor_source_run,
            c.observed_mode,
            (c.availability_at > e.cutoff_at OR c.ingested_at > e.cutoff_at
             OR e.known_at > e.cutoff_at OR e.last_quote_at > e.cutoff_at)
                AS data_lookahead_warning,
            'unreviewed_research_grid'::VARCHAR AS relation_status,
            'internal_research_only'::VARCHAR AS data_use_class,
            '{VERSION}'::VARCHAR AS pipeline_version,
            ?::VARCHAR AS build_id,
            current_timestamp AS built_at
        FROM {PREFIX}lab_event_features AS e
        JOIN phase1_daily_curve AS c
          ON e.observed_date = c.observed_date
         AND e.cutoff_at = c.cutoff_at
        WHERE e.known_at <= e.cutoff_at
          AND e.last_quote_at <= e.cutoff_at
          AND isfinite(e.probability)
          AND e.probability BETWEEN 0 AND 1
        """, [build_id])
        # Do not auto-release even as-known observations; model/review and
        # independent temporal accuracy are separate governance approvals.
        counts = con.execute("""
            SELECT min(observed_date), max(observed_date),
                   count(*) FILTER (WHERE observed_mode='retrospective'),
                   count(*) FILTER (WHERE observed_mode='as_known')
            FROM phase1_new_panel
        """).fetchone()
        if counts[0] is None:
            raise RuntimeError("No eligible event/factor records to materialize")
        con.execute("BEGIN TRANSACTION")
        try:
            # Atomic replacement of the owned versioned v3 dataset only.
            # Existing v1/v2 and raw provenance tables remain untouched.
            execute(con, f"DELETE FROM {PREFIX}lab_event_factor_panel_v3")
            execute(con, f"""
                INSERT INTO {PREFIX}lab_event_factor_panel_v3
                SELECT * FROM phase1_new_panel
            """)
            con.execute(f"""
                INSERT INTO {PREFIX}lab_phase1_build_runs_v3
                (build_id,pipeline_version,source_commit,source_sha256,started_at,
                finished_at,first_event_date,last_event_date,retrospective_rows,
                as_known_rows,released_for_backtesting,execution_status,notes)
                VALUES (?, ?, ?, ?, current_timestamp, current_timestamp,
                        ?, ?, ?, ?, FALSE, 'MATERIALIZED_UNRELEASED',
                        'Retrospective data and research grid are not a causal model')
            """, [build_id, VERSION, source_commit, source_sha256,
                    counts[0], counts[1], counts[2], counts[3]])
            con.execute(f"""
                DELETE FROM {PREFIX}lab_phase1_build_sources_v3
                WHERE build_id = ?
            """, [build_id])
            for table, scope in (
                ("lab_event_features", "event_cutoff_and_known_at"),
                ("lab_factor_observations", "availability_at_and_ingested_at"),
                ("lab_factor_catalog", "license_class_and_active"),
            ):
                con.execute(f"""
                INSERT INTO {PREFIX}lab_phase1_build_sources_v3
                SELECT ?, ?, count(*), 'row_count_only', ?, current_timestamp
                FROM {PREFIX}{table}
                """, [build_id, table, scope])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build_id}")
        print(f"EVENT_DATE_MIN={counts[0]} EVENT_DATE_MAX={counts[1]}")
        print(f"RETROSPECTIVE_ROWS={counts[2]} AS_KNOWN_ROWS={counts[3]}")
        print("RESEARCH_RELEASE=BLOCKED_PENDING_INDEPENDENT_GOVERNANCE")
    finally:
        con.close()


if __name__ == "__main__":
    main()

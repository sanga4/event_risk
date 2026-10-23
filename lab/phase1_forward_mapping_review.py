#!/usr/bin/env python3
"""Phase I: materialize prospective graph hypotheses and unbiased review queue.

This is a T R I A G E  pipeline. Existing graph edges were generated after
their historical snapshot dates. Mapping recorded_at <= a new capture's
receipt time is forward warehouse availability, not evidence of pre-snapshot
knowledge. All links remain proposed, unevidenced and NOT tradeable.
"""
from __future__ import annotations
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
import duckdb

DB="eventrisk_factor_lab"
P=f"{DB}.main."
VERSION="phase1-forward-mapping-v1.0.0"
LICENSE_ALLOWLIST=(
    "government_source_via_treasury",
    "government_source_via_fred",
    "derived_not_true_breakeven",
)

def ensure_schema(con):
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_forward_mapping_hypotheses_v1 (
      path_id VARCHAR NOT NULL,
      proposition_id VARCHAR NOT NULL,
      venue VARCHAR NOT NULL,
      market_id VARCHAR NOT NULL,
      question VARCHAR,
      question_id VARCHAR,
      entity_id VARCHAR,
      entity_role VARCHAR,
      event_action VARCHAR,
      event_channel VARCHAR NOT NULL,
      mechanism_id VARCHAR,
      macro_variable_id VARCHAR,
      factor_id VARCHAR NOT NULL,
      factor_license_class VARCHAR NOT NULL,
      source_graph_edge_id VARCHAR,
      ontology_relation_ids JSON,
      graph_asof TIMESTAMPTZ,
      mapping_available_at TIMESTAMPTZ NOT NULL,
      historical_snapshot_date DATE,
      historical_mapping_lookahead BOOLEAN NOT NULL,
      source_mapping_review_status VARCHAR NOT NULL,
      first_eligible_capture_at TIMESTAMPTZ NOT NULL,
      first_eligible_capture_run VARCHAR NOT NULL,
      event_probability DOUBLE NOT NULL,
      factor_observed_date DATE NOT NULL,
      factor_value DOUBLE NOT NULL,
      factor_ingested_at TIMESTAMPTZ NOT NULL,
      factor_available_at TIMESTAMPTZ NOT NULL,
      research_status VARCHAR NOT NULL,
      original_quote_time_verified BOOLEAN NOT NULL,
      provider_factor_publication_verified BOOLEAN NOT NULL,
      evidence_approved BOOLEAN NOT NULL,
      historically_backtest_released BOOLEAN NOT NULL,
      build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_forward_mapping_review_queue_v1 (
      review_id VARCHAR NOT NULL,
      proposition_id VARCHAR NOT NULL,
      venue VARCHAR NOT NULL,
      market_id VARCHAR NOT NULL,
      question VARCHAR,
      event_channel VARCHAR NOT NULL,
      factor_id VARCHAR NOT NULL,
      proposed_path_count BIGINT NOT NULL,
      first_eligible_capture_at TIMESTAMPTZ NOT NULL,
      earliest_mapping_available_at TIMESTAMPTZ NOT NULL,
      retrospective_hindsight_paths BIGINT NOT NULL,
      independently_verified_evidence_count BIGINT NOT NULL,
      review_state VARCHAR NOT NULL,
      reviewer VARCHAR,
      reviewed_at TIMESTAMPTZ,
      analyst_decision VARCHAR,
      analyst_rationale VARCHAR,
      evidence_url VARCHAR,
      review_batch VARCHAR NOT NULL,
      sampling_method VARCHAR NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      released_for_signal_use BOOLEAN NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_forward_mapping_build_runs_v1 (
      build_id VARCHAR NOT NULL,
      source_commit VARCHAR NOT NULL,
      source_sha256 VARCHAR NOT NULL,
      built_at TIMESTAMPTZ NOT NULL,
      eligible_hypotheses BIGINT NOT NULL,
      new_hypotheses BIGINT NOT NULL,
      new_review_items BIGINT NOT NULL,
      eligible_live_propositions BIGINT NOT NULL,
      historical_leakage_rows BIGINT NOT NULL,
      unintended_released_rows BIGINT NOT NULL,
      release_state VARCHAR NOT NULL
    )""")

def stage(con):
    classes=",".join("'"+c+"'" for c in LICENSE_ALLOWLIST)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_forward_hyp AS
    WITH matches AS (
      SELECT p.path_id,p.proposition_id,g.venue,g.market_id,
        e.question,p.question_id,p.entity_id,p.entity_role,
        p.event_action,p.event_channel,p.mechanism_id,
        p.macro_variable_id,p.factor_id,c.license_class AS factor_license_class,
        p.source_graph_edge_id,p.ontology_relation_ids,
        p.graph_asof,p.mapping_available_at,p.snapshot_date AS historical_snapshot_date,
        p.historical_mapping_lookahead,
        p.review_status AS source_mapping_review_status,
        g.event_capture_at AS first_eligible_capture_at,
        g.event_run_id AS first_eligible_capture_run,
        g.event_probability,g.factor_observed_date,g.factor_value,
        g.factor_ingested_at,g.factor_available_at,
        'proposed_forward_hypothesis_only'::VARCHAR AS research_status,
        FALSE AS original_quote_time_verified,
        FALSE AS provider_factor_publication_verified,
        FALSE AS evidence_approved,
        FALSE AS historically_backtest_released,
        row_number() OVER (
          PARTITION BY p.path_id
          ORDER BY g.event_capture_at ASC,g.event_run_id ASC
        ) AS rn
      FROM {P}lab_event_factor_candidate_paths AS p
      JOIN {P}lab_prospective_event_factor_grid_v1 AS g
        ON p.proposition_id=g.proposition_id AND p.factor_id=g.factor_id
      JOIN {P}lab_factor_catalog AS c ON c.factor_id=p.factor_id
      JOIN {P}lab_live_event_features_v1 AS e
        ON e.proposition_id=g.proposition_id AND e.run_id=g.event_run_id
      WHERE p.review_status='proposed'
        AND p.mapping_available_at <= g.event_capture_at
        AND p.graph_asof <= g.event_capture_at
        AND g.factor_ingested_at <= g.event_capture_at
        AND g.factor_available_at <= g.event_capture_at
        AND g.factor_license_class=c.license_class
        AND c.active AND c.license_class IN ({classes})
        AND g.relation_status='unreviewed_factor_coobservation_grid'
        AND NOT g.historical_backtest_released
    )
    SELECT * EXCLUDE(rn) FROM matches WHERE rn=1
    """)
    # The sampling grid is deterministic by venue, channel and factor to
    # avoid a few highly connected events crowding out review diversity.
    # No algorithm can auto-approve a mapping; humans must supply signed
    # evidence, reject hindsight and separately approve release.
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_review_rank AS
    WITH grouped AS (
      SELECT proposition_id,venue,market_id,
        any_value(question) AS question,event_channel,factor_id,
        count(*) AS proposed_path_count,
        min(first_eligible_capture_at) AS first_eligible_capture_at,
        min(mapping_available_at) AS earliest_mapping_available_at,
        count(*) FILTER (WHERE historical_mapping_lookahead)
          AS retrospective_hindsight_paths
      FROM p1_forward_hyp
      GROUP BY proposition_id,venue,market_id,event_channel,factor_id
    ), ranked AS (
      SELECT *,
        row_number() OVER (
           PARTITION BY venue,event_channel,factor_id
           ORDER BY md5(proposition_id||'|'||event_channel||'|'||factor_id),
                    proposition_id
        ) AS rank_in_stratum
      FROM grouped
    )
    SELECT *
    FROM ranked
    WHERE rank_in_stratum <= 4
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_missing_hyp AS
    SELECT h.* FROM p1_forward_hyp AS h
    WHERE NOT EXISTS (
      SELECT 1 FROM {P}lab_forward_mapping_hypotheses_v1 v
      WHERE v.path_id=h.path_id
    )
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_missing_queue AS
    SELECT r.* FROM p1_review_rank r
    WHERE NOT EXISTS (
      SELECT 1 FROM {P}lab_forward_mapping_review_queue_v1 v
      WHERE v.proposition_id=r.proposition_id
        AND v.event_channel=r.event_channel AND v.factor_id=r.factor_id
    )
    AND NOT EXISTS (
      SELECT 1 FROM {P}lab_mapping_review_cases old
      WHERE old.proposition_id=r.proposition_id
        AND old.event_channel=r.event_channel AND old.factor_id=r.factor_id
    )
    """)

def main():
    if os.environ.get("LAB_RESEARCH_SCOPE")!="internal-only":
        raise RuntimeError("LAB_RESEARCH_SCOPE must be internal-only")
    commit=os.environ.get("LAB_PIPELINE_COMMIT","")
    if len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("Immutable 40-char Git commit required")
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build_id=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        ensure_schema(con)
        stage(con)
        stats=con.execute("""
          SELECT
            (SELECT count(*) FROM p1_forward_hyp),
            (SELECT count(*) FROM p1_missing_hyp),
            (SELECT count(*) FROM p1_missing_queue),
            (SELECT count(distinct proposition_id) FROM p1_forward_hyp),
            (SELECT count(*) FROM p1_forward_hyp
             WHERE mapping_available_at > first_eligible_capture_at
                OR graph_asof > first_eligible_capture_at
                OR factor_available_at > first_eligible_capture_at
                OR factor_ingested_at > first_eligible_capture_at),
            (SELECT count(*) FROM p1_forward_hyp
             WHERE evidence_approved OR historically_backtest_released
                OR original_quote_time_verified OR provider_factor_publication_verified)
        """).fetchone()
        if stats[4] or stats[5]:
            raise RuntimeError("Release, provider-timing or hindsight leak detected")
        if not stats[0]:
            raise RuntimeError("No forward-market to graph as-of join candidates")
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""
              INSERT INTO {P}lab_forward_mapping_hypotheses_v1
              SELECT *,? FROM p1_missing_hyp
            """,[build_id])
            con.execute(f"""
              INSERT INTO {P}lab_forward_mapping_review_queue_v1
              SELECT
                'forward-review:'||md5(proposition_id||'|'||event_channel||'|'||factor_id),
                proposition_id,venue,market_id,question,event_channel,factor_id,
                proposed_path_count,first_eligible_capture_at,
                earliest_mapping_available_at,retrospective_hindsight_paths,
                0::BIGINT,'pending_human_review',NULL,NULL,NULL,NULL,NULL,
                'phase1-forward-stratified-v1',
                'stable_hash_4_per_venue_channel_factor',
                current_timestamp,FALSE
              FROM p1_missing_queue
            """)
            con.execute(f"""
              INSERT INTO {P}lab_forward_mapping_build_runs_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,
                       'UNRELEASED_PENDING_HUMAN_EVIDENCE')
            """,[build_id,commit,source_hash,*stats])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print("BUILD_ID="+build_id)
        print("FORWARD_HYPOTHESES="+str(stats[0]))
        print("NEW_HYPOTHESES="+str(stats[1]))
        print("NEW_REVIEW_ITEMS="+str(stats[2]))
        print("LIVE_OVERLAP_PROPOSITIONS="+str(stats[3]))
        print("TEMPORAL_LEAKS="+str(stats[4]))
        print("FALSE_RELEASE_OR_CERTIFICATION="+str(stats[5]))
        print("ALL_MAPPING_EVIDENCE_STATUS=PENDING_HUMAN_REVIEW")
    finally:
        con.close()

if __name__=="__main__":
    main()

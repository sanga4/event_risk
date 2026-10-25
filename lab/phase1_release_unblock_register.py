#!/usr/bin/env python3
"""Source-controlled release blocker register grounded in MotherDuck gate results.

Every gate is mapped to an acceptance artifact and accountable *role*, not a
fabricated person's approval. No release flags or historical data are changed.
This inventory preserves operational versus research/rights approval distinctions.
"""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
import duckdb

P="eventrisk_factor_lab.main."
VERSION="phase1-release-unblock-register-v1.5.0"

# id: (workstream, priority, accountable_role, action, evidence_to_clear)
REMEDIATIONS={
"rolling_security_six_factor_beta_stability_research":("Statistical model validation","P1","Quantitative equity risk methodology",
 "Fit joint FF5-plus-momentum excess-simple-return loadings on fixed 378-day rolling train, 63-day holdout steps; record uncertainty, outlier exposure and train-only conditioning.",
 "At least 900 source-linked ex-post security-beta windows and precommitted stability/holdout diagnostics"),
"rolling_security_six_factor_beta_stability_certification":("Statistical model validation","P0","Independent quantitative model-risk reviewer",
 "Resolve coefficient instability, poor forward holdout and structural breaks using source-reviewed prices, regime-aware calibration and independently repeated validation.",
 "Zero unresolved flagged rolling beta models under independently accepted stability criteria and signed model-risk evidence"),
"independent_security_mapping_evidence_worklist":("Event mapping and evidence","P1","Data steward + event methodology",
 "Version original price corporate-action, FX quote conflict and event economic mapping source requirements without inventing split events or original quotes.",
 "At least 400 fully enumerated evidence requirements across original security, FX and mapping case samples"),
"original_source_evidence_and_second_signoffs":("Event mapping and evidence","P0","Primary source analyst + independent second approver",
 "Secure original source payload+checksum, publication/revision timestamps, usage rights, original corporate action data, reviewer identity and a second attributed signoff.",
 "At least 10 complete immutable source evidence records that satisfy original-time, licensing and dual-review controls, without auto-approving an event link"),

"institutional_source_family_evidence_inventory":("Schema and cross-asset factors","P0","Institutional source data architect",
 "Run consistent source-family snapshot after source ingestion and release-gate rebuild. Track actual loaded row counts and gaps without synthetic rows.",
 "16 source-family observations with table-present, row count, native grain, first/last observation and actionable evidence gaps"),
"institutional_source_family_rights_and_pit_certification":("Point-in-time provenance","P0","Independent source licensor/data QA/model-risk committee",
 "Obtain and review original source publication/vintage evidence, vendor data rights and independent approval across each product-required domain.",
 "All applicable source families independently certified and signed off, with missing domains explicitly unavailable rather than approved"),

"nyfed_sofr_effr_reference_research_loaded":("Schema and cross-asset factors","P1","Rates data engineering",
 "Keep two official NY Fed source observations separately versioned with original response SHA and percentage units; verify replay and deduplication.",
 "500 or more exact response-hashed reference observations; labels must remain research-only, no source publication clock approval"),
"nyfed_funding_provider_vintages_rights_verified":("Point-in-time provenance","P0","NY Fed release-data QA + legal data owner",
 "Obtain original rate as-published times and historical revision records with permission to store/use and redistribute as intended.",
 "Both SOFR and EFFR independently publication/vintage verified with signed reuse and original source evidence"),
"rolling_crossasset_covariance_diagnostics_materialized":("Statistical model validation","P1","Institutional quant risk research",
 "Maintain fixed 252/63-day rolling, train-only covariance scaling/diagonal shrink and 21-day moving window checks.",
 "At least 15 source-linked windows, full holdout metrics and zero source/PIT release claims"),
"rolling_crossasset_covariance_regime_stability_screen":("Statistical model validation","P0","Independent quantitative model-risk owner",
 "Review all covariance instability windows, diagnose market regime effects, stress scenarios, temporal validity and document accepted calibration.",
 "Zero unresolved materially unstable rolling windows under prospectively approved threshold, signed independent model-risk review separately required"),

"official_ecb_eur_fx_research_loaded":("Schema and cross-asset factors","P1","Cross-asset source engineering",
 "Maintain source-hashed informational EUR currency-pair history with unambiguous quote orientation and dated reference values.",
 "Seven ECB reference currencies, >30000 price records, immutable source hashes and unit-aware log change; no false tradability approval"),
"cross_asset_factor_covariance_research_diagnostic":("Statistical model validation","P1","Quantitative risk methodology",
 "Preserve train-only unit normalization, covariance shrinkage, chronological holdout drift and factor definitions; reject erroneous portfolio-release claims.",
 "Complete seven-factor 49-cell research matrix with independent holdout diagnostics; not a cleared portfolio risk engine"),
"ecb_original_provider_vintage_and_source_rights_certification":("Point-in-time provenance","P0","ECB source QA + licensing owner",
 "Verify each original provider publication/version, permitted use and distinguish informational rates from tradeable executable FX data.",
 "Seven EUR pair reference sources with independent original release/vintage timestamps and rights; separate tradeable FX feed required for execution"),

"us_equity_style_source_archive_research_backfill":("Schema and cross-asset factors","P1","Quantitative data engineering",
 "Maintain reproducible internal research source snapshots with provider file checksums, missing-sentinel and percent/decimal validation.",
 "At least 100,000 source-versioned daily FF5/MOM records; never imply historical source release timestamps"),
"us_equity_style_vintages_and_rights_certified":("Rights and service credentials","P0","Vendor licensing + independent provider provenance owner",
 "Confirm French/CRSP data-use and distribution rights and recover independently verifiable historic factor archive/vintage and publication evidence.",
 "Seven source series rights- and true-PIT-verified with independent model-risk acceptance; no synthetic release dates"),

"genuine_pit_factor_panel":("Point-in-time provenance","P0","Data engineering + independent model validation",
 "Build historical as-known event/factor panels exclusively from replayable original source vintages and verified pre-cutoff mappings.",
 ">=10000 truly as-known, non-hindsight rows; independent per-source time replay and holdout validation"),
"historical_quote_pit_fraction":("Point-in-time provenance","P0","Market-data engineering + source QA",
 "Acquire original exchange quote timestamps and archived response bytes; verify historic market snapshot first-availability.",
 ">=80% of eligible legacy history independently verified, sampled to source evidence"),
"independent_mapping_reviews":("Event mapping and evidence","P0","Independent economic reviewers",
 "Perform attributed independent evaluations of mapping paths and reject or defer unsupported mechanisms.",
 ">=10 signed reviews with timestamp, source evidence, rationale and dispositions"),
"independent_oos_candidate_signals":("Statistical model validation","P1","Independent quantitative model-risk owner",
 "Pre-register event shock target and response horizons; perform purged chronological PIT trials and multiplicity-controlled holds.",
 ">=1 strictly PIT-eligible independent OOS candidate; full model card and approval still separate"),
"independent_rate_factor_vintage_certification":("Point-in-time provenance","P0","Official data sourcing and QA",
 "Archive original Treasury/FRED release and revised vintages with provider-attested availability; test calendar alignment.",
 "18 eligible factor series with verified true first publication, revisions, defined shock units and rights"),
"institutional_required_field_certification":("Schema and cross-asset factors","P0","Institutional data architect + source owners",
 "Populate or explicitly scope source-required contracts and independently validate every required field; no generated fake dates.",
 "16 contracted source domains certified under product release scope, all supporting evidence filed"),
"prospective_dual_venue_capture_recent":("Operational ingestion","P0","Data platform/SRE",
 "Restore schedule with least-privilege GitHub Actions MotherDuck secret after successful authorized manual run.",
 "Both venues with successful nonempty runs younger than 90 minutes across consecutive daily cycles"),
"provider_quote_freshness_evidence":("Point-in-time provenance","P0","Venue integration + source QA",
 "Collect provider-authenticated quote timestamps, source fields and independently verify their semantics.",
 ">=1 original provider quote timestamp independently verified; scale to documented sample before release"),
"real_time_venue_data_recent":("Operational ingestion","P0","Legacy ingestion operations",
 "Restore the separate historical/legacy market_snapshots realtime collector or formally deprecate it through approved release-governance migration.",
 "Legacy realtime observation no older than 12h; not substituted by prospective receipt view without agreed semantics"),
"reviewed_factor_evidence":("Event mapping and evidence","P0","Economic subject matter expert + independent peer",
 "Approve or reject a real relation with signed review record linked to evidence artifact.",
 ">=1 approved relation with nonnull evidence_id, source as-of and reviewer identity"),
"security_betas_independently_approved":("Statistical model validation","P1","Model risk and data-rights signoff",
 "Build PIT security total-return and rate/style factor model; independently validate beta stability, uncertainty and rights.",
 ">=1 beta row with independent as-of, data rights and risk release, not an exploratory coefficient"),
"security_prices_original_vintage_certified":("Point-in-time provenance","P0","Security master and corporate-actions team",
 "Verify original price source release timing, adjusted-close revisions, split/dividend/corporate actions and as-of security IDs.",
 ">=10000 true PIT-adjusted security-return rows with independently validated original revisions"),
"source_evidence":("Event mapping and evidence","P0","Research evidence curator",
 "Ingest actual cited evidence with publication timestamp, source hashes, license and immutable archive.",
 ">=1 real reviewable, license-permitted evidence record, not AI-generated corroboration"),
"unreviewed_large_price_moves":("Security source QA","P0","Market-data QA analyst",
 "Reconcile 12 >25% daily adjusted-price log returns to provider corrections, splits, corporate actions, or real market moves.",
 "Every exception attributable to source evidence or explicitly quarantined under approved QA policy"),
"independent_research_signoff":("Statistical model validation","P1","Independent model-risk committee",
 "Review independent backtest, identification, economic plausibility, code, and data lineage.",
 "Signed approval ID, model card, restrictions, review date, reviewer identity"),
"institutional_access_controls":("Serving and operating controls","P0","Security/SRE",
 "Verify service authentication, audit logs, least-privilege credentials, monitoring, alerts, rollback and backup recovery.",
 "Documented negative access tests, authenticated audit trail, incident runbook, rollback rehearsal"),
"licensed_market_data_review":("Rights and service credentials","P0","Legal/compliance and vendor owner",
 "Confirm each commercial use, storage, derived transformation and redistribution entitlement for Yahoo, Kalshi, Polymarket and credit sources.",
 "Signed per-provider permitted-use/license/expiry record; restricted feeds remain OFF"),
"railway_service_data_rights":("Rights and service credentials","P0","Environment owner and security",
 "Configure Railway LAB_DATA_RIGHTS_ACK and scoped MotherDuck and API-key secrets; exercise 401/403 and authenticated reads.",
 "Scoped token/API keys stored in secret manager (not chat/GitHub), rights attested and working authenticated read"),
"forward_mapping_candidate_temporal_leakage":("Event mapping and evidence","P0","Graph data engineering",
 "Preserve as-of graph mapping and avoid any later-than-capture joins or automatic relation approval.",
 "0 temporal leaks, 0 fabricated releases, monotonic append lineage"),
"historical_research_pipeline_built":("Research infrastructure","P1","Data platform engineering",
 "Maintain repeatable historical loader and traceable build manifests.",
 "Successful reproducible research build with source commit and recorded row counts"),
"institutional_field_contract_inventory":("Schema and cross-asset factors","P0","Data architecture",
 "Maintain versioned column-level requirements and completeness audit of all contracted data products.",
 ">=250 field rules audited and tracked with source, type, temporal and license semantics"),
"market_controlled_security_rate_research_backfill":("Security source QA","P1","Quantitative research",
 "Maintain rate-bps/asset-return-bps unit rules and SPY control; do not confuse same-day association with production beta.",
 ">=500 labeled retrospective model calculations with source and quality annotations"),
"prospective_capture_receipt_provenance":("Operational ingestion","P0","Market-data ingestion engineering",
 "Archive capture receipt time, response digests and versioned contract identity, and extend raw response replay.",
 ">=1000 distinct receipt-time/source-hash rows; quote-time certification remains separate"),
"prospective_mapping_review_queue_prepared":("Event mapping and evidence","P1","Economic research operations",
 "Keep diversified sampling queue and pending independent review assignments.",
 ">=50 traceable unapproved cases without autogenerated reviewer dispositions"),
"rate_factor_covariance_collinearity_report":("Schema and cross-asset factors","P0","Quantitative risk methodology",
 "Use key rates or training-fitted principal components to avoid 18 highly correlated Treasury drivers and derived algebraic proxies.",
 ">=150 diagnostic pairwise comparisons; subsequent rank/VIF/rolling risk model separately validated"),
"robust_diagnostics_pipeline_built":("Research infrastructure","P1","Research platform engineering",
 "Continue reproducible historical HAC, chronological test split and FDR baseline.",
 "Successful versioned statistics build, without causal approval"),
"warehouse_asof_prospective_grid_materialized":("Research infrastructure","P1","Data engineering",
 "Keep strictly receipt-asof factor grid and recording of ingest-first availability.",
 ">=1000 co-observations time-eligible within warehouse; NOT independent public release"),
"warehouse_asof_temporal_leakage":("Point-in-time provenance","P0","Data quality owner",
 "Reject factor warehouse ingest/availability timestamps after event receipt time.",
 "Zero future-warehouse factor joins; independent publication certification separate"),
}

def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("Require internal research and pinned full commit")
    scriptsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_release_unblock_register_v1(
          build_id VARCHAR NOT NULL,gate_build_id VARCHAR NOT NULL,
          gate_id VARCHAR NOT NULL,workstream VARCHAR NOT NULL,
          priority VARCHAR NOT NULL,accountable_role VARCHAR NOT NULL,
          gate_state VARCHAR NOT NULL,measured_value DOUBLE,
          pass_threshold DOUBLE,pass_rule VARCHAR NOT NULL,
          required_action VARCHAR NOT NULL,acceptance_evidence VARCHAR NOT NULL,
          source_explanation VARCHAR NOT NULL,
          requires_external_decision BOOLEAN NOT NULL,
          institutional_release_approved BOOLEAN NOT NULL,
          recorded_at TIMESTAMPTZ NOT NULL,
          source_commit VARCHAR NOT NULL,source_sha256 VARCHAR NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_release_workstream_metrics_v1(
          build_id VARCHAR NOT NULL,gate_build_id VARCHAR NOT NULL,
          workstream VARCHAR NOT NULL,n_gates BIGINT NOT NULL,
          n_passed BIGINT NOT NULL,n_blocked BIGINT NOT NULL,
          percent_gates_passed DOUBLE NOT NULL,
          p0_blockers BIGINT NOT NULL,
          external_approval_remaining BIGINT NOT NULL,
          institutional_release_approved BOOLEAN NOT NULL
        )""")
        latest=con.execute(f"""
           SELECT build_id FROM {P}lab_release_gate_summary_v1
           ORDER BY asof_utc DESC LIMIT 1
        """).fetchone()
        if not latest:raise RuntimeError("No release-gate measurements exist")
        gid=latest[0]
        gates=con.execute(f"""
           SELECT gate_id,gate_state,measured_value,threshold,rule,explanation
           FROM {P}lab_release_gate_history_v1 WHERE build_id=?
        """,[gid]).fetchall()
        names={r[0] for r in gates}
        if names!=set(REMEDIATIONS):
            raise RuntimeError(f"Unmapped source gates: {sorted(names-set(REMEDIATIONS))}; obsolete mapping: {sorted(set(REMEDIATIONS)-names)}")
        captured=[]
        for name,state,value,threshold,rule,description in sorted(gates):
            group,priority,role,action,evidence=REMEDIATIONS[name]
            captured.append((build,gid,name,group,priority,role,state,value,threshold,
                             rule,action,evidence,description,
                             state=="BLOCKED_MANUAL",False,
                             datetime.now(timezone.utc),commit,scriptsha))
        count_by_stream={}
        for row in captured:
            _,_,_,group,priority,_,status,*_=row
            v=count_by_stream.setdefault(group,[0,0,0,0,0])
            v[0]+=1
            v[1]+=int(status=="PASS")
            v[2]+=int(status!="PASS")
            v[3]+=int(status!="PASS" and priority=="P0")
            v[4]+=int(status=="BLOCKED_MANUAL")
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(f"INSERT INTO {P}lab_release_unblock_register_v1 VALUES ({','.join(['?']*18)})",captured)
            lines=[(build,gid,k,v[0],v[1],v[2],
                    round(100*v[1]/v[0],1),v[3],v[4],False)
                   for k,v in sorted(count_by_stream.items())]
            con.executemany(f"INSERT INTO {P}lab_release_workstream_metrics_v1 VALUES ({','.join(['?']*10)})",lines)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BLOCKER_REGISTER_BUILD={build}")
        print(f"METRICS_SOURCE_BUILD={gid}")
        print(f"GATES_TRACKED={len(captured)} WORKSTREAMS={len(count_by_stream)}")
        for name,m in sorted(count_by_stream.items()):
            print(f"{name}: PASS={m[1]}/{m[0]} P0_BLOCKED={m[3]} EXTERNAL_REMAINING={m[4]}")
        print("INSTITUTIONAL_RELEASE_APPROVED=FALSE")
    finally:
        con.close()

if __name__=="__main__":
    main()

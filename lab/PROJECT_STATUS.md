# EventRisk Factor — Institutional Phase I Status

**As-of:** October 24, 2026 (checked against MotherDuck/GitHub/Railway). This is an **as-of snapshot**, not a live telemetry dashboard. The authoritative current metrics are MotherDuck tables described below; rerun the release-gates Flight before using the numbers as a fresh assessment.

## Quick links

| What to inspect | Link |
|---|---|
| Factor Lab service process liveness | https://factor-lab-api-production.up.railway.app/health/live |
| Source code in sanga4 main | https://github.com/sanga4/event_risk |
| All GitHub pipeline/CI runs | https://github.com/sanga4/event_risk/actions |
| Latest institutional milestone pull request | https://github.com/sanga4/event_risk/pull/13 |
| Institutional Beta Methodology | https://github.com/sanga4/event_risk/blob/main/lab/INSTITUTIONAL_FACTOR_BETA_METHODOLOGY.md |
| Institutional Data Dictionary & Backfill | https://github.com/sanga4/event_risk/blob/main/lab/INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md |
| Required source/rights approvals | https://github.com/sanga4/event_risk/blob/main/lab/PHASE1_PRODUCTION_UNBLOCK_PLAN.md |
| Security source exceptions and beta robustness | https://github.com/sanga4/event_risk/blob/main/lab/SECURITY_SOURCE_QA_AND_BETA_SENSITIVITY.md |

## Latest methodology milestone — three-component Treasury curve model

Source-controlled risk-methodology code: [Treasury Curve Factor Model](INSTITUTIONAL_TREASURY_CURVE_MODEL.md) and `phase1_curve_factor_research.py`. MotherDuck Flight successfully fitted **48** joint SPY + Treasury nominal curve models (LEVEL/SLOPE/CURVATURE), and persisted **144** coefficient rows over **701** historical rate-change dates. **6** slopes have exploratory BH q under .05, **17** same-day holdout comparisons improve on SPY-only, **4** models contain previously flagged abnormal price movements; maximum standardized training design condition number **1.7616**. All model and source PIT/rights/production release flags remain **FALSE**. These are descriptive historical security-rate sensitivities, not independently approved betas or event-to-factor causal responses.

The formal institutional gate score is **still 11/24 (45.8%)** with four external/manual requirements; adding a model calculation is not acceptance evidence and has not changed the formal release gates.


## Current independent readiness checks

| Scope | Passing tests | What passing means |
|---|---:|---|
| Research pipeline/infrastructure | 3/3 = 100% | Research builds and diagnostics are reproducible |
| Operational market ingestion | 2/3 = 67% | On-demand fresh capture works; scheduled/legacy sources not complete |
| Data schema and quantitative factors | 2/3 = 67% | Data contracts and covariance reports exist; source certifications absent |
| Security source quality | 1/2 = 50% | Historical prices and models loaded; all 12 abnormal returns unreviewed |
| Event mappings and evidence | 2/5 = 40% | Forward hypothesis queue, zero approved mapped evidence |
| Genuine historical PIT provenance | 1/6 = 17% | Warehouse timing safe; original publication/quote times unverified |
| Vendor data rights and credentials | 0/2 = 0% | Production secrets and legal vendor rights not approved |
| API serving and operating controls | 0/1 = 0% | Public /health/live success is not private /health/ready and auth approval |
| Quantitative model validation | 0/3 = 0% | Exploration exists, zero independently approved risk betas or event impacts |

Formal automatic release gates = **11 passed / 24 total (45.8%)**. There are **13 automatic blockers** and **four separate manual approval requirements**. Institutional release is **FALSE**. Product implementation maturity is a separate engineering estimate (~35% institutional production), not the same as gate count or probability of economic accuracy.

## Real datasets loaded

| Dataset / measure | Verified count | Validity |
|---|---:|---|
| Historical market snapshots | 11,101,967 | Retrospective historical observations, not source-certified as-known |
| Raw security prices | 107,157 across 63 symbols | Backfilled Yahoo adjusted closes; original corporate actions/rights unapproved |
| Security adjusted-price return observations | 83,427 | Retrospective USD, not PIT total returns |
| Rate factor observations | 12,656 across 18 series | Treasury nominal/real plus derived gap proxy, provider vintages unverified |
| Daily rate shocks | 12,618 | Yield-change basis points |
| Historical single-rate-plus-SPY sensitivity estimates | 864 | **Zero** approved security risk betas |
| Prospective API market receipt observations | 15,445 | 1,889 Kalshi + 3,000 Polymarket newly captured October 24 |
| Forward event–factor warehouse-as-of grid | 278,010 | Warehouse-known timing, not historical published-at PIT |
| Graph path hypotheses | 8,216 | Proposed only |
| Pending human review cases | 97 | None independently approved |
| Security source >0.25 abs(log return) QA cases | 12 | Source review pending; large moves may be real |
| Duplicate FX source quote keys | 4 | Quote convention and source revision unverified |
| Affected rate beta models screened for outlier sensitivity | 72 | 30 change beta by >=20% under flag-exclusion sensitivity; not model approval |
| Field definition rules across 16 contracted domains | 274 | 146 mandatory absent, one mandatory present but wholly null |

## P0 blocking dependencies

1. **Fresh reliable ingestion** — on-demand Flights succeed, but the GitHub scheduled capture workflow has no enabled cron or scoped MotherDuck Actions secret. Restore/replace separate stale legacy realtime snapshots.
2. **Source original publication and replay** — venue quote timestamps, Treasury/FRED release and revision vintages, security corporate action history and true first-available records.
3. **Vendor permissions and secure backend access** — LAB_API_KEYS, MOTHERDUCK_TOKEN for Railway, rights acknowledgment **only after genuine legal approval**, negative auth and rollback tests.
4. **Independently reviewed economic mapping** — 97 queues prepared, real evidence/citations/reviewers absent.
5. **Robust security source QA** — 12 flagged market returns, four duplicate FX keys and a demonstrable sensitivity in 30 of 72 affected research beta fits. Review real vendor and exchange evidence, do not silently drop inconvenient observations.

Institutional multifactor betas, causal event→factor effects, and external use require all critical evidence above, improved licensed equity/FX/commodity/credit/style/volatility factor coverage, independent model-risk review and governed operations.

## Primary databases and owners

- MotherDuck: eventrisk_factor_lab, not the legacy event_risk or other production databases. Versioned QA tables: lab_security_price_exception_cases_v1, lab_security_duplicate_quote_cases_v1, lab_beta_price_exception_sensitivity_v1, lab_security_price_exception_builds_v1.
- Gate truth: lab_release_gate_summary_v1, lab_release_gate_history_v1, lab_release_unblock_register_v1 and lab_release_workstream_metrics_v1.
- Repository: sanga4/event_risk **main**. The separate huimarco/event_risk MVP stays unchanged.

**Important:** an app process that returns HTTP 200 from health/live is not a data-access approval, model validation or permission to trade.

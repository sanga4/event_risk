# EventRisk Factor — Institutional Phase I Status

**As-of:** October 25, 2026 UTC (October 24, Los Angeles; checked against MotherDuck and GitHub). This is an **as-of snapshot**, not a live telemetry dashboard. The authoritative current metrics are MotherDuck tables described below; rerun the release-gates Flight before using the numbers as a fresh assessment.

## Most recent institutional gate assessment — October 25, 2026 UTC

**19/39 automatic checks PASS (48.7%), 20 BLOCKED, plus four independently required manual approvals. Institutional production release remains FALSE.** Prior readiness snapshots in the historical milestones below are superseded.

**Newest quantitative and original-evidence methodology:** [Rolling Security Beta and Original Evidence Report](ROLLING_SECURITY_BETA_AND_EVIDENCE_METHODOLOGY.md).

| Newly executed evidence | Latest verified result |
|---|---|
| Full rolling FF5-plus-Momentum security beta windows | **958** windows across **48** USD securities |
| Research beta coefficients | **5,748** (six per window), no duplicate keys, zero released betas |
| Material adjacent beta shift screens | **59** rolling windows flagged, unreviewed |
| Weak full-vs-market-only holdout diagnostics | **36** windows flagged, unreviewed |
| Windows containing flagged adjusted-price movements | **65**, which are not automatically erroneous or excluded |
| Original-source evidence worklist | **448** distinct requirements for **113** cases (12 price, four duplicate FX, 97 event/mapping); **zero** independently verified or dual-approved |
| Source rights, release times and independent model risk | **0** approvals |
| Formal action register | **43** requirements across nine workstreams, **0** institutional approvals |

All retrospective factor and security inputs remain original publication-time uncertified. Do not call these trading betas, true event impacts, or approved portfolio risk parameters. The 8–15 substantive continuation request closeout estimate remains a planning range for engineering and research acceptance work, not institutional signoff.

## Prior Phase I release snapshot — October 24, 2026 (Los Angeles)

**Measured institutional automatic controls:** **17/35 passing (48.6%)**, 18 blocked, **four additional manual signoffs outstanding**; **production authorization remains FALSE**. The total number of controls grew as real new source and stability requirements were added. This is a gate pass fraction, not a business-completion percentage.

**Fast links:** [Closeout roadmap and number of requests](PHASE1_CLOSEOUT_ROADMAP.md) · [New rolling covariance / NY Fed report](PHASE1_CLOSEOUT_ROADMAP.md) · [Institutional blocker register](PHASE1_PRODUCTION_UNBLOCK_PLAN.md) · [Latest GitHub Actions](https://github.com/sanga4/event_risk/actions).

| Latest verified dataset or risk control | State |
|---|---|
| Prospective two-venue HTTP receipts | **20,334** captured; source quote-at independently verified **FALSE** |
| Prospective warehouse event/factor same-receipt research grid | **366,012** rows after another successful 88,002-row append, with **zero future-warehouse factor timing violations**; independent provider release-time certification FALSE |
| New York Fed official SOFR/EFFR rates | **500** publisher-sourced overnight rate levels (250 each), **498** descriptive daily bps changes; zero duplicate source observations on rerun |
| ECB informational EUR FX | **39,088** rates, seven currency pairs; nontradable with no original publication PIT |
| U.S. French equity style and RF research factors | **121,598** history observations across seven factor IDs; source commercial rights/vintages unapproved |
| Rolling mixed Treasury/FX/equity factor covariance | **17** historical 252/63-day windows; **17 flagged** for instability; median drift **59.1%**, p90 **202.9%** |
| Institutional source availability gap matrix | **7/16** source families loaded, **9 missing** (unapproved original vintages, licensed credit, executable FX, futures, options, portfolio, economic releases/evidence, corporate actions) |
| Original 255-field institutional source-contract audit | **119/255 populated (~47%)**, 135 missing, one empty first quote timestamp; separate schema scope from new family inventory |
| FRED economic source feed | Public FRED endpoint timed out twice; **zero FRED macro rows** loaded by that importer. NY Fed SOFR/EFFR partially fills separate official overnight rate requirement |

**Change in methodology:** the 7×7 factor covariance is only research descriptive; **all 17** rolling stability windows exceed prespecified drift/variance-review thresholds. This blocks institutional VaR/portfolio risk use without independent model-risk investigation, regime handling, true source published-at clocks, legal rights and authorized portfolios.

## Quick links

| What to inspect | Link |
|---|---|
| Factor Lab service process liveness | https://factor-lab-api-production.up.railway.app/health/live |
| Source code in sanga4 main | https://github.com/sanga4/event_risk |
| All GitHub pipeline/CI runs | https://github.com/sanga4/event_risk/actions |
| Latest institutional milestone pull request | https://github.com/sanga4/event_risk/pulls |
| Institutional Beta Methodology | https://github.com/sanga4/event_risk/blob/main/lab/INSTITUTIONAL_FACTOR_BETA_METHODOLOGY.md |
| Institutional Data Dictionary & Backfill | https://github.com/sanga4/event_risk/blob/main/lab/INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md |
| Required source/rights approvals | https://github.com/sanga4/event_risk/blob/main/lab/PHASE1_PRODUCTION_UNBLOCK_PLAN.md |
| Security source exceptions and beta robustness | https://github.com/sanga4/event_risk/blob/main/lab/SECURITY_SOURCE_QA_AND_BETA_SENSITIVITY.md |

## Latest methodology milestone — three-component Treasury curve model

Source-controlled risk-methodology code: [Treasury Curve Factor Model](INSTITUTIONAL_TREASURY_CURVE_MODEL.md) and `phase1_curve_factor_research.py`. MotherDuck Flight successfully fitted **48** joint SPY + Treasury nominal curve models (LEVEL/SLOPE/CURVATURE), and persisted **144** coefficient rows over **701** historical rate-change dates. **6** slopes have exploratory BH q under .05, **17** same-day holdout comparisons improve on SPY-only, **4** models contain previously flagged abnormal price movements; maximum standardized training design condition number **1.7616**. All model and source PIT/rights/production release flags remain **FALSE**. These are descriptive historical security-rate sensitivities, not independently approved betas or event-to-factor causal responses.

At the **earlier Treasury-curve milestone**, 11/24 automatic release gates passed (45.8%). This is historical, superseded by the current gate summary above; additional statistical calculations do not alone approve an investment model.



## New official U.S. equity-style factor data and six-factor model — October 24, 2026

See the [source/license/PIT and six-factor beta methodology](STYLE_FACTOR_SOURCE_AND_BETA_METHOD.md). The *official* Kenneth French daily U.S. five-factor + RF and separate momentum archives were downloaded into independently versioned private MotherDuck research tables. **121,598 historical factor-return observations, 7 source series**, daily factor histories through **2026-08-31**, 2 independently SHA256-recorded ZIP archive versions. A second execution made **0 duplicate rows**. Dates are historical observation dates; first source retrieval in our system was October 24, **not known-at in 1963/1926**, and commercial re-use/distribution approval is not established.

First complete **six-factor (Mkt-RF/SMB/HML/RMW/CMA/Mom)** USD-security research run: **48 models / 288 coefficients**, 15,897 complete joint U.S. factor days, 1,555–1,673 matched security observations/model, 151 global FDR q<5% *exploratory associations*, 27 same-day holdout improvements versus market-only, 9 models exposed to >25% adjusted-price-return flags, and **0** independently released institutional betas. RF is a *research cash return*, not a seventh risky beta. Source return percentages converted to daily simple decimals; dependent asset adjusted-close log returns converted back to daily simple returns before subtracting RF. Raw style returns/coefficients are deliberately not exposed via the service API.

At the **earlier style-factor milestone**, gate v1.6 had **12/26 passing, 14 blocked and 4 manual approvals open**. The new source-loaded gate passes; independent provider PIT/vintage/licensing gate stays blocked. Institutional mandatory field coverage improved to **119/255 ~47%**, with 135 required fields missing and one existing field entirely empty. Neither a loaded source nor a research FDR statistic implies institutional model approval.


## Latest verified research milestone — ECB FX and cross-asset risk matrix

Source-controlled [FX/Macro/Covariance Institutional Methodology](CROSS_ASSET_FX_MACRO_RISK_METHOD.md).

- **ECB primary source loaded:** 7 EUR-base informational reference pairs, **39,088 historical rates** and **39,081 daily log quote-per-EUR changes** over 2005-01-03 through 2026-10-23. Retried full source load and verified **zero duplicate source versions** and zero false PIT/execution/trading rights approvals.
- **Seven-factor cross-asset research:** Three Treasury nominal curve components, two ECB FX quote changes, two U.S. French research style portfolio returns, all matched on the same date with no weekly/monthly forward-fill. **655 calendar observations**, 458 training/197 holdout, **49 covariance cells**, 10% fixed diagonal shrinkage, training-only normalization. **Holdout covariance drift 69.94%**, material instability; risk model and source-license approvals FALSE.
- **U.S. FRED macro funding and conditions:** Versioned native-unit importer for DFF, SOFR, NFCI, CPIAUCSL, UNRATE and WALCL created and tested offline; the **actual FRED source service timed out twice** from MotherDuck. **ZERO of those source rows loaded**; official API/network access and original release-vintage history remain blocked.
- **Formal Phase I release gate v1.7:** 14 of 29 automatic PASS (**48.3%**), 15 BLOCKED, four manual sign-offs outstanding. New available-research-data checks pass but independent FX source/vintage/rights remains blocked.
- **Field inventory remains measured on the previous 16-domain scope**: 119/255 required fields structurally populated (~47%), 135 missing. New ECB/FRED source contracts need a future explicit versioned scope expansion; existing contract metric should NOT be silently enlarged or misrepresented as all global factor fields.

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

Formal automatic release gates = **17 passed / 35 total (48.6%)**. There are **18 automatic blockers** and **four separate manual approval requirements**. Institutional release is **FALSE**. Product implementation maturity is a separate engineering estimate (~35% institutional production), not the same as gate count or probability of economic accuracy.

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
| Forward event–factor warehouse-as-of grid | 366,012 | Warehouse-known timing, not historical published-at PIT |
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

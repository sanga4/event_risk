# EventRisk Factor — Institutional Phase I Closeout Roadmap and Work-Packages

## Latest verified execution — October 26, 2026 UTC

The October 24 numerical as-of material below remains historic. The **current** source-pinned status and institutional blockers are [PHASE1_CURRENT_VERIFIED_STATUS_2026_10_26.md](PHASE1_CURRENT_VERIFIED_STATUS_2026_10_26.md), including the accepted original Treasury XML source records and 893,988 event-factor co-observations, source-locked **20,064 paired security daily losses**, an independently replayed **96-model Holm audit with zero robust candidate survivors**, and a genuinely executed 54-gate release snapshot **25 PASS / 29 BLOCK + four manual**. Source first-published histories, legal data rights, corporate-action-vintage evidence, prospective sampling duration and original economic surprise timing—not merely additional code rounds—remain the critical path. Forecasting a fixed number of user turns or assigning an overall completion percentage from gate count would overstate the evidence.

**As-of:** 2026-10-24 Los Angeles. **Authoritative**: `sanga4/event_risk/main`; MotherDuck `eventrisk_factor_lab`. The separate huimarco/EventRisk MVP is not a deployment target.

## What was genuinely executed this milestone

- **Official overnight funding data:** 500 New York Fed `SOFR`/`EFFR` rate-level source observations, 250 each; annualized percent rates, not realized security returns or surprises. Two independent execution runs successful, second added **zero duplicate source versions/rows**. 498 day-to-day level differences in **basis points**, research only. Native effective date is NOT historical published-at. NY Fed official data source: https://markets.newyorkfed.org/api/rates/secured/sofr/last/250.json . Rights/revision histories remain unapproved.
- **Rolling covariance risk:** 17 actual 252-day training + 63-day heldout + 21-day-step cross-asset seven-factor windows, on 655 intersecting rate/FX/style observation dates. **All 17** windows breach either predefined >0.50 relative covariance drift or >2× variance-ratio review threshold. Median heldout covariance drift **0.5906** (~59.1%); 90th-percentile **2.0289** (~202.9%); maximum **2.2533** (~225.3%). This is a quantitative failure-of-stability screen, not an approved VaR model.
- **Source completeness truth ledger:** 16 independent source families audited, **7 loaded and 9 unpopulated**: original market snapshots, prospective receipts, USD security prices, Treasury levels, US style factors, ECB reference FX, NY Fed rates are available; FRED macro, original corporate actions, tradeable FX, licensed credit, futures, options volatility, authorized portfolio holdings, timestamped macro consensus and original reviewable event evidence are **not loaded** in the specified source families. Every family remains uncertified for original publication PIT, external rights and risk production use.
- **Prospective venue capture:** refreshed 4,889 market records (Kalshi 1,889; Polymarket bounded 3,000), bringing total receipts to **20,334**. These are capture-at HTTP receipts, not validated quote creation dates. The collector is on-demand, NOT scheduled.

## What is unblocked and what is not

| Workstream | Working now | Blocking institutional acceptance |
|---|---|---|
| Research source ingestion | 7/16 data families, source hashes and explicit transform conventions | 9 absent families, permissions and exact original publication/revisions |
| Overnight reference rates | NY Fed 250 SOFR + 250 EFFR publisher source records | Period before 2025, historical first publication, vendor terms, forecast-consensus surprises |
| FX | 7 informational EUR-quoted ECB reference pairs | True executable FX bid/ask and intraday time, source terms, historical vintages |
| US equity styles | 121,598 historical Kenneth French US FF/Momentum/RF points | First-known archives, CRSP/redistribution terms, survivor bias |
| Curve and equity factor risk | 48 security curve models + 48 FF6 equity style models, 144+288 descriptive coefficients | Independent adjusted-return PIT universe, corporate actions and model-risk review |
| Joint covariance | 7×7, 49 cells, 17 rolling windows and instability metrics | Every window demands regime stability review; true exposures/positions absent |
| Event→economic links | Prospective event/factor co-observation grid and reviewer queue | 0 independently accepted source evidence/event innovations or causally identified effects |
| Deployment | Railway application liveness 200 and source-controlled CI | Restricted API credentials, vendor usage rights, monitoring/rollback, scheduled capture |

## How many additional requests?

**Forecast, not a promise or an objective completion fraction**: roughly **8–15 substantial multi-deliverable continuation rounds** to reach an **engineering-complete institutional Phase I release candidate**, *if* authorized source access, security histories and domain decisions arrive early. This estimates coding, actual data backfills, testing and documentation rather than business/legal sign-off.

Potential division of those rounds (work streams can overlap):

1. **Two to four source/historical-vintage rounds:** complete official macro calendars and revisions, permanent security identifiers/corporate actions including delisted names, source rights evidence, and approved historical market quotes. FRED web CSV is currently blocked by outbound timeouts; NY Fed official API source is a partial workaround for SOFR/EFFR only.
2. **Two to four factor/risk methodology rounds:** validated cross-asset factor universe, robust covariance/regime model, factor-beta stability, factor exposures and heldout statistical reviews. Each scenario needs actual tradable exposure data and correct economic units.
3. **Two to three event/economics rounds:** original quote-time/consensus, event surprise ontology, time-resolved event→economic-channel mapping, real evidence archive and independent reviewer decision workflow. A queue cannot self-approve causal effects.
4. **Two to four operational/security/acceptance rounds:** scheduled collection, secret management, rights scoped serving, observability, runbooks, replay tests, negative auth cases, gated releases and independent audit artifacts.

**Full signed institutional production approval has no bounded request count.** Data-vendor permission, legal contracts, API keys, independent analyst review and model-risk committee approval happen outside assistant code; it may take weeks/months or remain unavailable. If the intended scope also includes **Phase II portfolio products and production trading/enterprise distribution**, add roughly **5–10+ more substantial engineering rounds after Phase I groundwork**, again conditional on positions, licenses, model approval and product scope. These ranges are heuristic planning estimates, not delivery commitments.

## User-owned unblocking checklist (do not paste secrets)

- GitHub repository `sanga4/event_risk` → Settings → Secrets and variables → Actions → repository secret `MOTHERDUCK_TOKEN`, least-privilege warehouse account. Authorize and test a manual recurring capture; only then enable a true schedule/alerts. Current MotherDuck plan does not support scheduled Flights.
- Railway project `eventrisk-factor-lab` → service `factor-lab-api` → Variables: confirm `LAB_DB=eventrisk_factor_lab`, store scoped `MOTHERDUCK_TOKEN` and `LAB_API_KEYS`, and set `LAB_DATA_RIGHTS_ACK` ONLY after vendor rights actually allow intended use. App `/health/live` indicates liveness only.
- Provide permitted primary security-master/corporate-action, FX/credit/commodity/volatility and official vintage history providers; do not assume public endpoints grant commercial distribution rights.
- Appoint independent economic mechanism reviewers and model-risk approvers and require dated signed evidence; never automate approval flags.

## Boundaries

Production risk/portfolio beta release stays blocked. Source timestamps from retrieval cannot be converted to historic first-publication timestamps. FDR significance and same-day holdout fit do not demonstrate tradable alpha. Strong historical covariance drift must not be papered over with artificial backfills, hindsight joins or threshold changes.

[One-page Project Status](PROJECT_STATUS.md) · [Release Blockers](PHASE1_PRODUCTION_UNBLOCK_PLAN.md) · [Full Source Data Dictionary](INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md) · [Cross-Asset Methodology](CROSS_ASSET_FX_MACRO_RISK_METHOD.md)
# EventRisk: Institutional Data Dictionary and Factor-Acquisition Standard

Version 1.0 | 2026-10-24 | RESEARCH GOVERNANCE DRAFT — NOT PRODUCTION APPROVED

Authoritative owner: sanga4/event_risk, lab subtree. The executable 16-dataset field contract is institutional_data_contracts.py. The measured MotherDuck registry is lab_institutional_field_contracts_v1, lab_institutional_field_audit_v1, lab_institutional_dataset_audit_v1 and lab_institutional_data_contract_builds_v1. Never push to the separate huimarco repo.

## 1. Evidence-based completion accounting

The first run inventoried **274 field rules** (255 mandatory; 19 optional) across **16 datasets**. There are **146 mandatory missing fields**, including fields whose target dataset is not built, and **one mandatory field present but entirely null**: original venue quote time. This measures structural field presence and populated values, NOT independent source veracity, legal rights or model readiness. Ten existing datasets have data; six institutional target datasets are not loaded. A database with millions of observations can still fail required field coverage.

Loaded and retained research sources: 11,101,967 historical market snapshots; 107,157 security prices across 63 symbols; 83,427 USD adjusted-price return observations; 12,656 factor observation versions across 18 modeled rate/derived-proxy series; 12,618 derived daily rate shocks; 10,556 forward-collected market quote receipts; 190,008 warehouse-as-of event/factor co-observations; 8,216 event graph path hypotheses; 864 single-rate-plus-SPY historical sensitivity regressions; 97 proposed human-review cases; no institutional risk models approved.

## 2. Required source clocks and versioning

A reproducible as-of record must distinguish:

| Field | Definition | Independent verification |
|---|---|---|
| observed_at or observed_date | Source market observation / economic reference date | Not proof of original availability |
| provider_quote_at or source_published_at | Original provider first publication / exchange quote time | May be NULL, never inferred from retrieval |
| capture_received_at or retrieved_at | Earliest timestamp collector received bytes | System receipt claim only |
| warehouse_ingested_at | When that exact version was stored | Immutable processing-time record |
| first_available_to_model_at | Conservative first time model could access the exact version under entitlements | Separately approved from receipt, release and permission |
| revision_id / realtime_start / realtime_end | Published revisions and date-vintage intervals | Date resolution must not become fabricated intraday precision |
| mapping_available_at / evidence_source_published_at | Availability of economic transmission hypothesis and evidence | No backdating hindsight graph links |
| asof_training_cutoff / model_version | Training freeze and parameter lineage | Freeze before holdout and decision |

Never overwrite a first-observed vintage with today's revised number. If source and quote clocks are missing, the observation stays research-only.

## 3. Factor family source contracts and transformations

| Intended factor family | Required source | Unit and shock | Lab status |
|---|---|---|---|
| Nominal Treasury rates | Treasury par yield curve with original release/vintage | Yield percent level; 100×difference is bps | 11 maturity series loaded; source publication clock not certified |
| TIPS real rates | Treasury real par yield curves with release/vintage | Real yield percent; changes bps | 5 maturities loaded; time certification pending |
| Nominal–real gaps | Versioned matched nominal and real par yields | Percent-gap proxy; changes bps | 2 derived proxies loaded; NOT actual inflation breakevens |
| Policy/funding | Federal Reserve target, effective and funding/OIS series | bps changes; policy shock needs timestamped consensus | Not loaded as separate model factors |
| CPI/PCE/inflation expectations | Official first releases, vintages, timestamped consensus or licensed swaps | Surprise versus pre-release forecast; maturity/horizon | Not loaded |
| Credit/default/liquidity | Appropriately licensed IG/HY credit indices, duration and liquidity | OAS/bps with vintage and rights | Two ICE/BofA series inactive/restricted |
| FX | Source spot/fixings, pair base/quote, calendar and timezone | Log quote-currency return, quote orientation fixed | FX-like symbols in security price history; no approved FX factor returns |
| Equity broad market and sectors | Licensed total-return indexes with constituents, dividends and currency | Total/excess benchmark return; simple/log convention | Some ETFs available only as retrospective price proxies |
| Equity styles | Documented Fama-French portfolio returns by market/region and historical archives | Daily simple long–short/excess returns, vintage-reproducible | Not loaded |
| Commodities energy/metals | Source futures contract, delivery/roll or true spot and source rights | Spot log return or futures excess return, separately defined | Gold ETF exists, but gold factor itself NOT loaded |
| Implied/realized volatility | Option or VIX-style licensed dataset, horizon, index construction | Volatility points or log index returns, prespecified | Not loaded |
| Financial conditions | NFCI with official release/vintage | Index point change; weekly release time matters | Catalog entry with zero observations |
| Country/style/sector | Versioned indices and as-of constituent membership | Country/sector excess return, USD conversion | ETF proxies only; not independent factor series |
| Supply-chain/geopolitical events | Canonical event ontology plus signed source evidence | Event innovation first, then identified transmission response | Candidate graph links; no approved causal betas |

No ETF, proxy spread or qualitative factor label automatically becomes an approved canonical financial risk-factor return. All factor definitions require source series ID, family, observation calendar, unit, shock transformation, direction convention, exposure benchmark, original publish time, revision vintage, license, risk-model status and source checksum.

### Rate factor collinearity

The source-controlled factor diagnostics populated 22 factor specifications and 153 rate-shock pairwise correlations. Nine pairs have absolute correlation at least 0.95; 33 pairs touch algebraically derived nominal-minus-real yield proxies. Example: 20y and 30y nominal Treasury daily changes correlate about 0.981 over 701 matched days. Never use the nominal and real factors plus their deterministic gap as unconstrained independent regressors. Production choices require prespecified key-rate buckets, maturity curve PCs (trained strictly within training windows), or regularization with rank/VIF/condition and factor covariance diagnostics.

## 4. Security prices, returns and permanent identities

Raw security source requirements: permanent source security ID, ticker and ticker-valid-from/to, exchange MIC, security type, domicile, issuer, sector industry, country, first listing and delisting dates, currency, exchange calendar, trading timezone, corporate actions with source publication/vintage, clean raw price and adjusted price, dividend/split methodology, source original publication timestamp, retrieval timestamp, checksum, source rights, FX conversion path and tax/fee assumptions.

Current historical security_prices has 107,157 Yahoo-sourced records from one October 17, 2026 backfill. Four ticker-date duplicates were resolved in the derived research returns. Twelve adjusted-price log moves over 25% remain flagged for independent investigation. Non-USD price rows include FX pairs and Asian securities: never treat them as USD security total returns without pair quote convention, corporate-action verification and as-of FX translation. SPY is merely a contemporaneous benchmark control; it does not confer model authorization.

## 5. Event innovation and mapping evidence

For each market: venue, immutable market/contract version, venue quote time, collector receipt, yes-bid/ask/last, spreads/depth/liquidity, source hash, question wording, outcomes, negation, resolution rules/source, status, cancellation, expiry and settlement. Normalize probability to [0,1] and changes to percentage points only across contract-consistent versions. A probability change is not necessarily an identified information surprise. Actual innovation requires an ex ante forecast/consensus and announcement clock.

Economic transmission edges need event ID, geography, subject/entity, action, event class, economic channel, mechanism, intermediate variable, risk factor ID, sign ambiguity, lag/horizon, timestamp first-known, signed reviewer and independent peer reviewer, source publication date, evidence content checksum, citation/license and rejection outcomes. Current 8,216 generated hypotheses and 97 pending review items cannot be called approved just because the graph existed before a NEW market API receipt.

## 6. Betas and scenario construction

**Security factor sensitivity:** on compatible eligible asset excess returns and factor shocks, estimate a specified market/sector/macro/FX/credit/commodity/style model; report beta unit, permanent security ID, dates, currency, train-only scaling, versioned factor covariance, residual variance, conditioning and VIF, HAC/clustered/bootstrapped SE, rolling stability, out-of-sample and rights status. Do not combine 18 correlated rate factors without explicit identification or regularization. The current 864 SPY-plus-one-yield fits are ex-post descriptions, not an approved multifactor model.

**Event factor response:** separately estimate identified event surprise to factor level/return reaction at predeclared 1h/1d/5d horizons only if data timing and frequency support them. Match the original source publication to tradable factor clocks; control for overlapping announcements and pre-trends. Do not call date-level co-movement causal impact.

**Portfolio risk:** requires actual authorized position files (permanent ID, quantities, market value, currency, as-of, FX conversion, sensitivity freeze), factor covariance, portfolio residuals, liquidity and approved scenario shocks. Do not infer holdings from question text or forecast P&L with missing betas.

## 7. Immediate acquisition/backfill and sign-off order

P0: Preserve historic backfill but never classify it as known-at the historical date. Independently verify corporate-action adjustments, original security quotes, data licenses, Treasury release/vintage clocks, provider quote times, source response bytes and issuer identities. Track the 146 missing required fields as a remediation backlog.

P1: Import explicitly licensed/authorized official Treasury and ALFRED revisions, policy rates, verified equity total-return indices, FX convention-correct quote histories, official style portfolio research factors (with usage rights) and commodity/credit/volatility sources, each into its own versioned raw tables with exact units. Populate missing source fields only from **actual evidence**. Source snapshots and historical revisions must remain append-only.

P1: Acquire security master and delisted universe, evidence-backed event mapping reviews, legal permissions, and original provider first-publication clocks. These are prerequisites for PIT beta backtesting.

P2: Train actual factor models and event-response models, with pre-registered horizons, temporal purging, robust/clustered uncertainty, FDR, out-of-sample monitoring, independently reviewed model cards, licence signoff and operational release approvals. Keep both data and model release bits false until each evidence gate passes.

## 8. Official reference sources — not blanket reuse licences

- Treasury daily par yield and methodology: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?page=1&type=daily_treasury_yield_curve
- ALFRED/FRED realtime periods: https://fred.stlouisfed.org/docs/api/fred/realtime_period.html
- FRED revision dates: https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html
- Kenneth French style return definitions and archives: https://mba.tuck.dartmouth.edu/pages/faculty/Ken.French/data_library.html

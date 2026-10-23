# EventRisk Phase I — Forward mapping review protocol

## Scope, provenance, and independence

Review the **hypothesis** that an event or forecasted outcome can transmit to a measurable economic variable and then a financial risk factor. Proposed graph links are **not** independently approved or backtest-safe, even if their recorded `mapping_available_at` timestamp precedes a new API-response receipt.

Data lives in `eventrisk_factor_lab.main.lab_forward_mapping_hypotheses_v1` and its review queue `lab_forward_mapping_review_queue_v1`. The source-controlled producer is `lab/phase1_forward_mapping_review.py`. Only `sanga4/event_risk/main` is used for this project; never push these scripts to `huimarco/event_risk`.

The first 2026-10-23 build materialized 8,216 unique forward hypotheses, covering 612 newly captured markets and four permitted source factor series, and generated 97 diversified pending human-review cases. Zero mappings were approved. All source graph paths were marked `historical_mapping_lookahead=TRUE` for their older snapshot date; they may be **forward research hypotheses only after their mapping creation time**.

## Human reviewer checklist

For each `review_id`, open the original market question and resolution rules. Independently inspect the linked source graph edges, event entity/action/channel, economic mechanism, macro variable and proposed factor. Record all of the following before claiming a hypothesis is evidence-supported:

1. Full reviewer ID and timestamp; another independent reviewer or governance owner must eventually validate sensitive or controversial links.
2. Decision **reject**, **defer/needs evidence**, or **evidence supported for forward research**. Avoid binary trade/use conclusions.
3. The exact event-to-economic-channel causal narrative, alternative pathways, direction ambiguity, country/geography, and expected lag. A co-occurrence alone is never evidence.
4. Evidence source URL, document title, snippet, source publication timestamp, SHA256/content version, relevance and licensing restrictions. Check the source was published at/before the applicable **forward capture**, not merely retrieved afterwards.
5. Record data limitations: public market quote receipt timestamp is not the exchange's quote publication timestamp; Treasury/FRED warehouse ingestion time is not independently verified first public release/vintage time; restricted ICE/BofA credit and unchecked licensing sources are excluded.
6. Reviewer rationale including confounders (macro announcements, central-bank actions, risk appetite), resolution horizon, whether the mapping changes by regime, evidence supporting and contradicting the thesis.
7. Keep institutional/backtest release flags **FALSE**. A human's evidence-supported relationship does not automatically confer source time certification, statistical significance, rights clearance or investment deployment.

## Suggested sampling and review decisions

The queue is deterministically sampled up to four market propositions per venue × event-channel × factor stratum using a stable hash. Existing legacy review cases are not duplicated. This gives broad hypothesis coverage; it is **not** random selection of all markets for error-rate inference and is **not** a calibrated statistical accuracy sample.

Proposed analyst evaluation labels:
- `reject`: the event/channel/financial transmission mechanism is wrong or speculative with no defensible mechanism.
- `defer`: insufficient evidence, unresolved definition, licensing or timestamp ambiguity.
- `evidence_supported_forward_only`: a reviewed, cited mechanism *could* transmit to the factor after the date it was recorded. This is NOT a pre-2026-10-23 hindsight-free historical mapping.
- `independent_peer_review_pending`: second review needed before approval candidate.

Review status stays `pending_human_review` until a signed independent attestation is actually submitted and accepted in a separate governed review process. Do not populate reviewer identity, sources or decisions using generated text.

## Read-only research API

- `GET /v1/research/mappings/forward/summary`: counts, leakage counters and human-review readiness.
- `GET /v1/research/mappings/forward/queue`: paginated and filtered review cards, still unapproved.
- Both require the research service's scoped `X-API-Key` and correctly configured MotherDuck access and data-rights variables.
- **No public reviewer-write endpoint** has been enabled; decisions must remain attributable, audited and separately authorized.

## Release gates and next owner actions

The review materializer's success verifies that proposed relationships are traceable; it does not meet the independent-human-evidence gate. Remaining conditions include actual review decisions, external quote/factor publication time certification, authenticated incremental capture schedule (MotherDuck Flight scheduling is unavailable on the current plan), licensing acceptance, source-controlled research validation and independent production signoff. Never set `historically_backtest_released` or `released_for_signal_use` to TRUE from a preparation script.

# Phase I — Original BEA release pages: actual published economic data AS RECEIVED

**Scope:** public BEA source packets for August 2026 PCE/personal income and international trade, now retrievable directly from the official `bea.gov` publisher. The collected pages represent what BEA served **at our HTTP receipt time** in October 2026, not what was necessarily displayed in the minute of their original September 30 and October 6 release. Never recast page-retrieval time as original first-publication time.

## Verified source probes

On-demand MotherDuck Flight `d6b8e138-55c8-4844-9e95-d3f3a60d4ed2` #1 actually retrieved both pages with HTTP **200**, no redirects, HTML content:

- [Official personal income and outlays, August 2026](https://www.bea.gov/news/2026/personal-income-and-outlays-August-2026): **52,287** bytes; SHA256 `921b66e9910f292a0e84a52eaec1f5a79335e143dfbc2c4caa036ec921b34264`. Publisher's personal income/PCE table reports seven July-to-August percent-change labels: current-dollar income **0.2**, current-dollar disposable income **0.3**, real disposable income **0.0**, current-dollar PCE **0.9**, real PCE **0.6**, PCE price index **0.3**, core PCE price index excluding food/energy **0.2**. These are percent changes, NOT percentage-point surprises.
- [Official international trade in goods and services, August 2026](https://www.bea.gov/news/2026/us-international-trade-goods-and-services-august-2026): **94,015** bytes; SHA256 `3d01bc6395a85ea0aa39c2c53268c40d1356f6661027ca5fd0835dc514b7e0e4`. The issuer's release summary reports August trade deficit magnitude **$105.6 billion**, exports **$315.2 billion**, imports **$420.8 billion**. The deficit is stored as a **positive reported magnitude**, not a signed net-accounting trade balance.

Second read-only source table-shape Flight `48d2eca3-f1f7-4f04-b814-cbaca899e504` #1 verified actual publisher DOM properties: personal income `table.table-md` (July/August rates) and trade `table.table-release-trade` (Deficit/Exports/Imports). Both headline and metric values were inspected directly from real publisher HTML; fake fixtures are separately tested.

## The collector

`lab/phase1_bea_original_economic_release_value_receipt.py` is a source commit-pinned, **read-only by default** original-payload collector that requires both official exact allowlisted source URLs, HTTP 200, no redirects, HTML, bounded byte sizes, exact publisher headline and table identity, exactly 7 PCE/person-income measures and 3 trade measures, native units, source-date label `2026-08` and SHA256 of original source bytes.

Only an explicit `--append-research` with `LAB_RESEARCH_WRITE_ACK=confirmed` can append to two new **internal-research-only** tables: `lab_bea_original_release_page_receipts_v1` (per-page original response BLOB, SHA256, real source response UTC receipt clock, later warehouse load clock) and `lab_bea_original_reported_values_v1` (ten native published number and unit labels, original packet linkage and original source receipt clocks). No old-source revision is overwritten, no artificially earlier availability is assigned, and re-inserting identical source bytes is rejected.

Both tables maintain **FALSE** flags for original publisher first-known/published-as-known PIT, source revision chronology, pre-event consensus, contractual downstream use and institutional event modeling. The reported-values table has **NULL** `publisher_first_known_at` and `verified_announcement_surprise` by design. An original source headline quoting **embargo date/time** is evidence of stated embargo intent, not independently verified first-publication clocks.

## Interpretation

Actual economic reported values are more substantive than a *future release schedule*, but **not yet first-publication-vintage-certified economic innovations**. In particular, a published price index level/percent change minus a guessed expectation is not an independently known pre-announcement surprise. A legitimate event surprise requires versioned forecast/consensus evidence stamped strictly BEFORE the actual independent source release and the original market quote clock. The present collector does not create or attest `lab_source_release_vintages_v1`, `lab_event_innovations_v1`, risk betas, or release approval.

The latest executed institutional review remains **25/54** automatic PASS, 29 automatic BLOCK, 4 manual, production FALSE. This pipeline must pass the full GitHub test suite, then a real read-only preview and an independently replayed post-write **SELECT-only** raw-source parser/math/clock audit before stored numbers may be described as accepted internal-source records.

**Repetition limit:** Once original packets are successfully appended and independently verified, disable the one-shot write acknowledgment. Do not re-run merely because follow-up QA needs debugging. No automatic scheduled runs or source-rights approvals are granted here.

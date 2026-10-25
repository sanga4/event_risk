# Phase I — checkpointed research validation batch

**Producer:** `lab/phase1_research_checkpoint_runner.py`. It is a source-pinned, on-demand MotherDuck Flight that performs five *append-only research diagnostics* sequentially: independent original source-clock gaps, seven-factor covariance tail calibration, FF6 rolling beta integrity, institutionally blocked release-gate recomputation, and its downstream blocker register. It does **not** import new market data, repair prices, grant licenses, run model approvals or deploy the API.

## Usage and restart semantics

The MotherDuck Flight is created with `LAB_RESEARCH_SCOPE=internal-only`, `LAB_RUNNER_COMMIT=<40hex actual Git commit of runner>`, and `LAB_BATCH_ID=<32hex unique identifier>`. Source scripts are fetched only from hard-pinned GitHub commit `dd7f4dcff70dba20e35db358fec4233c7282361f`, and each fetched payload is checked against its *exact Git blob hash*, compiled, then SHA-256 recorded. The Flight itself runs without a calendar schedule and without external user-supplied secrets; the MotherDuck Flight infrastructure supplies its own attached warehouse token.

Re-run the Flight with **the same batch ID and pinned runner version** after an interruption: all `SUCCEEDED` stages are re-verified against exact source/build/approval manifests and skipped; any unfinished stage is re-executed. Use a **fresh batch ID** to recompute metrics on newly loaded data. Different runner/source identities, incomplete prior stages, missing source artifacts, conflicting successful builds and any institutional release flags cause immediate failure. A failed subprocess must not persist raw stderr, source URLs or tokens; journal records only a safe exception class. One flight can perform all five stages in a single remote execution without additional ChatGPT prompts.

The journal `eventrisk_factor_lab.main.lab_research_checkpoint_events_v1` has stable batch ID, distinct attempt ID, stage ordinal, state, build identifier, immutable producer SHA lineage, runner SHA256, timestamp and explicit release FALSE. A successful downstream register must cite the same batch's immediately preceding release-gate build. No operator should treat `SUCCEEDED` as commercial model authorization.

## Explicit engineering limits

**This is at-least-once stage execution, not exactly-once replay or an immutable historical data snapshot.** A worker may die after a producer committed but before its success journal entry; an ensuing retry then produces a separate append-only research build. Source market prices and original snapshots are never updated by these stages. Source upstream datasets are mutable between runs. No distributed mutex or atomic execution lease exists: operators MUST serialize invocations for a batch and all production warehouse writers. Do not schedule overlapping warehouse runs. This runner deliberately has no automatic transient retries of child writes.

**An on-demand MotherDuck Flight is not persistent autonomous continuous operation.** Actual no-chat future scheduling or alerting requires independently provisioned least-privilege credentials, a supported GitHub Actions/worker scheduler, tested alarms, data-rights approval for each source, and a separate ops decision. The repository already has an on-demand, serial GitHub Actions QA workflow gated on a scoped `MOTHERDUCK_TOKEN` repository secret.

The run neither certifies historical provider original publication clocks nor solves the FRED registered-key, nine absent source families, four manual approvals or beta/covariance model-risk deficiencies. The institutional release switch remains FALSE.

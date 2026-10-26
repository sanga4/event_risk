# Phase I — BEA economic actuals / source-receipt and release-gate freshness preflight

**Status:** independent, SELECT-only acceptance tooling for *already received* official BEA August 2026 personal-income/PCE and trade publisher pages. It does not collect new data, publish models, alter existing warehouse rows, create release vintages, or grant permissions.

## Why this was added

On October 26, 2026, the immutable BEA packets and ten native-value observations were accepted in MotherDuck (source materialization at 03:23:53 UTC). The last materialized Phase I 54-automatic-gate release snapshot is from **02:10:05 UTC**, earlier than the source load. A passed *source receipt* audit is not evidence that the subsequent source has itself passed a new institutional gate evaluation.

The audit separates four facts:
1. Original BEA HTML bytes and their independently accepted packet hashes, source Git commit and real HTTP-received/warehouse-ingested times agree with all ten values.
2. Seven personal-income/PCE numbers are explicitly **percent changes from the prior month**, not forecast surprises; three trade numbers are **positive USD-billion magnitudes**. The separately rounded trade deficit is consistent with imports less exports within a maximum $0.15 billion rounding tolerance.
3. The publisher first-publication, pre-event-consensus, redistribution-rights and model-approval fields remain exactly FALSE / NULL (unknown flags also fail). Zero values are eligible for event innovations or factor-beta release.
4. Latest pinned institutional release snapshot has 25 PASS/29 BLOCK + four manual outstanding and is **older** than the last BEA receipt. Report this as a gate-refresh dependency, not as a new automatic gate failure or a change in the fraction passed.

## Run (read-only)

From repository root with a separately scoped **read-only** MotherDuck connection token configured outside code and logs:

```sh
python lab/phase1_bea_event_surprise_eligibility.py \
  --source-build phase1-bea-original-release-values-receipt-v1.0.0-20261026T032352560589Z \
  --producer-commit 351b77f382e0d4f23d3e6950bfe949dfcf78cd88 \
  --gate-build phase1-gates-v2.4.0-20261026T021002390238Z \
  --income-sha256 921b66e9910f292a0e84a52eaec1f5a79335e143dfbc2c4caa036ec921b34264 \
  --trade-sha256 3d01bc6395a85ea0aa39c2c53268c40d1356f6661027ca5fd0835dc514b7e0e4
```

Read-only SQL uses pinned build IDs with bound parameters, and independently rehashes both original HTML BLOB packets against caller-supplied, previously accepted source digests. A mismatch or unsupported approval state raises, rather than producing an affirmative report. The parent original-source numerical reparser is separately maintained in `phase1_bea_original_reported_value_acceptance.py`; that independently re-parses actual BEA HTML and was executed successfully as Flight `ec3638ce-cfc1-42db-a0a6-73a85c9f77bc` #1. This new preflight is complementary consistency/methodological gating, **not a substitute** for that source reparser, vendor documentation, or independent publication-clock certification.

Offline adversarial tests are in `tests/test_lab_bea_event_surprise_eligibility.py`, automatically discovered by the existing `verify_phase1_lab.yml` job using `test_lab_*.py`. They exercise tampered source bytes, hash pin mismatch, mixed builds, duplicate and missing metrics, native-unit violations, invalid market accounting, altered source or receipt timestamps, forged event surprises, unknown/TRUE license or PIT flags, and false institutional release assertions. These fixtures do not constitute real source data or a warehouse acceptance run.

## What remains blocked

- Historical BEA page *retrieval* on October 26 cannot establish what was actually first published at the September/October release cutoffs.
- An economic actual or prior-month comparative is not a forecast consensus. Obtain publisher-original first-release archives, independently timestamped pre-release market consensus, and signed source entitlements before computing an economic surprise.
- A refreshed institutional release-gate materialization may be run only through the existing source-controlled producer and its independent acceptance workflow. Do not alter old immutable gate rows or claim that this audit changed the 25/54 gate ratio.
- No change to the API, Railway deployment, rights settings, model approvals, or investment-signal release is part of this addition.

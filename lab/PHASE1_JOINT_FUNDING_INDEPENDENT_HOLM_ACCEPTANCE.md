# Phase I — Independent original-parent 96-cell Holm audit acceptance

**Source auditor**: `lab/phase1_joint_funding_familywise_acceptance.py`. Its `verify(...)` is a pure function with ten synthetic adversarial regression tests; its CLI uses only **SELECT** against the original parent model, original v1.1 familywise build manifest, and persisted 96 original-family model rows.

**Production risk approval**: NOT granted. Reproducing a retrospective 96-cell coefficient/p-value screen neither authenticates issuer price adjustment PIT nor licenses a beta for institutional risk models.

## Rationale and observed evidence

The source-locked internal-research familywise producer v1.1 was actually executed on October 26 UTC under build `phase1-joint-funding-familywise-v1.1.0-20261026T020207074946Z` from Git SHA `5ede48ca6adf59461a430dede47bc03756ba2047`. Its original code SHA256 is `f668e525d84052b1e719748a4d990bfac989e887a5b415616390e186c5fec26c`; original parent build `phase1-joint-security-funding-v1.0.0-20261025T171802478028Z`.

The output comprises 48 tickers × two prespecified training variants: 22 nominal five-lag HAC normal-tail p-values below 0.05, **zero** 96-family Holm adjusted p-values below 0.05 (lowest 0.13537), **zero** joint beta candidates, 10 sign-flip securities, 30 with large beta shifts, and 41 failing cross-variant screening. The original manifest and rows both carry FALSE PIT, original issuer correction rights, license and institutional release flags.

Source table cardinality and flags were independently checked with MotherDuck read-only SQL. This newer verifier adds *independent replay of every original coefficient-derived p-value, global Holm order, cumulative adjusted probability, training-pair stability status and persisted build counters*, rather than trusting the producer's already-materialized output.

## Acceptance contract

1. Require the exact original producer source-code SHA256 from the reviewed Git commit. Audit manifest source Git SHA, code digest, original model source rows SHA256 (Python deterministic `repr` of original 96 ordered DB rows), and parent model build identity must match.
2. Parent model must have 96 nonduplicated two-variant records across 48 tickers, valid source date/holdout/fitting population, finite nonzero HAC SE, zero source-approval flags. All original source coefficient and preliminary screen states are independently checked.
3. Independently compute `erfc(|funding_beta / HAC_SE|/sqrt(2))` for every original cell, sort the **entire 96-cell family** by original two-sided p-value and stable ticker/variant order, apply cumulative `max(previous, (96−rank+1)*p)` capped at 1; compare each stored 96-cell rank, nominal p, adjusted Holm p and nominal/Holm significance flag.
4. Recompute both variants' funding-beta signs, coefficient shifts (relative to the full-training source estimate), cross-variant heldout-skill requirement, original parent training-half/HAC screen status and final reject state; compare every stored per-cell output, including original mean holdout skill, original fitted beta and HAC SE.
5. Recompute all 96-cell manifest counters, both minimum probabilities, full-family pass count, 48-security sign/research exclusion counts, approval flags. **No source right/PIT/institutional approval may be true.**
6. Reject a missing or duplicated source or audit record, changed SHA, mutated beta/p-value/rank, changed model variant, forged sign-stability claim, or unauthorized approval.

## Usage

For an authorized research read-only MotherDuck connection:

```bash
python lab/phase1_joint_funding_familywise_acceptance.py \
  --source-commit 5ede48ca6adf59461a430dede47bc03756ba2047
```

The auditor computes the SHA of the adjacent exact original `lab/phase1_joint_funding_familywise_audit.py`. If independently replaying the original executed build from a **later repository revision**, the supplied `--source-commit` **must still refer to the writer's original SHA**, and that exact original producer source byte file must accompany the auditor. Do not substitute future estimator source bytes.

**Operational state:** PR #67 introduces this independent verifier; do not label the 96-cell materialization as independently accepted by this new script until a completed live read-only execution returns `INDEPENDENT_HOLM_96_SOURCE_REPLAY_ACCEPTED_RESEARCH_ONLY`.

## Interpretation

A 96-model Holm corrected p-value does not establish a valid original-source time-aware distribution, free causal innovation, or economically validated risk factor. Cross-security p-values are exposed to common dates and correlated macro shocks. The separate 209-date 48-security paired-loss max-t bootstrap is the better screen for clustered shared-date predictability and found no security passing both training variants. Both methods may only **reject** weak retrospective coefficients. Original source rights, pre-event consensus, issuer corporate action as-known and independent model governance must be reviewed before any institutional funding-beta release.

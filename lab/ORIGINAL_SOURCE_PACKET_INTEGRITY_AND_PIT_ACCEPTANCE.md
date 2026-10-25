# Phase I — Source payload integrity and independently attested historical clocks

**Owner:** EventRisk Factor research infrastructure. **Release status:** source-evidence intake tooling only; institutional release blocked.

## Why this is required

A warehouse receipt and a valid SHA256 digest do not establish when a venue, exchange, Treasury, Federal Reserve, issuer, data vendor or publisher first made its data available. Nor does a retrospective adjusted-close download reproduce as-known corporate-action vintages. The Phase I event/economic risk engine requires *three independent classes of proof*:

1. Exact source bytes plus stable source identity, secure retrieval timing and deterministic SHA256.
2. Original publisher/quote announcement or source revision first-publication time, corroborated with independently reviewable source records and timezone conventions.
3. Commercial permission and institutional-model approval by authorized, attributable human reviewers.

The source review worklist currently holds required evidence slots for flagged security-price outliers, duplicated FX quotes and event-factor hypotheses. The new intake CLI validates **class 1 only**, checks basic temporal consistency for claims in class 2, and **never grants class 2 or class 3 approvals**. A claimed first-publication timestamp in a user-supplied JSON file is not automatically authentic.

## Local intake using original authorized bytes

With an original provider source file lawfully obtained and retained in a controlled local directory, make a sidecar JSON manifest. Example below contains only illustrative, non-real identifiers and must not be submitted as financial evidence without matching authentic payload bytes.

    {
      "source_family": "treasury_par_yields",
      "source_record_id": "DGS2:DATE:PROVIDER_REVISION_ID",
      "source_uri": "https://example.test/official/series",
      "payload_path": "source-data.bin",
      "payload_sha256": "<actual lowercase SHA256 of original bytes>",
      "capture_received_at": "2026-10-25T17:00:00Z",
      "warehouse_registered_at": "2026-10-25T17:10:00Z",
      "provider_published_at": null,
      "source_observation_date": "2026-10-23",
      "source_version": "not-yet-source-verified"
    }

Then use:

    python lab/phase1_original_source_packet_integrity.py --packet /secure/sidecar.json --root /secure/original-bytes

The script checks:

- Exact 16-family source allowlist, source record identity format, required/optional metadata schema and no approval flags accepted from the user sidecar.
- Bounded local source file inside its configured root, no absolute paths, traversal, external symlink or empty/oversized contents.
- Full SHA256 over the actual bytes compared with the sidecar hash (not hashing a URL, date, filename or revised warehouse value).
- Explicit timezone-aware receipt/registration/publication/revision claims and physically possible ordering. Source observation date is kept separate from provider publication.
- Credentials forbidden in source URLs and scrubbed query values in output.
- Stable packet identity for evidence reconciliation, no database writes, no source payload echoed, no outbound requests and no claims of validated publisher first-availability.

The output is research-only evidence of **checksum-vs-byte correspondence**. Even with a passing intake packet, flags for provider clock verification, first-available-to-market time, original publisher authenticity, licensing, reviewer approval and institutional risk use all remain FALSE. The script does not establish whether supplied bytes actually came from the named publisher; that requires an attributable, independently reviewable archival source chain.

## Independent human evidentiary acceptance (not automated)

An external steward must match packet_id and byte digest to the intended issuer/provider original record and preserve immutable original response bytes, vendor document/certificate or signed archive assertion, original revision/first-published time, named retrieval method, ticker or permanent issuer master and entitlement terms. Store reviewer and independent second reviewer identities and dated signatures separately from ingestion.

For event-to-factor hypotheses, also preserve pre-event consensus vintages, actual provider market quote publication timestamps, signed economic transmission rationale and independent holdout model approval. For security betas, prove original price adjustments, split/dividend vintages, permanent identifiers and rights before any purported point-in-time response fit.

**A passing cryptographic hash test never makes a vendor quote executable, validates a probability-surprise methodology, proves tradable as-known information, or grants redistribution rights.**

## Acceptance roadmap

- Collect actual source bytes through authorized channels; do not import proprietary raw bytes into the public GitHub repository, PR descriptions or chat.
- Run local packet integrity on each real archived version; quarantine malformed/counterfeit packets without overwriting earlier versions.
- Require independent provider-time/vintage acceptance and reviewer provenance with signatures. The existing 16-family warehouse gap and external rights gates remain blocked until that happens.
- Link accepted records through a separately reviewed, versioned mapping to existing factor observations, security price revisions and original event quote captures. Never substitute historical HTTP receipt times for source first-publication.
- Recompute warehouse-as-of and genuinely as-known research panels only after original-vintage inputs are available and approved. Re-run all chronological holdouts, uncertainty screens, beta/stability diagnostics and independent release-gate checks. No retroactive approval flags.

**Engineering limitations:** This patch creates no licensed source feed, no provider payload archive, no database ingestion of real source files and no model signoff. The two version-2 MotherDuck Flights remain unexecuted until compute becomes available or an authorized alternative run path is used.

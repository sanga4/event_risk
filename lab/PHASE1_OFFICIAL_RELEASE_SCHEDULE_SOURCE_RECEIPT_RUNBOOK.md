# Phase I — Original-source release SCHEDULE intake, not published economic vintages

**As of October 26, 2026 UTC.** The highest-priority missing institutional source dataset is `lab_source_release_vintages_v1`, with **12 required fields missing**. Its contractual fields include `release_published_at`, `first_publicly_available_at`, `reported_value`, `revision_id`, `source_payload_sha256` and `independent_replay_verified`. A schedule alone cannot establish actual publisher first availability or the released numeric value.

## Verified source access and boundary

- **BLS** offers an official `bls.ics` release-date subscription and publishes scheduled economic releases, but the actual MotherDuck read-only official calendar request returned **HTTP 403**. Research Flight `5fcce0ca-9f36-4078-9e89-aa54a2f4a5ea` run #1 exited nonzero. We do not bypass its bot/access policy or invent the inaccessible data.
- **BEA** has an official `https://www.bea.gov/news/schedule/` page. Read-only MotherDuck Flight `f91c84c0-5fd4-4527-95bb-18740b480bef` run #1 SUCCEEDED with HTTP **200**, **71,485** authentic response bytes and original SHA256 `4ab69b7cd50eee2994f8564f81cbd41001c09a6037e794e72ee6fb7bb92a2a48`. A second read-only Flight `9607af8e-63a6-4172-9a62-790ea13a4e8d` run #1 independently found the real `table#release-schedule-table`, a `Year 2026` header, and schedule rows with exact date/time, release type and title, including GDP (Advance Estimate), PCE and international trade.
- These scheduled times use the publisher's **U.S. Eastern calendar convention**; the parser uses `America/New_York` to convert correctly across daylight-saving changes, rather than assuming year-round fixed UTC-5. See [BEA release schedule](https://www.bea.gov/news/schedule/).

## Implementation

`lab/phase1_bea_official_release_schedule_receipt.py` is a source-pinned, default **read-only** producer with exact official HTTPS URL allowlist, status/content-type/no-redirect/byte-length checks and strict parser guards on real source table/year/time/duplicate events. It archives original full response HTML bytes and SHA256 in append-only **research-source calendar schedule** tables if and only if a deliberately authorized `--append-research` run uses `LAB_RESEARCH_WRITE_ACK=confirmed`:

- `lab_bea_schedule_receipt_builds_v1`: actual HTTP received-at, original raw HTML BLOB, SHA256, parser source Git commit, 2026 schedule year, parsed entry count, source append time and **five FALSE** first-publication/data-consensus/rights/model approval fields.
- `lab_bea_schedule_events_v1`: one entry per scheduled news/data announcement with source event identity SHA256, local date and timezone-correct scheduled UTC time, title/type, original packet/source received-at reference. `actual_published_at` and `reported_numeric_value` remain **NULL** and all approval/certification flags remain **FALSE**.

An official *future schedule displayed on the page when we retrieved it* is not historical evidence of what a trader knew at earlier times. Scheduled announcement time is **not** the actual release-published-at timestamp; neither a reported macro number nor a market surprise is supplied by a calendar. The script does **not** create or fill the required institutionally certified `lab_source_release_vintages_v1` dataset.

## Execution protocol

Read-only example:

```bash
LAB_RESEARCH_SCOPE=internal-only LAB_PIPELINE_COMMIT=<reviewed-full-40-hex-commit> \
  python lab/phase1_bea_official_release_schedule_receipt.py
```

The supported `--append-research` mode is a distinct deliberate source-research approval and requires a secured MotherDuck credential and `LAB_RESEARCH_WRITE_ACK=confirmed`. Source packet acceptance must be verified independently afterward by recomputing original HTML SHA, parsed per-event schedule identities, UTC date conversion, raw packet counts and all false approval flags. No timer or automatic schedule is enabled. A static runbook or source-controlled script does NOT establish a loaded source packet or a passing independent post-write acceptance audit.

## Why Phase I remains blocked

The latest real institutional field audit has 16 contracts, 274 field rules, 255 mandatory fields, **135 missing, 1 unpopulated and 255 uncertified**. The latest automatic release assessment has **25 PASS / 29 BLOCK of 54** plus 4 manual, production FALSE. Four prospective capture dates and two prospective factor observation dates fall far below the minimum 60 and 30 research screens. Needed next: actual BEA/BLS/Census provider publication and revision history with first-known instants, real reported economic values and pre-announcement consensus, historical issuer action publication vintages, rights and genuine forward source captures. The calendar provides future collection time structure but never clears original economic surprise validation or license approval.

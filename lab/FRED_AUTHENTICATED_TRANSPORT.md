# Authenticated official FRED macro research transport

Phase I producer: lab/phase1_fred_macro_research.py v1.1.0.

The old unauthenticated graph CSV endpoint at fred.stlouisfed.org repeatedly timed out from MotherDuck; the third failed run was on October 25, 2026 UTC. Do not keep retrying that endpoint and do not interpret those failures as successfully loaded data.

The revised producer requires a registered official FRED API key supplied privately as a MotherDuck Flight secret (runtime FRED_API_KEY or api_secret_FRED_API_KEY), together with the existing LAB_RESEARCH_SCOPE=internal-only and LAB_ALLOW_FRED_RESEARCH=true guards. It calls the documented official observations JSON API at api.stlouisfed.org, validates descending/duplicate/realtime metadata, source-native values and per-series boundaries, and stores only a redacted safe URL and response SHA-256.

**No API key is supplied or committed by this change.** No MotherDuck FRED ingestion is claimed complete. Source API keys cannot appear in persisted source_url columns, run logs, exception messages or GitHub files. Negative auth and malicious response tests are run offline; after an authorized secret has been provided, complete a credentialed Flight execution, verify six source series, native observation counts and idempotent rerun, and then rebuild the institutional source inventory.

The existing v1 warehouse columns source_csv_url and source_csv_sha256 are *legacy column labels*: for v1.1.0 the SHA is over the original FRED JSON response and the URL references the JSON API without api_key. Future schema v2 should rename these to source_payload_uri and source_payload_sha256 before any formal data contract approval.

FRED JSON real-time start/end fields are **observation vintage dates, not hour/minute first-publication timestamps**. Original source release times, revisions, licensed institutional reuse, event surprises, signed model approval, beta production use and source first-known-at claims remain FALSE or NULL. Successfully downloading revised history does not make it a certified historical PIT backtest.

The official API requires a registered key: https://fred.stlouisfed.org/docs/api/fred/series_observations.html . Never paste credentials into chat or commit them to the repository.

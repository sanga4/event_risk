# Protected research API — corrected event–factor v3.1

Two new authenticated endpoints are introduced in `lab/api.py`:

- `GET /v1/research/v3_1/summary`: aggregate versioned source alignment repair evidence; no vendor source prices, factor-observation return arrays or portfolio betas in the response
- `GET /v1/research/v3_1/panel`: only `mode=retrospective&research_use=true` with operator-controlled `LAB_ENABLE_RETROSPECTIVE_READ=true`. Requires `X-API-Key`, valid `LAB_DB`, a scoped `MOTHERDUCK_TOKEN`, and owner-confirmed `LAB_DATA_RIGHTS_ACK`. Inputs for proposition, factor and event dates are all bound parameters; row pages are bounded to 100

Legacy `/v1/research/v3/panel` remains backward-compatible and authenticated but now explicitly warns that its source factor observation dates/carry labels are semantically unreconciled, and recommends `v3_1`. No route may make a first-provider-publication timestamp, causal mapping, historically tradable signal, licensed vendor source redistribution or institutional-beta approval claim.

The corrected v3.1 panel is read from `lab_event_factor_panel_v3_1_latest` to avoid pooling append-only historical replay builds. SQL requires `reconciled_to_existing_factor_hash_and_run=TRUE`, `original_publication_pit_independently_certified=FALSE` and `institutional_event_factor_approved=FALSE`. The new summary endpoint hard-fails if the manifest is missing or has any unexpected rights/model/PIT-release approval.

Both endpoints depend on the existing `require_api_key` server-side guard and retain `Cache-Control: no-store`. The Railway service without configured credentials correctly returns 401/503 and must not be opened to public source access by default.

This API update is a **data integrity access improvement**, not evidence that the licensed historical event-to-financial-factor methodology is institutionally approved.

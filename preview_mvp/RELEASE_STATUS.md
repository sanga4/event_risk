# Preview MVP analyst acceptance ledger — independent of Phase I

Last engineering review: October 26, 2026. This ledger is separate from institutional Phase I governance checks. It must NEVER change the original Phase I release approvals.

| Gate | State | Verifiable test / dependency |
| --- | --- | --- |
| Separate app and deployment root | PASS | Railway project eventrisk-preview-mvp, service preview-mvp-analyst, source root /preview_mvp |
| Original-site visual consistency | BUILT / CLIENT QA PENDING | Original base CSS, central graph, left search, right detail, light analyst desk |
| Full public security reference catalog | PASS | 543 public original-repository security references; endpoint /api/v1/catalog |
| Full qualitative factor reference catalog | PASS | 108 factor definitions; 18 source-observed factor series is a separate warehouse quantity |
| Economic transmission catalogue | PASS AS HYPOTHESES | 22 descriptive channel mechanisms; no causal effect sizes |
| Original exposure research priors | PASS AS NONCAUSAL PRIORS | Source CSV replayed qualitative relevance weights, 0–1 range |
| Dated broad research warehouse coverage audit | PASS | /api/v1/inventory states 4,907 question nodes, 169,996 versioned graph edges, 12,764 factor observations |
| Public navigation and research workbench | BUILT, HTTP LOCAL VERIFIED | / and /lab, graph-to-case pathway, print and CSV |
| Funding regression diagnostics contract | PASS, ENTITLEMENT REQUIRED | Reads actual source 48-security 96-fit latest model family and independent familywise models |
| Actual regression values loaded from deployed Railway | BLOCKED | New read-only MotherDuck token and analyst key absent from Preview MVP Railway |
| Original factor source history contract | PASS, ENTITLEMENT REQUIRED | /api/v1/research/factor-series with original dated source and availability warnings |
| Historical factor series loaded from deployed Railway | BLOCKED | New token, analyst key and derived research distribution permission absent |
| All real source event questions in UI | BLOCKED ON REDISPLAY RIGHTS | Bounded auth-protected paginated warehouse graph question search; 4,907 distinct question nodes in source |
| Retractions honored in live neighbor queries | PASS, QUERY DESIGN VERIFIED | Latest graph op=assert wins; retracted old edge/node version not shown |
| Independent warehouse connection success telemetry | BUILT / NO SUCCESS YET | /api/v1/runtime distinguishes credential presence from actual last successful authenticated SELECT |
| Real analyst accounts with SSO | NOT BUILT | Existing shared key is a temporary beta credential; per-user SSO and audit identity required for broad use |
| Source redistribution rights | BLOCKED | Independent source license/data contract review; never flip *_APPROVED flags without valid review |
| Office Excel catalog/graph/formula add-in | CODE/HTTP TESTED | /excel/manifest.xml and taskpane imports ER_ sheets with COUNTIFS/SUMIFS |
| Actual Excel sideload and write acceptance | NOT YET VERIFIED | Requires an actual Excel host session with analyst-granted Office add-in rights |
| Request boundedness and basic abuse control | PASS FOR SINGLE REPLICA | Allowlisted SQL, parameterized ids/limits, in-process 90 source SELECTs / 60 seconds; replace with distributed limits when scaled |
| Point-in-time source and verified event effect | NOT APPROVED | Incomplete original quote clocks, issuer rights, consensus vintages, independent causal model evidence |
| Institutional Phase I release | SEPARATE / UNCHANGED | Do not promote this research beta or modify original research governance flags |

## Exact next operational handoff

1. In the *new* Railway project only, provision a MotherDuck account/service credential with SELECT rights limited to approved Preview MVP research-safe views, and a distinct strong PREVIEW_MVP_ANALYST_KEY.
2. Confirm /api/v1/runtime reports configured true but tested false *before* first actual query; enter issued analyst key in the Preview MVP and run /api/v1/research/coverage. Tested becomes true after successful SELECT.
3. Independently review rights for any real provider question display before enabling PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED, and for regression/factor series before PREVIEW_MVP_DERIVED_RESEARCH_APPROVED. A boolean acknowledgement is not itself a legal entitlement.
4. For entitled accounts, validate event search pagination against the active graph operation versions, factor observed dates, full-and-trimmed regression values, Holm adjustment, error states, and CSV export.
5. Sideload the new Excel manifest into actual Excel, test reference sheet imports, formulas, analyst rights gates, model/series import and non-approved labels. Document timestamp and client version.
6. For multi-analyst release, replace the shared access key with SSO, analyst identity, server-side authorization, distributed request rate limits, monitored query budgets and source/provenance audit logs.

**Do not represent the beta as a real-time, comprehensive all-prediction-markets or approved event-impact model while any source coverage, provider quote age, or license gate remains blocked.**

Public site: https://preview-mvp-analyst-production.up.railway.app/
Draft Preview MVP review: https://github.com/sanga4/event_risk/pull/75
Phase I main branch untouched.

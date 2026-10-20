# Isolated Event Risk Analyst Excel

Source is a separate development branch in the personal fork of `huimarco/event_risk`.
It retains the existing API / web explorer / graph code unchanged.

## Exactly requested formulas

- `=ER.PROB(id)`: latest probability of a proposition or a question's headline rung
- `=ER.FIELD(id,"volume")`: current 24-hour trading volume from the existing API
- `=ER.HISTORY(id,start,end)`: probability series; spills date/probability/number of markets
- `=ER.ASKNOWN(id,at)`: probability at `at` using `as_of=at&known_as_of=at`
- `=ER.EVENT(id,"title")`: title from the existing question/proposition API
- `=ER.SEARCH("Taiwan")`: matching question IDs, titles, probability and headline event IDs
- `=ER.UPDATED(id)`: latest actual source-observation time, as Excel date serial

The other original functions (CHANGE, NAME, QUESTIONS, RUNGS, PROPOSITIONS, EXPOSURES, SCAN) remain registered as `ER.*`.
Use real proposition or `q:...` question IDs from the sidebar; `event_123` is a placeholder, not an ID format in this API.

## Sidebar

Theme search lists questions. Selecting one fills the lower question search and shows its
attached event propositions (rungs). The lower search can also select questions independently.
Click an event to write a live four-cell watchlist row. Portfolio scan, refresh, API key, and
advanced formula help remain in place.

## Independent deployment

This feature branch provides a separate Node service with its own Excel manifest ID
`15fbb7e3-86bf-433a-9a85-f2c7c8cf0a15`. Start with `npm start`.
- `PUBLIC_ORIGIN`: this new service's public HTTPS origin (e.g. https://new-host.up.railway.app).
- `EVENTRISK_UPSTREAM`: existing read-only API, default `https://geo-risk-api-production.up.railway.app`.
- `PORT`: assigned by Railway.

The Excel server proxies existing read-only API endpoints, so the add-in is fully isolated
from the original Excel deployment **but currently shares the original data API and warehouse**.
To make the data backend itself independent later, provision database credentials and a separate
API service; do not copy secrets from your friend's infrastructure without permission.

Install from `/excel/manifest.xml` or `/excel/install.cmd` (subject to Office and
corporate policy). Desktop Excel sideloading has not been accepted-tested here.

## Checks

`npm test` runs built-in Node unit checks of all seven functions, the Office metadata,
the taskpane script and the standalone HTTP server. CI runs this on the isolated branch.
These tests do **not** substitute for Windows Microsoft 365 sideloading / calculation tests.

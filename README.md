# pred_market_risk

Geopolitical event-risk data from prediction markets (Kalshi + Polymarket): probability history,
a point-in-time knowledge graph linking markets → propositions → entities → securities, and an API.

## Pipeline

| Script | Workflow (GitHub Actions) | Schedule | Writes |
|---|---|---|---|
| `collector.py` + `graph_build.py` | `collect_markets_and_update_graph` | every 15 min | `market_snapshots` (source=`realtime`), `market_versions`; graph only when markets change |
| `prices.py` | `get_security_prices` | weekdays 22:30 UTC | `security_prices` (Yahoo, research use only) |
| `backfill.py` | `backfill_market_history` | manual, one-time | `market_snapshots` (source=`backfill`) |
| `graph_build.py --refresh …` | `refresh_wikipedia_facts` | manual | re-fetched Wikipedia/Wikidata facts, then graph |
| `securities.py` | — (run locally) | after index rebalances | `securities.csv` (S&P 500 from Wikipedia; review and commit) |
| `backtest.py` | — (run locally) | after graph or price changes | nothing; prints whether exposure priors predict returns when odds jump |

All data lives in MotherDuck: put `MOTHERDUCK_TOKEN` in `.env` (copy `.env.example`; git-ignored) or the environment. `DB` defaults to `md:geo_odds`.

## API

```
pip install -r requirements.txt
uvicorn api:app      # reads .env; explorer at http://localhost:8000, docs at /docs
```

```
GET  /propositions?entity=country:TW&sort=move          # what moved, filtered by entity
GET  /propositions/{id}                                 # markets, entities, logical links
GET  /propositions/{id}/history?interval=1d&start=...   # blended probability series
GET  /securities/TSM/exposures?sort=risk                # propositions a security is exposed to, signed
GET  /markets?status=unparsed                           # match review: unmatched / unparsed / linked / merged
GET  /markets/{id}                                      # signature, parser issues, rejected candidates
```

The same server hosts an interactive explorer at `/` (`web/index.html`): browse propositions
(sorted by 24h move), entities, securities and markets (the **Markets** tab lists markets that
weren't matched, with their parsed signature and why each near miss was rejected); click anything to see its neighbourhood as a
network and its details (prices, markets and rules, Wikipedia description, exposures); set
"As of" to view the graph and prices at any past moment.

The explorer's **API** tab documents every endpoint with examples; `/docs` is the interactive reference.

Every read accepts `as_of` (state of the world at T) and `known_as_of` (what the graph knew at T);
set both to T for a point-in-time, backtest-safe view. Set `API_KEYS` to require `X-API-Key`.

## Excel add-in — EventRisk Analyst

The fork serves a Microsoft Office.js Excel add-in under `/excel/`. This version
has a new manifest ID and the exact `ER` namespace, so it can coexist with the
original add-in rather than overwrite its `EVENTRISK.*` formulas.

Seven formulas (real event IDs have a `prop:` prefix; `event_123` is only a
placeholder, not an ID in the graph):

```excel
=ER.PROB("prop:venue:id")                      latest event probability
=ER.FIELD("prop:venue:id","volume")            most recent 24-hour market volume
=ER.HISTORY("prop:venue:id",A2,B2)             restated historical probability table
=ER.ASKNOWN("prop:venue:id",A2)                probability known at A2
=ER.EVENT("prop:venue:id","title")            event-contract question text
=ER.SEARCH("Taiwan")                          event IDs and prices matching a topic
=ER.UPDATED("prop:venue:id")                  latest underlying market-observation time
```

`q:...` identifiers refer to broad questions grouping multiple event contracts.
`mkt:...` selects one venue-native market for ER.PROB, ER.FIELD and ER.UPDATED.
ER.PROB on `prop:` returns the API's blend **only for validated same_as market
mappings**. ER.FIELD with `volume` returns `volume_24h`. ER.UPDATED returns
an Excel serial date/time, so format the cell as `yyyy-mm-dd hh:mm`.

ER.HISTORY is a **restated**, not as-known, time series: it follows the currently
selected contract mapping. ER.ASKNOWN sends both `as_of` and `known_as_of`
set to the selected date and uses the API's seven-day market-price freshness window.
The remaining helper formulas are still registered: `ER.CHANGE`, `ER.NAME`,
`ER.QUESTIONS`, `ER.RUNGS`, `ER.PROPOSITIONS` and `ER.EXPOSURES`.

The sidebar has **Search a theme** (Taiwan → questions) followed by **Search for
questions / Events**. Clicking a question populates its linked event contracts
below. Searching the lower box directly finds matching questions and their events.
Click an event to insert its ID, live title, probability and source update time
into Excel. Refresh, API-key controls and formula reference remain. The retired holdings-analysis worksheet action is not present in this fork.

### Install and iterate

1. Deploy **this fork** (`sanga4/event_risk`) to a *separate* Railway HTTPS
   service. The existing `geo-risk-api` still runs the upstream repo and will
   not reflect this fork's changes.
2. Download `https://YOUR-NEW-DOMAIN/excel/manifest.xml`. On Windows where
   policies permit, download `https://YOUR-NEW-DOMAIN/excel/install.cmd` and
   run it. Otherwise sideload the XML via the Office Add-ins interface; in
   corporate Excel, administrator approval may be required.
3. Restart Excel, open **EventRisk Analyst** on Home, and try
   `=ER.SEARCH("Taiwan")`. Enter your server API key in the pane if needed.
4. For every change: new GitHub feature branch → automated tests (including
   `node --test tests/er_analyst.test.cjs`) → separate Railway test service →
   real Excel workbook test → merge to main when accepted.

Local development requires HTTPS. Install Office dev certs with
`npx office-addin-dev-certs install`, then run
`uvicorn api:app --ssl-keyfile ~/.office-addin-dev-certs/localhost.key --ssl-certfile ~/.office-addin-dev-certs/localhost.crt`.
Sideload `https://localhost:8000/excel/manifest.xml`.

## Deploying (Railway)

The API and explorer are one web service; GitHub Actions keeps collecting data into MotherDuck.
`railway.json` (start command + health check), `Procfile` (same command, for other hosts),
`.python-version` and the pinned `requirements.txt` are all Railway needs.

1. railway.com → sign in with GitHub → **New Project → Deploy from GitHub repo** → this repo.
2. Service → **Variables**: `MOTHERDUCK_TOKEN` (a read-only token is safest for a public
   service); optionally `API_KEYS=key1,key2` to require `X-API-Key` on data calls.
3. Service → **Settings → Networking → Generate Domain**. The explorer is at `/`, docs at `/docs`.

Every push to `main` redeploys.

## Scope

Every geopolitical market: Polymarket's `geopolitics` tag, plus Kalshi World/Politics markets that
involve a foreign state actor — a country other than the US, or a person/organisation belonging to
one, per Wikidata ("Will Trump visit China?" in, "Will the Senate confirm…?" out).

## Refreshing cached facts

Wikipedia/Wikidata lookups are fetched once and cached, so the routine refresh never repeats them.
Refresh them manually to pick up real-world changes. A refresh re-fetches, appends the new values
(old ones stay as history), and rebuilds the graph — only facts that actually changed are rewritten.

**Wikidata refresh — monthly.** Entity facts: type, parent country, statements such as *head of
state* or *citizen of* (e.g. a new leader). Takes a few minutes.

```bash
python graph_build.py --refresh wikidata
```

or GitHub: **Actions → refresh_wikipedia_facts → Run workflow → wikidata**.

**Relatedness refresh — yearly.** Wikipedia co-occurrence counts behind entity ↔ entity link
strengths. Slow (around an hour at full scope).

```bash
python graph_build.py --refresh relatedness
```

or GitHub: **Actions → refresh_wikipedia_facts → Run workflow → relatedness**.

The terminal commands need `MOTHERDUCK_TOKEN` in `.env`; the workflow uses the repository secret.

## How markets become propositions

`matching.py` parses every market into a contract signature — action, actors/targets, time window,
threshold, conditions — from venue fields and the venues' templated rules text, then compares them
field by field: `same_as` (merged, prices blended), `near_equivalent` (linked, never blended),
`implies` (A ⇒ B), or rejected with a reason. Prices are the final check: markets that the text
says are identical but trade more than 10 points apart are not merged. Within one venue the
operative rules are compared as well (names in the rules that neither question has mean different
bets), and a negated question ("agrees *not* to join", "military action *ends*") never matches the
plain one.

## Direction and size of impact

Each `involves` edge carries the entity's role in the contract (actor / target / party / concept)
and what YES means for it: `matching.EFFECTS` maps each action to a channel (conflict, trade,
sanctions, instability, diplomacy), a severity and a direction for target and actor; negated
questions flip it. `seeds/channel_signs.csv` lists the industries that *gain* from escalation on
a channel (defense, oil producers, fertilizers); every other exposure suffers with its entity.
`/securities/{t}/exposures` sums over every path: `impact` = Σ sign × severity × role weight ×
pass-through × exposure weight (> 0: expected to rise if the event happens), `score` = relevance,
`risk` = |impact| × √(p(1−p)). These are priors in graph units; `python backtest.py` checks them
against abnormal returns on days odds jump (magnitude within each security, direction hit rate,
calibration slope). First run (2026-10-18, 62 priced securities, daily data): direction at chance
(~50%), so the priors are not yet validated.

## Curating the graph

- `seeds/match_overrides.csv` — human overrides of the matcher (`same_as`, `near_equivalent`,
  `implies`, `different`); always win. Review queue: `python graph_build.py --review > review.csv`.
- `seeds/exposures.csv` — entity → security exposures, keyed by Wikidata id. Hand-written;
  current weights are analyst placeholders, not sourced data.
- `seeds/channel_signs.csv` — which sub-industries / tickers gain (−1) rather than suffer from an
  adverse event on a channel. Hand-written priors, like exposures.

## How entities are found and connected

`entities.py` regenerates the entity list from the markets on every build: phrases in market
titles are linked to Wikipedia articles, Wikidata supplies each entity's type and parent country,
and entities are connected by Wikidata statements and by normalized co-occurrence on Wikipedia
(how many articles mention both, relative to each alone). Lookups are cached in MotherDuck.

# Factors — qualitative event mapping

**Purpose.** Give institutional analysts a stable, auditable relationship between a
prediction-market *question* (and its underlying propositions) and recognized
risk-model **Factors**, without forecasting returns or estimating sensitivities.
This is not a quantitative multi-factor risk engine and is not a substitute for
licensed vendor models, portfolio risk numbers, or analyst approval.

## Architecture and data boundaries

The existing event pipeline is unchanged:

    market -> proposition -> question -> entity -> security

The **Factors** layer runs alongside it:

    graph question + action + linked typed entities
      -> eligible qualitative economic mechanisms
      -> governed factor catalog
      -> established deterministic links / separate review candidates
      -> optional analyst approval, rejection or downgrade

- [seeds/factors.json](seeds/factors.json): currently **108 distinct factors**, with
  stable IDs, model and universe labels, definitions and methodology references.
  Covers the five Fama–French US/developed-ex-US/emerging-market factors,
  momentum and other styles, equity countries, industries, rates, credit,
  FX, commodities, inflation, volatility, liquidity and cross-asset styles.
- [factors.py](factors.py): standard-library Python mapper. Runs locally with
  `python factors.py --demo` or `python factors.py --family equity_style`. Imports the
  existing contract-action parser in `matching.py`; does not connect to any DB,
  use network access, or estimate beta coefficients.
- [seeds/factor_overrides.json](seeds/factor_overrides.json): initially empty
  review register for documented analyst approvals, rejections and downgrades.
- The API reads existing event-graph objects as the *input*. **There are no
  new MotherDuck tables or database writes for factor mappings**. The
  original graph and probability APIs still use their preexisting data source.

## What a factor is

A factor is an identifiable risk-model quantity or defined portfolio return
spread, with a stated model and universe, not a generic keyword tag.

Examples:

- `FF5.US.HML` = a U.S. Fama–French research value spread; not the
  same as `STYLE.GLOBAL.GROWTH` and not a security value score.
- `STYLE.US.UMD` = research momentum return-spread factor.
- `EQUITY.COUNTRY.TW` = Taiwan equity country risk category.
- `EQUITY.INDUSTRY.SEMICONDUCTORS` = semiconductor equity industry.
- `FX.USD_TWD` = USD/TWD foreign-exchange factor.
- `RATES.US_2Y` = U.S. short-dated Treasury yield factor.
- `COMMODITY.BRENT` = Brent crude price factor.

Catalog entries provide taxonomy and definitions. They do **not** imply that
we can calculate a licensed vendor factor return from these labels. Before
using the output in a production vendor risk-model workflow, identify the
exact vendor factor identifier, portfolio construction, rebalance/roll
convention, model version, benchmark, and necessary redistribution license.

## Boolean methodology

Let a question be represented by its parsed signature and graph context:

    C_q = {event action, named entities, geography, operative terms, time window}

The process identifies eligible transmission mechanisms M (e.g. sanctions,
maritime disruption, commodity supply, monetary policy). For an individual
factor f and mechanism m:

    A[q,m] = event q explicitly activates mechanism m
    B[m,f] = mechanism m can connect to factor f
    G[q,m,f] = specific entity, region, instrument and terms pass the rule's gates

The accepted qualitative link is:

    L[q,f] = OR over m of (A[q,m] AND B[m,f] AND G[q,m,f])

These are **logical predicates, not numerical weights**. The engine never
multiplies a question probability by a factor loading, predicts the sign of
returns, generates an estimated beta, or calculates a portfolio factor exposure.

Actual implementation is a versioned deterministic rule family per eligible
action and explicit title/entity context. It outputs a traceable `rule_id`,
`mechanism`, `evidence` and `reason`. No vector embeddings, language
models or open-ended keyword association silently create accepted links.

### False-positive controls

- A conflict involving Taiwan can have accepted Taiwan country and USD/TWD
  links. Semiconductor exposure is a **review candidate** if no contract term
  explicitly mentions chips, rather than an automatic chip-industry assertion.
- An explicit semiconductor export ban qualifies for the semiconductor
  industry, without silently assigning *all* Chinese industry factors.
- A Strait of Hormuz closure passes a maritime-route gate for freight and
  oil transmission; an unnamed blockade does **not** automatically map oil.
- A Federal Reserve rate-decision question can qualify for U.S. policy and
  short-end rates, but *not* automatically for Fama–French HML or SMB.
- CPI outcomes and inflation breakeven expectations are different quantities.
  CPI mentions create **review candidates** for expectations factors.
- A general geopolitical conflict does not imply exposure to return spreads
  for value, size, profitability, investment, low volatility or momentum.
  Such relative-style effects require explicit, auditable differential
  mechanisms and independent approval.

Accepted links are **rule-supported qualitative relevance**, not
human-verified economic forecasts. Review candidates are never mixed into
accepted results unless a source-controlled review approves them. Failure to
map is a deliberate abstention, not a claim of zero factor risk.

### Question-first inheritance

The existing graph groups propositions differing only by deadline or
threshold into one question. Common factors attach to that question and
are inherited by propositions. When event-specific terms justify an
exception, a reviewer may add a `proposition_id`-scoped override. We do
not multiply the number of links by the number of rungs or estimate a new
beta for each deadline.

## Human review and governance

Edit `seeds/factor_overrides.json` in a **reviewed GitHub pull request**.
Every non-empty entry must contain:

    id             immutable decision ID
    question_id    canonical q:... question
    proposition_id optional prop:... rung-specific scope
    factor_id      a validated catalog ID
    decision       approve | reject | review
    mechanism      documented causal / transmission channel
    rationale      why the relationship is or is not defensible
    evidence       source citation, research memo, operative contract term
    reviewer       independently accountable person/team identifier
    reviewed_at    timezone-aware ISO timestamp

Sample schema (illustration only; not a real approval):

```json
{
  "id": "RISKREVIEW-000001",
  "question_id": "q:your-real-question",
  "proposition_id": "prop:your-particular-contract",
  "factor_id": "EQUITY.INDUSTRY.SEMICONDUCTORS",
  "decision": "review",
  "mechanism": "possible_chip_supply_chain",
  "rationale": "Needs evidence that the specific contract disrupts chip production",
  "evidence": "Research memo DRAFT-2026-001; event contract text",
  "reviewer": "risk-committee",
  "reviewed_at": "2026-10-20T12:00:00Z"
}
```

Rules validate IDs, decisions, evidence, reviewers, timestamps and duplication.
An approval adds a record with `source_controlled_analyst_review` provenance;
a rejection removes the link and exposes an audit exclusion; `review` downgrades
a previously accepted rule link to a separate candidate. Rules themselves
have no numerical severity, signs or risk weights.

Do not store private credentials or unsupported financial estimates in
catalog, overrides or Excel workbooks.

### Temporal integrity

The event graph supports bitemporal `as_of` and `known_as_of` queries.
The factor logic is code and the version-controlled catalog, not a table
of historical adjudications. Accordingly, historical endpoints **apply
the currently deployed rules and review file to the selected historical
event-graph snapshot**. They are **not an as-known history of past mapping
decisions**. The responses state catalog, rule and review versions.

For audit-grade reconstruction of a historic mapping decision, pin the
specific Git commit/image carrying `factors.py`, `factors.json` and
`factor_overrides.json` and use the same event graph snapshot. Never
silently relabel today's rules as yesterday's human judgment.

## API

- `GET /factors?family=&q=` — complete filtered factor catalog; no DB read.
- `GET /factors/{factor_id}` — one factor definition.
- `GET /questions/{question_id}/factors` — mapped and review factors, traces.
- `GET /propositions/{proposition_id}/factors` — inherited question
  mapping, with optional proposition-specific analyst overrides.
- `GET /factors/{factor_id}/questions?include_review=false&limit=100` —
  reverse lookup from factor to linked questions. Uses the existing event
  graph snapshot but no factor tables. The default excludes review candidates.
- `GET /graph/{node_id}?include_factors=true` — optional *virtual*
  factor nodes attached to the selected question/proposition. Graph edges
  are unweighted and are never persisted to `graph_edges`.

Existing API authentication (`X-API-Key` when configured) continues to apply
to factor endpoints. The web and Excel frontends use the same credentials
and the existing read-only request helper.

## Excel and website

The **EventRisk Analyst** sidebar now shows **Factors** immediately below
the selected Events list. Clicking a theme question loads factor links for
that question; clicking an event loads its inherited question factors.
The sidebar separates accepted mappings from *Review candidates* and
lets the analyst inspect the deterministic reason, evidence and rule ID.
It does not alter the seven existing `ER.*` formulas or the worksheet
event-insertion sequence.

The website includes a **Factors** catalog tab, factor metadata, reverse
question lookup, factor sections on questions/propositions, and an optional
Factor graph overlay. Factor nodes have a distinct shape and *no*
numerical edge weight; they never use the existing security-impact values.

## Tests and release gates

Pure-Python no-database QA:

```sh
python -m unittest discover -s tests -p 'test_factors.py' -v
python -m unittest discover -s tests -p 'test_factors_governance.py' -v
python factors.py --demo
```

API and client QA (requires the existing requirements plus `httpx==0.27.2`):

```sh
python -m unittest discover -s tests -p 'test_factors_api.py' -v
node --test tests/er_analyst.test.cjs tests/sidebar_analyst.test.cjs \
  tests/sidebar_factors.test.cjs tests/web_factors.test.cjs
```

CI also checks syntax, factor catalog schema, source-controlled reviews,
and that Portfolio Scan never returns. A *successful CI run is not a
real-market or native-Excel acceptance test*. Before institutional release,
deploy the fork to its own isolated HTTPS service, test live event IDs,
validate the API authentication policy and source freshness, and sideload
the manifest in a supported Excel client. Also obtain independent risk
review of mappings and clarify applicable factor-data licenses.

## Known limitations / prioritized follow-ups

1. Automated mappings have not been independently annotated for precision,
   recall and reviewer agreement on a representative event sample. CI
   verifies deterministic behavior on controlled positive/negative fixtures,
   not universal economic accuracy.
2. Current mapping rules are intentionally conservative; not every factor in
   the catalog has an automatic trigger. A large catalog does not imply
   exhaustive factor coverage.
3. The event graph's parsed question action and Wikipedia entity resolution
   can be incomplete; the mapper abstains rather than fabricate connections.
4. Some model factors are relative long/short spreads and cannot be inferred
   from a broad event's stock-market relevance.
5. Vendor factor-return series and security-level factor loadings are not
   obtained or reproduced; permission and construction requirements must
   be established before quantitative use.
6. Rule versions are maintained in source. Point-in-time review-decision
   reconstruction requires pinned historical code/artifacts, as above.

**References:** [Fama–French data library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
[MSCI factor research](https://www.msci.com/indexes/factor-indexes),
[BIS market-risk framework](https://www.bis.org/bcbs/publ/d457.htm).

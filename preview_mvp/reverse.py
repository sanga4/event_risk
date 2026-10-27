"""Permission-scoped reverse event discovery using existing versioned research graph.

All event identities and exposure edges are research hypotheses unless separately reviewed.
No quote is returned without the caller's explicit source redisplay entitlement.
"""
from __future__ import annotations

import re

_ALLOWED = {"security", "entity", "factor", "question", "proposition"}
_ID = re.compile(r"^[A-Za-z0-9:._=/-]{1,128}$")


def reverse_source(query, kind: str, node_id: str, limit: int = 40):
    """Return captured contract quotes reached from an entity/security/factor.

    Query uses the latest asserted graph edges, not the append-only raw history;
    contract prices remain distinct and are never aggregated into an 'event probability'.
    The caller must check analyst authentication AND source redisplay authorization.
    """
    if kind not in _ALLOWED or not _ID.fullmatch(node_id):
        raise ValueError("INVALID_REVERSE_LOOKUP")
    if kind == "security" and node_id.startswith("security:"):
        node_id = "sec:" + node_id.split(":", 1)[1]
    limit = max(1, min(75, int(limit)))

    edges = """WITH versioned AS (
        SELECT src_id,dst_id,edge_type,weight,confidence,provenance,op,
          row_number() OVER (
            PARTITION BY edge_id ORDER BY recorded_at DESC,run_id DESC
          ) AS version_no
        FROM main.graph_edges
        WHERE edge_type IN ('involves','exposure','relevant_to','rung_of')
    ), active AS (
        SELECT src_id,dst_id,edge_type,weight,confidence,provenance
        FROM versioned WHERE version_no=1 AND op='assert'
    ), candidates AS ("""

    if kind in ("security", "entity"):
        condition = ("JOIN active exp ON exp.edge_type='exposure' "
                     "AND exp.src_id=inv.dst_id AND exp.dst_id=? "
                     if kind == "security" else "")
        filt = "" if kind == "security" else "AND inv.dst_id=? "
        part = ("""SELECT DISTINCT inv.src_id AS proposition_id,
                       ru.dst_id AS question_id,
                       inv.dst_id AS matched_entity,
                       inv.confidence AS relation_confidence,
                       inv.provenance AS relation_provenance
                   FROM active inv """
                + condition
                + """LEFT JOIN active ru ON ru.edge_type='rung_of'
                       AND ru.src_id=inv.src_id
                   WHERE inv.edge_type='involves'
                       AND starts_with(inv.src_id,'prop:') """
                + filt)
    elif kind == "factor":
        part = """SELECT DISTINCT rung.src_id AS proposition_id,
                      rel.src_id AS question_id,
                      NULL AS matched_entity,
                      rel.confidence AS relation_confidence,
                      rel.provenance AS relation_provenance
                  FROM active rel JOIN active rung
                    ON rung.dst_id=rel.src_id AND rung.edge_type='rung_of'
                  WHERE rel.edge_type='relevant_to' AND rel.dst_id=?"""
    elif kind == "question":
        part = """SELECT rung.src_id AS proposition_id,
                      rung.dst_id AS question_id,
                      NULL AS matched_entity,
                      rung.confidence AS relation_confidence,
                      rung.provenance AS relation_provenance
                  FROM active rung WHERE rung.edge_type='rung_of'
                       AND rung.dst_id=?"""
    else:
        part = """SELECT ? AS proposition_id, NULL AS question_id,
                      NULL AS matched_entity, NULL AS relation_confidence,
                      NULL AS relation_provenance"""

    sql = edges + part + """), ranked AS (
       SELECT * FROM candidates ORDER BY proposition_id LIMIT 450
    ), named AS (
       SELECT node_id,name,node_type FROM (
          SELECT node_id,name,node_type,op,
                 row_number() OVER (
                    PARTITION BY node_id ORDER BY recorded_at DESC,run_id DESC
                 ) AS rn
          FROM main.graph_nodes
       ) WHERE rn=1 AND op='assert'
    )
    SELECT c.proposition_id,c.question_id,c.matched_entity,
           COALESCE(m.question,p.name,c.proposition_id) AS contract_question,
           COALESCE(q.name,m.event_title) AS question_name,
           c.relation_confidence,c.relation_provenance,
           m.venue,m.market_id,m.event_id,m.event_title,
           m.probability,m.previous_probability,m.probability_delta_pp,
           m.quote_basis,CAST(m.known_at AS VARCHAR) AS known_at,
           CAST(m.observed_at AS VARCHAR) AS observed_at,
           m.provider_quote_freshness_verified,
           m.historical_point_in_time_released
      FROM ranked c
      LEFT JOIN main.lab_live_market_latest_v1 m
          ON m.proposition_id=c.proposition_id
      LEFT JOIN named p ON p.node_id=c.proposition_id
      LEFT JOIN named q ON q.node_id=c.question_id
     ORDER BY CASE WHEN m.market_id IS NOT NULL THEN 0 ELSE 1 END,
              m.known_at DESC NULLS LAST,c.proposition_id
     LIMIT ?"""
    records = query(sql, (node_id, limit))
    return {
        "mode": "ENTITLED_REVERSE_GRAPH_TO_CAPTURED_CONTRACTS",
        "kind": kind, "node_id": node_id, "rows": records,
        "total_returned": len(records),
        "source_scope": "SAMPLED_CAPTURED_MARKETS_NOT_PROVIDER_WIDE",
        "contract_quotes_are_not_calibrated_event_probabilities": True,
        "original_provider_quote_freshness_not_verified": True,
        "mapping_status": "RESEARCH_HYPOTHESES_NOT_APPROVED_ISSUER_EVENT_BETAS",
        "warning": "Do not pool distinct settlement contracts into one event probability."
    }


def reverse_reference(graph, node_id: str, limit: int = 30):
    """Public repo reference paths only; no live contract names, odds or histories."""
    byid = {n["id"]: n for n in graph["nodes"]}
    if node_id not in byid:
        raise ValueError("UNKNOWN_REFERENCE_NODE")
    edges = graph["edges"]
    adjacent = {}
    for edge in edges:
        adjacent.setdefault(edge["src"], []).append(edge["dst"])
        adjacent.setdefault(edge["dst"], []).append(edge["src"])
    seen = {node_id: [node_id]}
    queue = [node_id]
    while queue:
        current = queue.pop(0)
        if len(seen[current]) >= 6:
            continue
        for other in adjacent.get(current, []):
            if other not in seen and other in byid:
                seen[other] = seen[current] + [other]
                queue.append(other)
    candidates = [dict(event_id=nid, name=byid[nid]["name"], path=route,
                       path_length=len(route)-1,
                       status="ILLUSTRATIVE_RESEARCH_SCENARIO_NOT_LIVE_EVENT")
                  for nid, route in seen.items()
                  if byid[nid]["type"] == "event" and nid != node_id]
    candidates.sort(key=lambda r: (r["path_length"], r["name"]))
    return {"mode":"PUBLIC_REFERENCE_REVERSE_PATHS_NO_LIVE_PROBABILITIES",
            "node_id":node_id,"node":byid[node_id],
            "events":candidates[:max(1,min(limit,75))],
            "quotes_included":False,
            "notice":"Only hypothetical source-seed scenarios; authentic market quotes require entitled analyst access."}

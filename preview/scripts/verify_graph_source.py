#!/usr/bin/env python3
"""Recheck every published graph analyst-prior security edge against original git seed.

Offline, read-only. Any invented analyst-weight, issuer name, or factor
definition fails instead of silently escaping as 'source-backed'. Does NOT
review hypothetical scenario/channel edges as factual causal relations.
"""
from __future__ import annotations
from collections import defaultdict
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
PREVIEW=ROOT/"preview"
ALLOWED={"seeds/exposures.csv","securities.csv","seeds/factors.json"}


def audit_graph_sources(root: Path=ROOT):
    g=json.loads((root/"preview"/"data"/"graph.json").read_text())
    with (root/"seeds"/"exposures.csv").open(newline="",encoding="utf-8") as f:
        exp=list(csv.DictReader(f))
    prior=defaultdict(set)
    for x in exp:
        if x.get("qid") and x["qid"].startswith("Q"):
            try: weight=float(x["weight"])
            except (TypeError,ValueError):continue
            prior[x["qid"],x["ticker"]].add((weight,x.get("rationale") or "Analyst-prior exposure membership"))
    with (root/"securities.csv").open(newline="",encoding="utf-8") as f:
        security={x["ticker"]:x for x in csv.DictReader(f)}
    factor={x["id"]:x for x in json.loads((root/"seeds"/"factors.json").read_text())["factors"]}
    ids=set()
    for n in g["nodes"]:
        if n["id"] in ids: raise ValueError("Duplicate node")
        ids.add(n["id"])
        if n["type"]=="security":
            original=security.get(n.get("ticker"))
            if not original or n["id"]!="security:"+n["ticker"] or n["name"]!=original["name"]:
                raise ValueError("Security ticker/name drift from original repository")
        if n["type"]=="factor":
            original=factor.get(n["id"].removeprefix("factor:"))
            if not original or n["name"]!=original["name"] or n["description"]!=original["definition"]:
                raise ValueError("Qualitative factor definition drift")
        if n["type"]=="event" and n.get("source_received_at"):
            if n["review_status"]!="ORIGINAL_OFFICIAL_VALUE_RECEIPT_RESEARCH_ONLY":
                raise ValueError("Official later-retrieved BEA actual must not imply PIT evidence")
    nprior=0
    for e in g["edges"]:
        if e.get("review_status")!="RESEARCH_ONLY_NOT_APPROVED":
            raise ValueError("Graph edge incorrectly promoted to institutional approval")
        if e["src"] not in ids or e["dst"] not in ids:
            raise ValueError("Graph endpoint references missing node")
        if e["type"]=="research_exposure_prior":
            qid=e["src"].removeprefix("entity:")
            ticker=e["dst"].removeprefix("security:")
            if e["src"]!="entity:"+qid or e["dst"]!="security:"+ticker:
                raise ValueError("Analyst-prior endpoints must be entity/security")
            if (e.get("weight"),e.get("summary")) not in prior.get((qid,ticker),set()):
                raise ValueError("Altered/reinterpreted exposure weight or analyst rationale")
            if e.get("source")!="seeds/exposures.csv" or e.get("source_qid")!=qid:
                raise ValueError("Missing original seed attribution")
            nprior+=1
        elif e["type"] not in {"hypothetical_involves","hypothetical_transmission","hypothetical_factor_channel"}:
            raise ValueError("Unknown edge approval type")
    if nprior<40:
        raise ValueError("Graph source analyst-prior evidence missing")
    return {"status":"GRAPH_ORIGINAL_SEED_PRIORS_AND_FACTOR_DEFINITIONS_REPLAY_VERIFIED",
            "prior_edges_matched":nprior,"nodes":len(g["nodes"]),"edges":len(g["edges"]),
            "institutional_release":False,"causal_links_validated":False}


def main():
    print(json.dumps(audit_graph_sources(),sort_keys=True))


if __name__=="__main__":
    main()

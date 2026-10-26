#!/usr/bin/env python3
"""Standalone EventRisk engineering preview; serves ONLY audited aggregate snapshots.

No MotherDuck connector, no source secrets, and no institutional/raw price data
are loaded at runtime. Internet-facing demo is NOT the protected research API.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
import csv
from io import StringIO
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "data" / "snapshot.json"
GRAPH = ROOT / "data" / "graph.json"
MAX_BYTES = 1_000_000
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.js": ("assets/app.js", "text/javascript; charset=utf-8"),
    "/assets/styles.css": ("assets/styles.css", "text/css; charset=utf-8"),
    "/assets/icon-80.png": ("assets/icon-80.png", "image/png"),
    "/excel/taskpane.html": ("excel/taskpane.html", "text/html; charset=utf-8"),
    "/excel/taskpane.js": ("excel/taskpane.js", "text/javascript; charset=utf-8"),
    "/excel/taskpane.css": ("excel/taskpane.css", "text/css; charset=utf-8"),
    "/excel/manifest.xml": ("excel/manifest.xml", "application/xml; charset=utf-8"),
    "/report": ("report.html", "text/html; charset=utf-8"),
    "/assets/report.js": ("assets/report.js", "text/javascript; charset=utf-8"),
    "/assets/report.css": ("assets/report.css", "text/css; charset=utf-8"),
}
PUBLIC_ROUTES = frozenset({
    "/health/live", "/api/v1/meta", "/api/v1/overview", "/api/v1/release-gates",
    "/api/v1/factors", "/api/v1/evidence", "/api/v1/blockers",
    "/api/v1/metrics.csv", "/api/v1/graph", "/api/v1/capabilities",
})


def read_snapshot(path: Path = SNAPSHOT) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = ("snapshot_id", "as_of_utc", "source_git_sha", "mode",
                "release", "metrics", "factors", "evidence", "blockers")
    if any(k not in data for k in required) or data["mode"] != "FROZEN_RESEARCH_AGGREGATES":
        raise ValueError("Unsupported research preview snapshot or unapproved live mode")
    if data["release"].get("institutional_release_approved") is not False:
        raise ValueError("Preview cannot serve claimed institutional release")
    if data["release"]["automatic_passed"] + data["release"]["automatic_blocked"] != data["release"]["automatic_total"]:
        raise ValueError("Institutional release gate counts do not reconcile")
    if any(x.get("source_kind") != "audited_aggregate" for x in data["metrics"]):
        raise ValueError("Preview metrics must be reviewed aggregate-only evidence")
    return data


def read_graph(path: Path = GRAPH) -> dict:
    """Only public repository priors and illustrative hypotheses; never vendor quotes."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (doc.get("mode") != "FROZEN_PUBLIC_SEED_PRIORS_AND_ILLUSTRATIVE_EVENT_SCENARIOS"
        or doc.get("version") != "1.0"
        or len(doc.get("nodes", ())) > 250 or len(doc.get("edges", ())) > 600):
        raise ValueError("Unapproved graph snapshot or overlarge graph")
    allowed_types = {"event", "entity", "security", "channel", "factor"}
    expected_status = {
        "event": {"ILLUSTRATIVE_SCENARIO_NOT_AN_EVENT_OBSERVATION",
                  "ORIGINAL_OFFICIAL_VALUE_RECEIPT_RESEARCH_ONLY"},
        "entity": {"UNREVIEWED_RESEARCH"},
        "security": {"ANALYST_PRIOR_UNVERIFIED"},
        "channel": {"UNREVIEWED_HYPOTHESIS"},
        "factor": {"CATALOG_DEFINITION_NOT_MODEL_APPROVAL"},
    }
    allowed_edges = {"research_exposure_prior", "hypothetical_involves",
                     "hypothetical_transmission", "hypothetical_factor_channel"}
    ids = set()
    for n in doc["nodes"]:
        if (not isinstance(n.get("id"), str) or n.get("type") not in allowed_types
            or not n.get("name") or n["id"] in ids
            or n.get("review_status") not in expected_status[n["type"]]):
            raise ValueError("Unknown or promoted graph node")
        ids.add(n["id"])
    seen_edges = set()
    for e in doc["edges"]:
        edge_key = (e.get("src"), e.get("dst"), e.get("type"))
        if (e.get("type") not in allowed_edges or e.get("src") not in ids
            or e.get("dst") not in ids or edge_key in seen_edges
            or e.get("review_status") != "RESEARCH_ONLY_NOT_APPROVED"):
            raise ValueError("Invalid or promoted research edge")
        if e["type"] == "research_exposure_prior":
            if (not e["src"].startswith("entity:") or not e["dst"].startswith("security:")
                or type(e.get("weight")) not in (float, int)
                or not 0 < e["weight"] <= 1):
                raise ValueError("Invalid source analyst prior")
        seen_edges.add(edge_key)
    return doc


def capabilities_report(data: dict) -> dict:
    """Request-time report from current admitted public snapshots, not live market data."""
    graph = read_graph()
    node_counts = {t: sum(n["type"] == t for n in graph["nodes"])
                   for t in ("event", "entity", "security", "channel", "factor")}
    edge_counts = {t: sum(e["type"] == t for e in graph["edges"])
                   for t in ("research_exposure_prior", "hypothetical_involves",
                             "hypothetical_transmission", "hypothetical_factor_channel")}
    if not all(e["review_status"] == "RESEARCH_ONLY_NOT_APPROVED" for e in graph["edges"]):
        raise ValueError("Unapproved graph edge presented as certified evidence")
    return {
        "report_type": "ENGINEERING_CAPABILITY_REPORT",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_mode": "REQUEST_TIME_READ_OF_FROZEN_AUDITED_SNAPSHOTS",
        "continuous_market_refresh_enabled": False,
        "snapshot_id": data["snapshot_id"],
        "snapshot_as_of_utc": data["as_of_utc"],
        "graph_as_of_utc": graph["as_of_utc"],
        "institutional_release_approved": False,
        "graph": {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
                  "node_types": node_counts, "edge_types": edge_counts},
        "capabilities": [
            {"name": "Explore events, entities, and securities",
             "earlier": "Existing qualitative graph in the original MVP",
             "now": "Preserved interaction design with source-segregated research graph",
             "status": "AVAILABLE"},
            {"name": "Connect economic transmission channels",
             "earlier": "Not present in the original event-security graph explorer",
             "now": "Event -> economic channel -> factor hypotheses with explicit nonapproval",
             "status": "NEW_PREVIEW"},
            {"name": "Trace original public exposure weights",
             "earlier": "The analyst-prior paths were not separately replayed in this preview",
             "now": "Entity-security weights and rationales independently rechecked against repository seed CSV",
             "status": "NEW_PREVIEW"},
            {"name": "Inspect official BEA reported economic values",
             "earlier": "No independently accepted original BEA actual-value packets in the earlier MVP",
             "now": "Two actual published values plus October retrieval provenance; no surprise or first-publication claim",
             "status": "NEW_RESEARCH_EVIDENCE"},
            {"name": "See institutional readiness and failed tests",
             "earlier": "Original graph did not foreground the institutional release-gate / beta evidence ledger",
             "now": "Explicit 54-gate status, 135 missing mandatory fields, 96 beta fit negative result",
             "status": "NEW_PREVIEW"},
            {"name": "Use Excel and API research outputs",
             "earlier": "Earlier graph already provided API and Office add-in foundations",
             "now": "Separate graph JSON endpoint, capability report and formulas-ready Excel research workbook",
             "status": "EXPANDED"},
        ],
        "release": data["release"],
        "metrics": data["metrics"],
        "limitations": [
            "Request-time generation does not mean real-time warehouse or venue data.",
            "Event scenarios and channel mappings are illustrative, not certified event innovations.",
            "Entity-security seed weights are priors, not original-source PIT betas or price forecasts.",
            "Original corporate actions, source redistribution rights and independent model review remain blocked."
        ]
    }


def csv_export(data: dict) -> bytes:
    out = StringIO(newline="")
    w = csv.writer(out)
    w.writerow(["Metric", "Value", "Unit", "Verified as of UTC", "Evidence source", "Status"])
    for m in data["metrics"]:
        label = str(m["label"])
        source = str(m["source"])
        # Prevent spreadsheet CSV formula injection even if a future snapshot
        # mistakenly carries external string labels.
        def excel_safe(s: str) -> str:
            return "'" + s if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else s
        w.writerow([excel_safe(label), m["value"], m["unit"], data["as_of_utc"],
                    excel_safe(source), "Research only - not institutionally approved"])
    return out.getvalue().encode("utf-8")


def response_for(path: str, data: dict):
    if path not in PUBLIC_ROUTES:
        return None
    if path == "/health/live":
        obj = {"status": "alive", "service": "eventrisk-engineering-preview",
               "data_mode": "frozen_aggregates"}
    elif path == "/api/v1/meta":
        obj = {k: data[k] for k in ("snapshot_id", "as_of_utc", "source_git_sha", "mode", "warnings")}
        obj["live_data_refresh_enabled"] = False
        obj["institutional_release_approved"] = False
    elif path == "/api/v1/overview":
        obj = {k: data[k] for k in ("snapshot_id", "as_of_utc", "mode", "metrics", "release", "summary")}
    elif path == "/api/v1/release-gates":
        obj = {"snapshot_id": data["snapshot_id"], "as_of_utc": data["as_of_utc"],
               "release": data["release"]}
    elif path == "/api/v1/factors":
        obj = {"snapshot_id": data["snapshot_id"], "factors": data["factors"]}
    elif path == "/api/v1/evidence":
        obj = {"snapshot_id": data["snapshot_id"], "evidence": data["evidence"]}
    elif path == "/api/v1/blockers":
        obj = {"snapshot_id": data["snapshot_id"], "blockers": data["blockers"]}
    elif path == "/api/v1/capabilities":
        obj = capabilities_report(data)
    elif path == "/api/v1/graph":
        return (200, "application/json; charset=utf-8",
                json.dumps(read_graph(), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    elif path == "/api/v1/metrics.csv":
        return (200, "text/csv; charset=utf-8", csv_export(data))
    else:
        return None
    return (200, "application/json; charset=utf-8",
            json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "EventRiskPreview/1.0"
    sys_version = ""

    def do_HEAD(self):
        self._get(send_body=False)

    def do_GET(self):
        self._get(send_body=True)

    def do_POST(self):
        self._write(405, "text/plain; charset=utf-8", b"Method not allowed", True)

    def _get(self, send_body=True):
        path = urlsplit(self.path).path
        try:
            data = read_snapshot()
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            self._write(503, "application/json", b'{"error":"unavailable_snapshot"}', send_body)
            return
        if path in PUBLIC_ROUTES:
            try:
                status, content_type, body = response_for(path, data)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                self._write(503, "application/json",
                            b'{"error":"unavailable_graph_snapshot"}', send_body)
                return
            self._write(status, content_type, body, send_body)
            return
        if path not in STATIC:
            self._write(404, "application/json", b'{"error":"not_found"}', send_body)
            return
        filename, mime = STATIC[path]
        target = ROOT / filename
        try:
            body = target.read_bytes()
            if len(body) > MAX_BYTES:
                raise OSError("Static asset too large")
        except OSError:
            self._write(503, "application/json", b'{"error":"asset_unavailable"}', send_body)
            return
        self._write(200, mime, body, send_body)

    def _write(self, status: int, mime: str, body: bytes, send_body: bool):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if not urlsplit(self.path).path.startswith("/excel/taskpane"):
            self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
            "default-src 'self'; script-src 'self' https://appsforoffice.microsoft.com; "
            "style-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "frame-ancestors 'self' https://*.office.com https://*.office365.com https://*.officeapps.live.com; object-src 'none'; base-uri 'none'")
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Do not log arbitrary request headers, query strings or API keys.
        sys.stderr.write("preview_http " + fmt % args + "\n")


def main():
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    read_snapshot()
    read_graph()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"EventRisk frozen-aggregate preview listening on {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

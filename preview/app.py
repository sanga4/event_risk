#!/usr/bin/env python3
"""Standalone EventRisk engineering preview; serves ONLY audited aggregate snapshots.

No MotherDuck connector, no source secrets, and no institutional/raw price data
are loaded at runtime. Internet-facing demo is NOT the protected research API.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import csv
from io import StringIO
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "data" / "snapshot.json"
MAX_BYTES = 1_000_000
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.js": ("assets/app.js", "text/javascript; charset=utf-8"),
    "/assets/styles.css": ("assets/styles.css", "text/css; charset=utf-8"),
    "/assets/icon-80.png": ("assets/icon-80.png", "image/png"),
    "/excel/taskpane.html": ("excel/taskpane.html", "text/html; charset=utf-8"),
    "/excel/taskpane.js": ("excel/taskpane.js", "text/javascript; charset=utf-8"),
    "/excel/manifest.xml": ("excel/manifest.xml", "application/xml; charset=utf-8"),
}
PUBLIC_ROUTES = frozenset({
    "/health/live", "/api/v1/meta", "/api/v1/overview", "/api/v1/release-gates",
    "/api/v1/factors", "/api/v1/evidence", "/api/v1/blockers",
    "/api/v1/metrics.csv",
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
            status, content_type, body = response_for(path, data)
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
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"EventRisk frozen-aggregate preview listening on {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

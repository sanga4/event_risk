#!/usr/bin/env python3
"""Read-only external smoke test for the deliberately unconfigured Factor Lab API.

Verifies current fail-closed behavior from outside Railway. This is NOT evidence
of institutional data authorization or permission to enable API credentials.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ORIGIN = "https://factor-lab-api-production.up.railway.app"
EXPECT = {
    "/health/live": 200,
    "/health/ready": 503,
    "/v1/research/status": 401,
    "/docs": 404,
}


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def direct_open(request, timeout):
    return build_opener(NoRedirects()).open(request, timeout=timeout)


def probe(path, opener=None):
    """Return a bounded, non-sensitive status record or fail the whole smoke."""
    if path not in EXPECT:
        raise ValueError("Unapproved probe path")
    request = Request(ORIGIN + path, headers={
        "User-Agent": "EventRisk-research-negative-auth-smoke/1.0",
        "Accept": "application/json",
    })
    if urlsplit(request.full_url).hostname != "factor-lab-api-production.up.railway.app":
        raise ValueError("Unexpected host")
    open_fn = opener or direct_open
    try:
        with open_fn(request, timeout=10) as response:
            status = response.getcode()
            headers = response.headers
            data = response.read(4096)
    except HTTPError as error:
        status = error.code
        headers = error.headers
        data = error.read(4096)
    if status != EXPECT[path]:
        raise RuntimeError("Unexpected status for %s: %s, expected %s"
                           % (path, status, EXPECT[path]))
    if headers.get("Cache-Control", "").lower() != "no-store":
        raise RuntimeError("Missing no-store cache header: " + path)
    if path == "/health/live":
        if json.loads(data).get("status") != "alive":
            raise RuntimeError("Live health contract violated")
    if path == "/v1/research/status":
        if "apikey" not in headers.get("WWW-Authenticate", "").lower():
            raise RuntimeError("Protected data API is missing auth challenge")
    return {"path": path, "http_status": status, "cache_disabled": True}


def main():
    if os.environ.get("LAB_RESEARCH_SCOPE") != "internal-only":
        raise RuntimeError("This smoke is explicitly research-only")
    results = [probe(path) for path in EXPECT]
    print("PUBLIC_FAIL_CLOSED_SMOKE=" + json.dumps(results, sort_keys=True))
    print("INSTITUTIONAL_RELEASE=FALSE")


if __name__ == "__main__":
    main()

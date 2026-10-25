"""Offline negative-auth smoke tests; never perform network calls in CI."""
from __future__ import annotations
import importlib.util
import io
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
import unittest

source = Path(__file__).resolve().parents[1] / "lab" / "phase1_public_fail_closed_smoke.py"
spec = importlib.util.spec_from_file_location("lab_public_smoke", source)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class FakeResponse:
    def __init__(self, code, headers, payload):
        self.status = code
        self.headers = headers
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return self.status

    def read(self, n):
        return self.payload[:n]


def opener_for(overrides=None):
    overrides = overrides or {}

    def open_fake(request, timeout):
        path = urlsplit(request.full_url).path
        assert request.full_url.startswith(smoke.ORIGIN + "/")
        assert "X-api-key" not in dict(request.header_items())
        assert timeout == 10
        code = overrides.get(path, smoke.EXPECT[path])
        headers = {"Cache-Control": "no-store"}
        if path == "/v1/research/status":
            headers["WWW-Authenticate"] = "APIKey"
        payload = b'{"status":"alive"}' if path == "/health/live" else b'{"detail":"blocked"}'
        if code >= 400:
            raise HTTPError(request.full_url, code, "blocked", headers, io.BytesIO(payload))
        return FakeResponse(code, headers, payload)

    return open_fake


class PublicSmokeTests(unittest.TestCase):
    def test_current_expected_fail_closed_contract(self):
        for path, expected in smoke.EXPECT.items():
            with self.subTest(path=path):
                result = smoke.probe(path, opener_for())
                self.assertEqual(result["http_status"], expected)

    def test_unexpected_open_readiness_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Unexpected status"):
            smoke.probe("/health/ready", opener_for({"/health/ready": 200}))

    def test_unexpected_open_data_endpoint_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Unexpected status"):
            smoke.probe("/v1/research/status", opener_for({"/v1/research/status": 200}))

    def test_unapproved_paths_not_requested(self):
        with self.assertRaises(ValueError):
            smoke.probe("/v1/research/panel", opener_for())

    def test_no_cache_header_fails(self):
        def wrong_headers(request, timeout):
            return FakeResponse(200, {}, b'{"status":"alive"}')
        with self.assertRaisesRegex(RuntimeError, "no-store"):
            smoke.probe("/health/live", wrong_headers)

    def test_no_auth_challenge_fails(self):
        def wrong_headers(request, timeout):
            raise HTTPError(request.full_url, 401, "blocked",
                            {"Cache-Control": "no-store"}, io.BytesIO(b'{}'))
        with self.assertRaisesRegex(RuntimeError, "auth challenge"):
            smoke.probe("/v1/research/status", wrong_headers)


if __name__ == "__main__":
    unittest.main()

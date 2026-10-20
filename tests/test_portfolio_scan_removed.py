"""Regression checks for the isolated EventRisk build.

These assertions guard only the retired portfolio-scanning surface. Market
history, event search, single-security exposures and all other features remain.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoPortfolioScanTests(unittest.TestCase):
    def read(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def test_excel_has_no_scan_function(self):
        metadata = json.loads(self.read("excel/functions.json"))
        registered = {item["id"] for item in metadata["functions"]}
        self.assertEqual(registered, {
            "PROB", "CHANGE", "NAME", "QUESTIONS", "RUNGS",
            "PROPOSITIONS", "EXPOSURES", "HISTORY",
        })
        js = self.read("excel/functions.js")
        self.assertNotIn('CustomFunctions.associate("SCAN"', js)
        self.assertNotRegex(js, r"function\s+scan\s*\(")
        self.assertNotIn("/portfolio/scan", js)

    def test_taskpane_has_no_scan_controls(self):
        html = self.read("excel/taskpane.html")
        for marker in ('id="scan"', 'scanMsg', '=EVENTRISK.SCAN',
                       "Scan selection", "Portfolio scan"):
            self.assertNotIn(marker, html)
        self.assertIn('id="refresh"', html)
        self.assertIn('id="search"', html)

    def test_website_has_no_scan_copy_or_api_documentation(self):
        html = self.read("web/index.html")
        self.assertNotRegex(html, r"(?i)portfolio[ -]?scan|scan[ -]?portfolio")
        self.assertNotIn("/portfolio/scan", html)
        self.assertNotIn("=EVENTRISK.SCAN", html)

    def test_backend_has_no_scan_endpoint(self):
        api = self.read("api.py")
        self.assertNotIn('/portfolio/scan', api)
        self.assertNotIn("class ScanRequest", api)
        self.assertNotIn("def portfolio_scan(", api)

    def test_docs_and_manifest_have_no_active_scan_references(self):
        for name in ("README.md", "CLAUDE.md", "excel/manifest.xml"):
            contents = self.read(name)
            self.assertNotRegex(contents, r"(?i)portfolio[ -]?scan|scan[ -]?portfolio")
            self.assertNotIn("/portfolio/scan", contents)
            self.assertNotIn("EVENTRISK.SCAN", contents)


if __name__ == "__main__":
    unittest.main()

import io
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from seo_audit import PageParser, score, parse_sitemap, audit_sitemap, main

HTML = """<html><head>
<title>Example Title For Testing Purposes Only Here</title>
<meta name="description" content="A description.">
<meta property="og:title" content="Example">
<link rel="canonical" href="https://example.com/">
<script type="application/ld+json">{"@type":"Article"}</script>
</head><body>
<h1>Hello</h1><h2>Sub</h2>
<img src="a.jpg" alt="A"><img src="b.jpg">
<a href="/x">internal</a><a href="https://other.com">external</a>
<p>one two three</p>
</body></html>"""


class TestParser(unittest.TestCase):
    def setUp(self):
        self.p = PageParser()
        self.p.feed(HTML)

    def test_title_and_h1(self):
        self.assertTrue(self.p.title.startswith("Example Title"))
        self.assertEqual(self.p.h1, ["Hello"])
        self.assertEqual(self.p.h2_count, 1)

    def test_canonical_and_ld(self):
        self.assertEqual(self.p.canonical, "https://example.com/")
        self.assertEqual(self.p.json_ld_blocks, 1)
        self.assertEqual(self.p.ld_types, ["Article"])

    def test_images_and_score(self):
        self.assertEqual((self.p.images, self.p.images_with_alt), (2, 1))
        report = {
            "status": 200, "title": self.p.title,
            "meta_description": "x" * 130, "h1": self.p.h1,
            "canonical": self.p.canonical, "json_ld_blocks": 1,
            "meta": {"og:title": "Example"}, "images": 2, "images_with_alt": 1,
        }
        self.assertGreaterEqual(score(report), 85)


SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
  <url><loc>https://example.com/blog</loc></url>
</urlset>"""

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>"""

CHILD_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/p1</loc></url>
  <url><loc>https://example.com/p2</loc></url>
</urlset>"""


def _resp(body):
    return (200, {"Content-Type": "application/xml"}, body, 0.01)


class TestSitemap(unittest.TestCase):
    def test_parse_urlset(self):
        self.assertEqual(parse_sitemap(SITEMAP_XML), [
            "https://example.com/",
            "https://example.com/about",
            "https://example.com/blog",
        ])

    def test_parse_limit(self):
        big = "<urlset>" + "".join(
            f"<url><loc>https://example.com/p{i}</loc></url>" for i in range(25)
        ) + "</urlset>"
        self.assertEqual(len(parse_sitemap(big)), 20)
        self.assertEqual(parse_sitemap(big, limit=2), [
            "https://example.com/p0", "https://example.com/p1"])

    def test_parse_empty_and_malformed(self):
        self.assertEqual(parse_sitemap("<urlset></urlset>"), [])
        with self.assertRaises(ET.ParseError):
            parse_sitemap("<urlset><loc>oops")

    @patch("seo_audit.fetch")
    def test_audit_sitemap_mixed_success_and_failure(self, mock_fetch):
        mock_fetch.return_value = _resp(SITEMAP_XML)
        reports = {
            "https://example.com/": {"url": "https://example.com/", "score": 90},
            "https://example.com/about": {"url": "https://example.com/about", "score": 70},
        }

        def fake_audit(url):
            if url == "https://example.com/blog":
                import urllib.error
                raise urllib.error.URLError("boom")
            return reports[url]

        with patch("seo_audit.audit", side_effect=fake_audit):
            summary = audit_sitemap("https://example.com/sitemap.xml")
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["audited"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["average_score"], 80.0)
        self.assertEqual(summary["results"][2]["url"], "https://example.com/blog")
        self.assertIn("error", summary["results"][2])

    @patch("seo_audit.fetch")
    def test_sitemap_index_followed(self, mock_fetch):
        def dispatch(url, timeout=20):
            if url.endswith("sitemap.xml"):
                return _resp(SITEMAP_INDEX_XML)
            return _resp(CHILD_SITEMAP_XML)
        mock_fetch.side_effect = dispatch
        with patch("seo_audit.audit", return_value={"url": "x", "score": 50}):
            summary = audit_sitemap("https://example.com/sitemap.xml")
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["average_score"], 50.0)

    @patch("seo_audit.fetch")
    def test_main_sitemap_json_end_to_end(self, mock_fetch):
        def dispatch(url, timeout=20):
            if url.endswith("sitemap.xml"):
                return _resp(SITEMAP_XML)
            return (200, {"Content-Type": "text/html"}, HTML, 0.01)
        mock_fetch.side_effect = dispatch
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--sitemap", "https://example.com/sitemap.xml", "--json"])
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["total"], 3)
        self.assertEqual(out["audited"], 3)
        self.assertIsInstance(out["average_score"], float)
        self.assertEqual(len(out["results"]), 3)

    def test_main_requires_exactly_one_target(self):
        with self.assertRaises(SystemExit):
            main([])
        with self.assertRaises(SystemExit):
            main(["https://example.com", "--sitemap", "https://example.com/sitemap.xml"])


if __name__ == "__main__":
    unittest.main()

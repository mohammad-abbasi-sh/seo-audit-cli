import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from seo_audit import PageParser, score

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


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""seo-audit-cli — a zero-dependency technical SEO audit for a single URL.

Usage:
    python seo_audit.py https://example.com
    python seo_audit.py https://example.com --json
    python seo_audit.py https://example.com --json -o report.json

Checks: HTTP status & timing, title, meta description, H1, canonical,
robots meta, Open Graph, JSON-LD structured data, image alt coverage,
internal/external links and word count. Prints a 0-100 score.
Only Python's standard library is used — nothing to install.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urlparse

UA = "seo-audit-cli/1.0 (+https://github.com/shahkooh/seo-audit-cli)"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str = ""
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.h1: list[str] = []
        self._in_h1 = False
        self._h1_buf = ""
        self.h2_count = 0
        self.canonical: str | None = None
        self.images = 0
        self.images_with_alt = 0
        self.links_internal = 0
        self.links_external = 0
        self.json_ld_blocks = 0
        self._in_ld = False
        self.ld_types: list[str] = []
        self.text_parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")
        elif tag == "h1":
            self._in_h1, self._h1_buf = True, ""
        elif tag == "h2":
            self.h2_count += 1
        elif tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = a.get("href")
        elif tag == "img":
            self.images += 1
            if (a.get("alt") or "").strip():
                self.images_with_alt += 1
        elif tag == "a" and a.get("href"):
            self._count_link(a["href"])
        elif tag == "script":
            if (a.get("type") or "").lower() == "application/ld+json":
                self.json_ld_blocks += 1
                self._in_ld = True
            self._skip += 1
        elif tag == "style":
            self._skip += 1

    def _count_link(self, href: str) -> None:
        # Resolved against the page host in audit(); here we only bucket
        # absolute external vs. everything else as a first pass.
        if href.startswith(("http://", "https://")):
            self.links_external += 1
        elif not href.startswith(("#", "mailto:", "tel:", "javascript:")):
            self.links_internal += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h1" and self._in_h1:
            self.h1.append(self._h1_buf.strip())
            self._in_h1 = False
        elif tag == "script":
            self._in_ld = False
            self._skip = max(0, self._skip - 1)
        elif tag == "style":
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h1:
            self._h1_buf += data
        if self._in_ld:
            for m in re.findall(r'"@type"\s*:\s*"([^"]+)"', data):
                self.ld_types.append(m)
        if not self._skip:
            self.text_parts.append(data)


def fetch(url: str, timeout: int = 20) -> tuple[int, dict, str, float]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, dict(resp.headers), body, time.time() - start


def score(report: dict) -> int:
    s = 0
    s += 15 if report["status"] == 200 else 0
    s += 15 if 30 <= len(report["title"]) <= 60 else (8 if report["title"] else 0)
    d = report["meta_description"]
    s += 15 if 120 <= len(d) <= 160 else (8 if d else 0)
    s += 15 if len(report["h1"]) == 1 else (5 if report["h1"] else 0)
    s += 10 if report["canonical"] else 0
    s += 10 if report["json_ld_blocks"] > 0 else 0
    s += 10 if report["meta"].get("og:title") else 0
    if report["images"]:
        s += round(10 * report["images_with_alt"] / report["images"])
    else:
        s += 10
    return int(s)


def audit(url: str) -> dict:
    if not urlparse(url).scheme:
        url = "https://" + url
    status, headers, body, elapsed = fetch(url)
    p = PageParser()
    p.feed(body)
    words = len(" ".join(p.text_parts).split())
    report = {
        "url": url,
        "status": status,
        "response_time_s": round(elapsed, 3),
        "content_type": headers.get("Content-Type", ""),
        "title": p.title.strip(),
        "meta_description": p.meta.get("description", ""),
        "h1": p.h1,
        "h2_count": p.h2_count,
        "canonical": p.canonical,
        "robots_meta": p.meta.get("robots", ""),
        "meta": {k: v for k, v in p.meta.items() if k.startswith("og:")},
        "json_ld_blocks": p.json_ld_blocks,
        "json_ld_types": p.ld_types,
        "images": p.images,
        "images_with_alt": p.images_with_alt,
        "links_internal_bucket": p.links_internal,
        "links_external_bucket": p.links_external,
        "word_count": words,
    }
    report["score"] = score(report)
    return report


def print_human(r: dict) -> None:
    print(f"\nSEO Audit — {r['url']}")
    print("=" * 64)
    print(f"Status: {r['status']}  |  Response: {r['response_time_s']}s  |  Words: {r['word_count']}")
    print(f"Score:  {r['score']}/100")
    print(f"Title ({len(r['title'])} chars): {r['title'] or '— MISSING —'}")
    print(f"Meta description ({len(r['meta_description'])} chars): {r['meta_description'] or '— MISSING —'}")
    print(f"H1 ({len(r['h1'])}): {r['h1'] or '— MISSING —'}  |  H2: {r['h2_count']}")
    print(f"Canonical: {r['canonical'] or '— none —'}")
    print(f"Robots meta: {r['robots_meta'] or '— none (indexable by default) —'}")
    print(f"Open Graph: {list(r['meta'].keys()) or '— none —'}")
    print(f"JSON-LD: {r['json_ld_blocks']} block(s) {r['json_ld_types']}")
    print(f"Images: {r['images']} total, {r['images_with_alt']} with alt")
    print("=" * 64)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Zero-dependency technical SEO audit for one URL.")
    ap.add_argument("url", help="URL to audit, e.g. https://example.com")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument("-o", "--output", help="also write the JSON report to this file")
    args = ap.parse_args(argv)
    try:
        r = audit(args.url)
    except (urllib.error.URLError, ValueError) as e:
        print(f"Error: could not fetch {args.url}: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print_human(r)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2, ensure_ascii=False)
        print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

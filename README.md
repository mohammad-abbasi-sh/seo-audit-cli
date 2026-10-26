# seo-audit-cli

[🇮🇷 توضیحات فارسی](README-fa.md)

**A zero-dependency technical SEO audit for any URL — one command, one score.**

```bash
python seo_audit.py https://example.com
python seo_audit.py https://example.com --json -o report.json
```

No `pip install`, no API key. Python 3.10+ standard library only.

## What it checks

| Check | Why it matters |
| --- | --- |
| HTTP status & response time | A page that is slow or not 200 cannot rank |
| Title (presence + length) | Primary ranking & CTR signal |
| Meta description (presence + length) | CTR in the SERP |
| Exactly one H1 | Document structure for crawlers and AI answers |
| Canonical tag | Duplicate-content control |
| Robots meta | Accidental `noindex` is the silent traffic killer |
| Open Graph tags | How the page looks when shared |
| JSON-LD structured data (+ `@type`s found) | Rich results & GEO / AI-search eligibility |
| Image alt coverage | Accessibility + image search |
| Word count, H2 structure, link buckets | A fast content sanity check |

Output ends with a **0–100 score** so you can track a page — or a competitor — over time.

## Example

See [`examples/example-com.json`](examples/example-com.json) for a real run.

## Tests

```bash
python -m pytest tests/ -q
# or, with no pytest installed:
python -m unittest discover -s tests
```

## Roadmap

- [ ] Sitemap mode: audit every URL in a `sitemap.xml`
- [ ] Batch mode from a CSV of URLs
- [ ] Core Web Vitals via the PageSpeed Insights API (optional key)

## Why I built this

I'm an SEO manager. I run this shape of check by hand every week — so I turned it into a tool. Part of my [12 projects in 12 weeks](https://github.com/mohammad-abbasi-sh) series: SEO × AI, built in public.

MIT — see [LICENSE](LICENSE).

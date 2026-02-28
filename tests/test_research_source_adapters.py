#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from scripts.research_source_adapters import lookup_sec_filings, lookup_sources, resolve_sec_cik, search_knowledge, search_openalex


def _fake_fetcher(url: str, headers: dict[str, str]):
    if "api.openalex.org" in url:
        return {
            "results": [
                {
                    "display_name": "Market structure paper",
                    "id": "https://openalex.org/W1",
                    "ids": {"openalex": "https://openalex.org/W1"},
                    "publication_year": 2024,
                    "cited_by_count": 12,
                    "authorships": [{"author": {"display_name": "Alice"}}],
                    "primary_location": {"source": {"display_name": "Journal A"}},
                }
            ]
        }
    if "company_tickers.json" in url:
        return {"0": {"ticker": "MSFT", "title": "MICROSOFT CORP", "cik_str": 789019}}
    if "submissions/CIK0000789019.json" in url:
        return {
            "name": "MICROSOFT CORP",
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q"],
                    "accessionNumber": ["0000789019-24-000001", "0000789019-24-000002"],
                    "filingDate": ["2024-07-30", "2024-10-24"],
                    "primaryDocument": ["msft10k.htm", "msft10q.htm"],
                }
            },
        }
    raise AssertionError(f"unexpected url: {url}")


class ResearchSourceAdaptersTest(unittest.TestCase):
    def test_search_openalex(self):
        rows = search_openalex("market structure", fetcher=_fake_fetcher)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["connector"], "openalex")
        self.assertEqual(rows[0]["authors"], ["Alice"])

    def test_resolve_sec_cik_and_lookup_filings(self):
        cik = resolve_sec_cik("MSFT", fetcher=_fake_fetcher)
        self.assertEqual(cik, "0000789019")
        rows = lookup_sec_filings("MSFT", fetcher=_fake_fetcher)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["connector"], "sec")
        self.assertEqual(rows[0]["form"], "10-K")

    def test_lookup_sources_combines_connectors(self):
        out = lookup_sources(
            "Microsoft strategy",
            {"source_connectors": ["openalex", "sec"], "company": "Microsoft", "ticker": "MSFT"},
            fetcher=_fake_fetcher,
        )
        self.assertEqual(sorted(out["connectors"]), ["openalex", "sec"])
        self.assertEqual(len(out["items"]), 3)

    def test_search_knowledge_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            kb = root / "知识库"
            kb.mkdir(parents=True, exist_ok=True)
            (kb / "支付SaaS市场研究.md").write_text("# 支付SaaS市场研究\n中国支付SaaS市场规模与竞争格局。", encoding="utf-8")
            rows = search_knowledge("支付SaaS 市场", root=kb, db_path=root / "missing.db")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["connector"], "knowledge")

    def test_search_knowledge_prefers_title_and_market_docs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            kb = root / "知识库"
            (kb / "iresearch_information").mkdir(parents=True, exist_ok=True)
            (kb / "regulation_weixin").mkdir(parents=True, exist_ok=True)
            (kb / "iresearch_information" / "支付SaaS市场研究.md").write_text("# 支付SaaS市场研究\n市场规模与竞争格局。", encoding="utf-8")
            (kb / "regulation_weixin" / "支付合规制度.md").write_text("# 支付合规制度\n支付机构内部控制。", encoding="utf-8")
            rows = search_knowledge("支付SaaS 市场", root=kb, db_path=root / "missing.db")
            self.assertGreaterEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "支付SaaS市场研究")


if __name__ == "__main__":
    unittest.main()

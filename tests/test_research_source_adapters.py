#!/usr/bin/env python3
import unittest

from scripts.research_source_adapters import lookup_sec_filings, lookup_sources, resolve_sec_cik, search_openalex


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


if __name__ == "__main__":
    unittest.main()

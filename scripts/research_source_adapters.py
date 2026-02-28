#!/usr/bin/env python3
"""Official-source retrieval adapters for Research Hub."""

from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

Fetcher = Callable[[str, Dict[str, str]], Dict[str, Any]]

OPENALEX_BASE = "https://api.openalex.org/works"
SEC_SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_USER_AGENT = "AgentSystem Research Hub/1.0 (contact: local-user)"


def _json_get(url: str, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    req = urllib.request.Request(url=url, method="GET", headers=headers or {})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_openalex(query: str, *, per_page: int = 5, mailto: str = "", fetcher: Fetcher | None = None) -> List[Dict[str, Any]]:
    clean = query.strip()
    if not clean:
        return []
    params = {"search": clean, "per-page": str(max(1, min(25, per_page)))}
    if mailto.strip():
        params["mailto"] = mailto.strip()
    url = f"{OPENALEX_BASE}?{urllib.parse.urlencode(params)}"
    payload = (fetcher or _json_get)(url, {"User-Agent": DEFAULT_USER_AGENT})
    rows = payload.get("results", []) if isinstance(payload.get("results", []), list) else []
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(rows, start=1):
        authorships = item.get("authorships", []) if isinstance(item.get("authorships", []), list) else []
        authors = []
        for author in authorships[:4]:
            author_row = author.get("author", {}) if isinstance(author.get("author", {}), dict) else {}
            name = str(author_row.get("display_name", "")).strip()
            if name:
                authors.append(name)
        ids = item.get("ids", {}) if isinstance(item.get("ids", {}), dict) else {}
        out.append(
            {
                "id": f"OA{idx}",
                "connector": "openalex",
                "title": str(item.get("display_name", "")).strip(),
                "type": "paper",
                "url": str(ids.get("openalex", item.get("id", ""))).strip(),
                "year": item.get("publication_year"),
                "authors": authors,
                "source": str((item.get("primary_location", {}) if isinstance(item.get("primary_location", {}), dict) else {}).get("source", {}).get("display_name", "")).strip(),
                "citation_count": int(item.get("cited_by_count", 0) or 0),
                "abstract": str(item.get("abstract", "")).strip(),
            }
        )
    return out


def resolve_sec_cik(identifier: str, *, fetcher: Fetcher | None = None) -> str:
    clean = identifier.strip()
    if not clean:
        return ""
    if clean.isdigit():
        return clean.zfill(10)
    payload = (fetcher or _json_get)(SEC_TICKERS_URL, {"User-Agent": DEFAULT_USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    rows = payload.values() if isinstance(payload, dict) else []
    low = clean.lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker", "")).strip().lower()
        title = str(row.get("title", "")).strip().lower()
        if low == ticker or low == title or low in title:
            cik = str(row.get("cik_str", "")).strip()
            if cik:
                return cik.zfill(10)
    return ""


def lookup_sec_filings(identifier: str, *, per_form: int = 5, fetcher: Fetcher | None = None) -> List[Dict[str, Any]]:
    cik = resolve_sec_cik(identifier, fetcher=fetcher)
    if not cik:
        return []
    url = f"{SEC_SUBMISSIONS_BASE}/CIK{cik}.json"
    payload = (fetcher or _json_get)(url, {"User-Agent": DEFAULT_USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    company_name = str(payload.get("name", "")).strip()
    filings = payload.get("filings", {}) if isinstance(payload.get("filings", {}), dict) else {}
    recent = filings.get("recent", {}) if isinstance(filings.get("recent", {}), dict) else {}
    forms = recent.get("form", []) if isinstance(recent.get("form", []), list) else []
    accession_numbers = recent.get("accessionNumber", []) if isinstance(recent.get("accessionNumber", []), list) else []
    filing_dates = recent.get("filingDate", []) if isinstance(recent.get("filingDate", []), list) else []
    primary_docs = recent.get("primaryDocument", []) if isinstance(recent.get("primaryDocument", []), list) else []
    out: List[Dict[str, Any]] = []
    for idx, form in enumerate(forms[: max(1, min(20, per_form * 2))]):
        accession = str(accession_numbers[idx] if idx < len(accession_numbers) else "").strip()
        filing_date = str(filing_dates[idx] if idx < len(filing_dates) else "").strip()
        primary_doc = str(primary_docs[idx] if idx < len(primary_docs) else "").strip()
        if not accession:
            continue
        accession_flat = accession.replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_flat}/{primary_doc}" if primary_doc else ""
        out.append(
            {
                "id": f"SEC{len(out) + 1}",
                "connector": "sec",
                "title": f"{company_name} {form} filing",
                "type": "sec_filing",
                "url": filing_url,
                "form": str(form).strip(),
                "filed_at": filing_date,
                "company": company_name,
                "cik": cik,
            }
        )
        if len(out) >= per_form:
            break
    return out


def lookup_sources(query: str, params: Dict[str, Any], *, fetcher: Fetcher | None = None) -> Dict[str, Any]:
    connectors = params.get("source_connectors", [])
    if isinstance(connectors, str):
        connectors = [part.strip() for part in connectors.split(",") if part.strip()]
    if not isinstance(connectors, list) or not connectors:
        connectors = ["openalex"]
        if str(params.get("company", "")).strip() or str(params.get("ticker", "")).strip() or str(params.get("sec_identifier", "")).strip():
            connectors.append("sec")

    mailto = str(params.get("mailto", "")).strip()
    per_page = int(params.get("lookup_limit", 5) or 5)
    source_results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for connector in connectors:
        name = str(connector).strip().lower()
        try:
            if name == "openalex":
                source_results.extend(search_openalex(query, per_page=per_page, mailto=mailto, fetcher=fetcher))
            elif name == "sec":
                identifier = (
                    str(params.get("sec_identifier", "")).strip()
                    or str(params.get("ticker", "")).strip()
                    or str(params.get("company", "")).strip()
                )
                if identifier:
                    source_results.extend(lookup_sec_filings(identifier, per_form=per_page, fetcher=fetcher))
            else:
                errors.append({"connector": name, "error": "unsupported_connector"})
        except Exception as exc:
            errors.append({"connector": name, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "query": query,
        "connectors": connectors,
        "items": source_results,
        "errors": errors,
    }

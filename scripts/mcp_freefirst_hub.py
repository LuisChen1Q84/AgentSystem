#!/usr/bin/env python3
"""Free-first data hub: fetch public sources and persist structured snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import tomllib
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "mcp_freefirst.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def detect_topic(cfg: Dict[str, Any], text: str) -> str:
    low = text.lower()
    topics = cfg.get("topics", {})
    for topic, conf in topics.items():
        for kw in conf.get("keywords", []):
            if str(kw).lower() in low:
                return str(topic)
    return "general"


def select_sources(cfg: Dict[str, Any], topic: str, max_sources: int) -> List[Dict[str, Any]]:
    topics = cfg.get("topics", {})
    sources = cfg.get("sources", {})
    source_names = topics.get(topic, {}).get("sources", [])
    if not source_names:
        source_names = topics.get("general", {}).get("sources", [])
    selected = []
    for name in source_names[:max_sources]:
        if name in sources:
            item = dict(sources[name])
            item["id"] = name
            selected.append(item)
    return selected


def extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title[:160]


def html_to_text(html: str, max_len: int = 1200) -> str:
    txt = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    txt = re.sub(r"<style[\s\S]*?</style>", " ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:max_len]


def fetch_one(url: str, timeout: int, user_agent: str) -> Dict[str, Any]:
    req = urllib.request.Request(url=url, headers={"User-Agent": user_agent}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(300_000)
        body = raw.decode("utf-8", errors="replace")
        return {
            "http_status": int(getattr(resp, "status", 200)),
            "content_type": str(resp.headers.get("Content-Type", "")),
            "bytes": len(raw),
            "title": extract_title(body),
            "snippet": html_to_text(body),
        }


def run_sync(cfg: Dict[str, Any], query: str, topic: str, max_sources: int) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    timeout = int(defaults.get("request_timeout_sec", 12))
    ua = str(defaults.get("user_agent", "AgentSystem-FreeFirst/1.0"))
    out_dir = Path(str(defaults.get("output_dir", ROOT / "日志/mcp/freefirst")))
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    day = dt.datetime.now().strftime("%Y-%m-%d")
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_jsonl = out_dir / f"raw_{ts}.jsonl"
    latest = out_dir / "latest.json"

    records: List[Dict[str, Any]] = []
    for src in select_sources(cfg, topic, max_sources):
        rec = {
            "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "date": day,
            "query": query,
            "topic": topic,
            "source_id": src["id"],
            "source_name": src.get("name", src["id"]),
            "source_tier": src.get("tier", "L2_public"),
            "url": src.get("url", ""),
            "status": "ok",
            "error": "",
        }
        try:
            data = fetch_one(rec["url"], timeout=timeout, user_agent=ua)
            rec.update(data)
        except Exception as e:
            rec["status"] = "error"
            rec["error"] = str(e)
        records.append(rec)

    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok = [r for r in records if r.get("status") == "ok"]
    payload = {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query,
        "topic": topic,
        "attempted": len(records),
        "succeeded": len(ok),
        "coverage_rate": round((len(ok) / len(records)) * 100, 2) if records else 0.0,
        "out_jsonl": str(out_jsonl),
    }
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP free-first sync")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--query", default="")
    parser.add_argument("--topic", default="")
    parser.add_argument("--max-sources", type=int, default=0)
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = load_cfg(cfg_path)

    query = args.query.strip()
    topic = args.topic.strip() or detect_topic(cfg, query)
    max_sources = args.max_sources if args.max_sources > 0 else int(cfg.get("defaults", {}).get("max_sources", 6))

    print(json.dumps(run_sync(cfg, query, topic, max_sources), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

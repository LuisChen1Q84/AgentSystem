#!/usr/bin/env python3
"""Week4 shadow compare for skill_router and mcp_connector routing baselines."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
OUT_DIR = ROOT / "日志" / "v2_migration" / "baseline"


SKILL_CASES = [
    "请分析513180的K线和买卖点",
    "帮我做一个低多边形风格人物图",
    "采集商业新闻",
    "我打算更新这张表，excel直接修改原文件",
    "请帮我获取网页内容",
]

MCP_CASES = [
    "帮我获取网页内容",
    "读取本地文件目录",
    "请帮我做任务拆解",
    "查询 sqlite 中的表信息",
]


def run_json(cmd: List[str]) -> Tuple[int, Dict[str, Any]]:
    cp = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    raw = cp.stdout.strip() or cp.stderr.strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {"_parse_error": True, "raw": raw[:500]}
    return int(cp.returncode), payload


def collect_snapshot() -> Dict[str, Any]:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot: Dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "stamp": ts,
        "skill_router": [],
        "mcp_connector": [],
    }
    for text in SKILL_CASES:
        rc, out = run_json(["python3", "scripts/skill_router.py", "route", "--text", text])
        snapshot["skill_router"].append(
            {
                "text": text,
                "returncode": rc,
                "section": out.get("section"),
                "skill": out.get("skill"),
                "score": out.get("score"),
                "keywords": out.get("keywords", []),
            }
        )
    for text in MCP_CASES:
        rc, out = run_json(["python3", "scripts/mcp_connector.py", "route", "--text", text])
        snapshot["mcp_connector"].append(
            {
                "text": text,
                "returncode": rc,
                "server": out.get("server"),
                "tool": out.get("tool"),
                "reason": out.get("reason", ""),
            }
        )
    return snapshot


def _index_by_text(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(x.get("text", "")): x for x in items}


def compare(prev: Dict[str, Any], cur: Dict[str, Any]) -> Dict[str, Any]:
    diffs: List[Dict[str, Any]] = []
    for key, fields in (("skill_router", ["skill", "section", "returncode"]), ("mcp_connector", ["server", "tool", "returncode"])):
        old_map = _index_by_text(prev.get(key, []))
        new_map = _index_by_text(cur.get(key, []))
        for text, new_item in new_map.items():
            old_item = old_map.get(text)
            if old_item is None:
                diffs.append({"module": key, "text": text, "type": "new_case"})
                continue
            changed = {}
            for f in fields:
                if old_item.get(f) != new_item.get(f):
                    changed[f] = {"old": old_item.get(f), "new": new_item.get(f)}
            if changed:
                diffs.append({"module": key, "text": text, "type": "changed", "fields": changed})
    return {"diff_count": len(diffs), "diffs": diffs}


def write_report(snapshot: Dict[str, Any], cmp_result: Dict[str, Any], out_dir: Path) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_json = out_dir / "latest_snapshot.json"
    latest_md = out_dir / "latest_report.md"
    stamp = snapshot["stamp"]
    json_path = out_dir / f"shadow_compare_{stamp}.json"
    md_path = out_dir / f"shadow_compare_{stamp}.md"

    payload = {
        "snapshot": snapshot,
        "compare": cmp_result,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Week4 Shadow Compare Baseline",
        "",
        f"- generated_at: {snapshot['generated_at']}",
        f"- diff_count: {cmp_result['diff_count']}",
        "",
        "## Skill Router Snapshot",
        "",
    ]
    for item in snapshot["skill_router"]:
        lines.append(f"- `{item['text']}` -> skill={item['skill']}, section={item['section']}, rc={item['returncode']}")

    lines.extend(["", "## MCP Connector Snapshot", ""])
    for item in snapshot["mcp_connector"]:
        lines.append(f"- `{item['text']}` -> server={item['server']}, tool={item['tool']}, rc={item['returncode']}")

    lines.extend(["", "## Diff Summary", ""])
    if cmp_result["diff_count"] == 0:
        lines.append("- 无差异（与上一版基线一致）。")
    else:
        for d in cmp_result["diffs"]:
            lines.append(f"- [{d['module']}] `{d['text']}` {d['type']} {d.get('fields', {})}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    latest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Week4 shadow compare baseline generator")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    latest_json = out_dir / "latest_snapshot.json"

    previous = {}
    if latest_json.exists():
        try:
            previous = json.loads(latest_json.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    current = collect_snapshot()
    cmp_result = compare(previous, current) if previous else {"diff_count": 0, "diffs": []}
    out_json, out_md = write_report(current, cmp_result, out_dir=out_dir)

    print(f"out_json={out_json}")
    print(f"out_md={out_md}")
    print(f"diff_count={cmp_result['diff_count']}")


if __name__ == "__main__":
    main()

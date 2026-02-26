#!/usr/bin/env python3
"""Generate concise daily digest markdown from explain/anomaly outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(v):
    if v is None:
        return "NA"
    return f"{v*100:.2f}%"


def render_top(items: List[Dict], title: str, n: int = 5) -> List[str]:
    lines = [f"### {title}"]
    if not items:
        lines.append("- 无")
        return lines
    for it in items[:n]:
        name = it.get("name", it.get("col", ""))
        prev = it.get("previous")
        curr = it.get("current")
        delta = it.get("delta")
        ratio = it.get("ratio")
        lines.append(f"- {name}: {prev} -> {curr}，变化 {delta}（{pct(ratio)}）")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily digest markdown")
    parser.add_argument("--explain-json", required=True)
    parser.add_argument("--anomaly-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    explain = load_json(Path(args.explain_json))
    anomaly = load_json(Path(args.anomaly_json))

    lines: List[str] = []
    lines.append(f"# 日报摘要（{explain.get('target_label','')}）")
    lines.append("")
    lines.append(f"- 对比：{explain.get('prev_label','')} -> {explain.get('target_label','')}")
    lines.append(f"- 异常：错误 {anomaly.get('summary',{}).get('errors',0)}，预警 {anomaly.get('summary',{}).get('warns',0)}")
    lines.append("")

    lines.extend(render_top(explain.get("table5", {}).get("national_key_changes", []), "表5全国关键变化", 6))
    lines.append("")
    lines.extend(render_top(explain.get("table5", {}).get("province_c_top_delta", []), "表5省份变化Top", 6))
    lines.append("")
    lines.extend(render_top(explain.get("table6", {}).get("top_e_delta", []), "表6终端总数变化Top", 6))
    lines.append("")

    findings = anomaly.get("findings", [])
    lines.append("### 异常清单（前10）")
    if not findings:
        lines.append("- 无")
    else:
        for f in findings[:10]:
            lines.append(f"- [{f.get('severity')}] {f.get('section')}: {f.get('message')}")
    lines.append("")

    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"out={out}")


if __name__ == "__main__":
    main()

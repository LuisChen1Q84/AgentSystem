#!/usr/bin/env python3
"""Generate lightweight HTML dashboard from anomaly + explanation reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(v) -> str:
    if v is None:
        return "NA"
    return f"{v*100:.2f}%"


def bar_rows(items: List[Dict], value_key: str, label_key: str, topn: int = 10) -> str:
    items = items[:topn]
    if not items:
        return "<p>无数据</p>"
    max_abs = max(abs(float(i.get(value_key, 0.0))) for i in items) or 1.0
    rows = []
    for i in items:
        label = i.get(label_key, "")
        v = float(i.get(value_key, 0.0))
        w = max(2, int(abs(v) / max_abs * 100))
        sign_cls = "pos" if v >= 0 else "neg"
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{label}</div>
              <div class="bar-track"><div class="bar {sign_cls}" style="width:{w}%"></div></div>
              <div class="bar-val">{v:,.4f}</div>
            </div>
            """
        )
    return "\n".join(rows)


def table_rows(items: List[Dict], cols: List[str]) -> str:
    if not items:
        return "<tr><td colspan='99'>无数据</td></tr>"
    out = []
    for it in items:
        tds = []
        for c in cols:
            v = it.get(c, "")
            if isinstance(v, float):
                if c.endswith("ratio"):
                    v = pct(v)
                else:
                    v = f"{v:,.4f}"
            tds.append(f"<td>{v}</td>")
        out.append("<tr>" + "".join(tds) + "</tr>")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate visual HTML dashboard")
    parser.add_argument("--explain-json", required=True)
    parser.add_argument("--anomaly-json", required=True)
    parser.add_argument("--out-html", required=True)
    args = parser.parse_args()

    explain = load_json(Path(args.explain_json))
    anomaly = load_json(Path(args.anomaly_json))

    t5_nat = explain.get("table5", {}).get("national_key_changes", [])
    t5_top = explain.get("table5", {}).get("province_c_top_delta", [])
    t6_top_e = explain.get("table6", {}).get("top_e_delta", [])
    t6_top_n = explain.get("table6", {}).get("top_n_delta", [])
    findings = anomaly.get("findings", [])

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>报表智能看板 - {explain.get('target_label','')}</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif; margin: 20px; color:#222; }}
    h1,h2 {{ margin: 8px 0; }}
    .meta {{ color:#666; margin-bottom:16px; }}
    .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:16px; }}
    .card {{ border:1px solid #ddd; border-radius:10px; padding:12px; background:#fff; }}
    .kpi {{ display:flex; gap:12px; }}
    .pill {{ padding:6px 10px; border-radius:999px; font-weight:600; }}
    .ok {{ background:#e8f5e9; color:#1b5e20; }}
    .warn {{ background:#fff8e1; color:#8a6d00; }}
    .err {{ background:#ffebee; color:#b71c1c; }}
    .bar-row {{ display:grid; grid-template-columns: 150px 1fr 120px; gap:8px; align-items:center; margin:6px 0; }}
    .bar-track {{ height:10px; background:#f0f0f0; border-radius:999px; overflow:hidden; }}
    .bar {{ height:100%; }}
    .bar.pos {{ background:#2e7d32; }}
    .bar.neg {{ background:#c62828; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ border:1px solid #e5e5e5; padding:6px; text-align:left; }}
    th {{ background:#fafafa; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} .bar-row {{ grid-template-columns: 120px 1fr 90px; }} }}
  </style>
</head>
<body>
  <h1>月度智能看板</h1>
  <div class="meta">对比区间：{explain.get('prev_label','')} → {explain.get('target_label','')}</div>
  <div class="kpi">
    <div class="pill ok">异常错误: {anomaly.get('summary',{}).get('errors',0)}</div>
    <div class="pill warn">异常预警: {anomaly.get('summary',{}).get('warns',0)}</div>
    <div class="pill">检查总数: {anomaly.get('summary',{}).get('total',0)}</div>
  </div>
  <div class="grid" style="margin-top:12px;">
    <div class="card">
      <h2>表5全国关键变化</h2>
      <table>
        <thead><tr><th>列</th><th>上月</th><th>本月</th><th>变化</th><th>环比</th></tr></thead>
        <tbody>{table_rows(t5_nat, ['col','previous','current','delta','ratio'])}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>表5省份变化Top（C列）</h2>
      {bar_rows(t5_top, 'delta', 'name')}
    </div>
    <div class="card">
      <h2>表6终端总数变化Top（E列）</h2>
      {bar_rows(t6_top_e, 'delta', 'name')}
    </div>
    <div class="card">
      <h2>表6辅助终端变化Top（N列）</h2>
      {bar_rows(t6_top_n, 'delta', 'name')}
    </div>
    <div class="card" style="grid-column: 1 / -1;">
      <h2>异常明细（Top 20）</h2>
      <table>
        <thead><tr><th>级别</th><th>模块</th><th>描述</th><th>位置</th><th>上月</th><th>本月</th><th>环比</th></tr></thead>
        <tbody>{table_rows(findings[:20], ['severity','section','message','row','previous','current','delta_ratio'])}</tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""

    out = Path(args.out_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"out={out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path


RULES = [
    {
        "id": "PY001",
        "severity": "high",
        "desc": "Python subprocess 使用 shell=True",
        "glob": "*.py",
        "regex": re.compile(r"subprocess\.(run|Popen|check_output|check_call)\([^\n]*shell\s*=\s*True"),
    },
    {
        "id": "PY002",
        "severity": "high",
        "desc": "Python 使用 eval/exec",
        "glob": "*.py",
        "regex": re.compile(r"\b(eval|exec)\s*\("),
    },
    {
        "id": "PY003",
        "severity": "high",
        "desc": "Python 使用 pickle 反序列化",
        "glob": "*.py",
        "regex": re.compile(r"pickle\.loads?\s*\("),
    },
    {
        "id": "PY004",
        "severity": "medium",
        "desc": "Python 使用 yaml.load（建议 SafeLoader）",
        "glob": "*.py",
        "regex": re.compile(r"yaml\.load\s*\("),
    },
    {
        "id": "SH001",
        "severity": "high",
        "desc": "Shell 中出现 eval",
        "glob": "*.sh",
        "regex": re.compile(r"(^|[^A-Za-z0-9_-])eval([^A-Za-z0-9_-]|$)"),
    },
    {
        "id": "SH002",
        "severity": "high",
        "desc": "Shell 出现 curl|bash 或 curl|sh",
        "glob": "*.sh",
        "regex": re.compile(r"curl[^\n]*\|[^\n]*(bash|sh)"),
    },
    {
        "id": "SH003",
        "severity": "medium",
        "desc": "Shell 直接 source .env",
        "glob": "*.sh",
        "regex": re.compile(r"source\s+[^\n]*\.env"),
    },
]

SEVERITY_SCORE = {"high": 5, "medium": 2, "low": 1}


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def finding_key(item: dict) -> str:
    raw = "|".join(
        [
            item.get("rule_id", ""),
            item.get("file", ""),
            str(item.get("line", "")),
            item.get("snippet", ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def should_skip(path: Path):
    if path.name == "security_audit.py":
        return True
    parts = set(path.parts)
    if ".git" in parts:
        return True
    if "日志" in parts:
        return True
    if "知识库" in parts:
        return True
    if "产出" in parts:
        return True
    if "__pycache__" in parts:
        return True
    return False


def collect_targets(root: Path):
    targets = []
    for p in root.rglob("*"):
        if not p.is_file() or should_skip(p):
            continue
        if p.suffix in {".py", ".sh"}:
            targets.append(p)
    return sorted(targets)


def scan_file(path: Path):
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for rule in RULES:
            if path.match(rule["glob"]) and rule["regex"].search(line):
                item = {
                    "rule_id": rule["id"],
                    "severity": rule["severity"],
                    "description": rule["desc"],
                    "file": str(path),
                    "line": idx,
                    "snippet": stripped[:180],
                }
                item["finding_key"] = finding_key(item)
                findings.append(item)
    return findings


def summarize(findings):
    high = sum(1 for f in findings if f["severity"] == "high")
    medium = sum(1 for f in findings if f["severity"] == "medium")
    low = sum(1 for f in findings if f["severity"] == "low")
    score = sum(SEVERITY_SCORE.get(f["severity"], 1) for f in findings)
    return {"high": high, "medium": medium, "low": low, "score": score, "total": len(findings)}


def load_baseline(path: Path):
    if not path.exists():
        return {"ignore_keys": []}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"ignore_keys": []}
    if not isinstance(obj, dict):
        return {"ignore_keys": []}
    keys = obj.get("ignore_keys", [])
    if not isinstance(keys, list):
        keys = []
    return {"ignore_keys": [str(x) for x in keys if str(x).strip()]}


def latest_report_json(out_dir: Path):
    reports = sorted(out_dir.glob("security_audit_*.json"), key=lambda p: p.name)
    return reports[-1] if reports else None


def load_prev_unresolved_keys(report_path: Path):
    if report_path is None or not report_path.exists():
        return set()
    try:
        obj = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    items = obj.get("unresolved_findings", [])
    if not isinstance(items, list):
        return set()
    keys = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        k = it.get("finding_key")
        if k:
            keys.add(str(k))
    return keys


def write_report(out_dir: Path, root: Path, report: dict):
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    json_path = out_dir / f"security_audit_{day}.json"
    md_path = out_dir / f"security_audit_{day}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = report["summary"]
    lines = [f"# 安全审计报告 | {day}", ""]
    lines.append(f"- 扫描目录: {root}")
    lines.append(f"- 发现总数(全部): {summary['total_all']}")
    lines.append(f"- 忽略基线: {summary['ignored_by_baseline']}")
    lines.append(f"- 未解决总数: {summary['total_unresolved']}")
    lines.append(f"- high: {summary['high']}")
    lines.append(f"- medium: {summary['medium']}")
    lines.append(f"- low: {summary['low']}")
    lines.append(f"- 风险分: {summary['score']}")
    lines.append(f"- 新增问题: {summary['new_findings']}")
    lines.append(f"- 已解决问题: {summary['resolved_findings']}")
    lines.append("")

    lines.append("## 新增问题")
    lines.append("")
    if report["new_findings"]:
        for f in report["new_findings"][:100]:
            lines.append(f"- [{f['severity']}] {f['rule_id']} {f['file']}:{f['line']} | `{f['snippet']}`")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## 未解决问题")
    lines.append("")
    if report["unresolved_findings"]:
        for f in report["unresolved_findings"][:200]:
            lines.append(f"- [{f['severity']}] {f['rule_id']} {f['file']}:{f['line']} | `{f['snippet']}`")
    else:
        lines.append("- 无高风险模式命中")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-dir", default="日志/安全审计")
    parser.add_argument("--baseline", default=".security_audit_baseline.json")
    parser.add_argument("--strict", action="store_true", help="存在 high 级未解决问题时返回非零")
    parser.add_argument("--update-baseline", action="store_true", help="将当前问题写入 baseline")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir)
    baseline_path = Path(args.baseline)
    if not baseline_path.is_absolute():
        baseline_path = root / baseline_path

    prev_path = latest_report_json(out_dir)
    prev_keys = load_prev_unresolved_keys(prev_path)

    targets = collect_targets(root)
    all_findings = []
    for path in targets:
        all_findings.extend(scan_file(path))

    baseline = load_baseline(baseline_path)
    ignore_set = set(baseline["ignore_keys"])

    unresolved = [f for f in all_findings if f["finding_key"] not in ignore_set]
    unresolved_keys = {f["finding_key"] for f in unresolved}

    new_keys = unresolved_keys - prev_keys
    resolved_keys = prev_keys - unresolved_keys

    new_findings = [f for f in unresolved if f["finding_key"] in new_keys]
    stats_unresolved = summarize(unresolved)

    report = {
        "generated_at": now(),
        "root": str(root),
        "baseline": str(baseline_path),
        "summary": {
            "total_all": len(all_findings),
            "ignored_by_baseline": len(all_findings) - len(unresolved),
            "total_unresolved": stats_unresolved["total"],
            "high": stats_unresolved["high"],
            "medium": stats_unresolved["medium"],
            "low": stats_unresolved["low"],
            "score": stats_unresolved["score"],
            "new_findings": len(new_keys),
            "resolved_findings": len(resolved_keys),
        },
        "all_findings": all_findings,
        "unresolved_findings": unresolved,
        "new_findings": new_findings,
        "resolved_finding_keys": sorted(resolved_keys),
    }

    md_path, json_path = write_report(out_dir, root, report)

    if args.update_baseline:
        merged = sorted(ignore_set | unresolved_keys)
        baseline_path.write_text(
            json.dumps({"updated_at": now(), "ignore_keys": merged}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        "security_audit: "
        f"all={len(all_findings)}, unresolved={stats_unresolved['total']}, "
        f"high={stats_unresolved['high']}, new={len(new_keys)}, resolved={len(resolved_keys)}, score={stats_unresolved['score']}"
    )
    print(f"report_md={md_path}")
    print(f"report_json={json_path}")
    print(f"baseline={baseline_path}")

    if args.strict and stats_unresolved["high"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

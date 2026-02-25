#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path


TIME_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$")


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def discover_files(import_dir: Path):
    if not import_dir.exists():
        return []
    files = sorted(import_dir.glob("*.csv")) + sorted(import_dir.glob("*.jsonl"))
    return files


def pick(obj: dict, *keys):
    for k in keys:
        if k in obj and obj[k] is not None and str(obj[k]).strip() != "":
            return obj[k]
    return ""


def to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def read_rows(path: Path):
    rows = []
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
    elif path.suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def check_file(path: Path):
    rows = read_rows(path)
    total = len(rows)
    if total == 0:
        return {
            "file": str(path),
            "rows": 0,
            "issues": [("empty_file", "ERROR", "文件为空或无法解析")],
            "stats": {},
        }

    miss_time = miss_metric = non_numeric_value = bad_time = duplicate = 0
    keys = set()

    for row in rows:
        event_time = str(pick(row, "event_time", "timestamp")).strip()
        metric = str(pick(row, "metric", "event", "type")).strip()
        value = pick(row, "value", "amount")
        entity = str(pick(row, "entity_id", "user_id", "id")).strip()

        if not event_time:
            miss_time += 1
        elif not TIME_RE.match(event_time):
            bad_time += 1

        if not metric:
            miss_metric += 1

        if to_float(value) is None:
            non_numeric_value += 1

        dedup_key = (event_time, entity, metric, str(value))
        if dedup_key in keys:
            duplicate += 1
        else:
            keys.add(dedup_key)

    issues = []

    def ratio(n):
        return n / max(total, 1)

    if ratio(miss_time) > 0.01:
        issues.append(("missing_event_time", "ERROR", f"event_time 缺失率 {ratio(miss_time):.2%}"))
    elif miss_time > 0:
        issues.append(("missing_event_time", "WARN", f"event_time 缺失率 {ratio(miss_time):.2%}"))

    if ratio(miss_metric) > 0.01:
        issues.append(("missing_metric", "ERROR", f"metric 缺失率 {ratio(miss_metric):.2%}"))
    elif miss_metric > 0:
        issues.append(("missing_metric", "WARN", f"metric 缺失率 {ratio(miss_metric):.2%}"))

    if ratio(non_numeric_value) > 0.05:
        issues.append(("non_numeric_value", "ERROR", f"value 非数值率 {ratio(non_numeric_value):.2%}"))
    elif non_numeric_value > 0:
        issues.append(("non_numeric_value", "WARN", f"value 非数值率 {ratio(non_numeric_value):.2%}"))

    if ratio(bad_time) > 0.02:
        issues.append(("bad_time_format", "ERROR", f"时间格式异常率 {ratio(bad_time):.2%}"))
    elif bad_time > 0:
        issues.append(("bad_time_format", "WARN", f"时间格式异常率 {ratio(bad_time):.2%}"))

    if ratio(duplicate) > 0.2:
        issues.append(("high_duplicate", "ERROR", f"重复率 {ratio(duplicate):.2%}"))
    elif duplicate > 0:
        issues.append(("high_duplicate", "WARN", f"重复率 {ratio(duplicate):.2%}"))

    return {
        "file": str(path),
        "rows": total,
        "issues": issues,
        "stats": {
            "missing_event_time": miss_time,
            "missing_metric": miss_metric,
            "non_numeric_value": non_numeric_value,
            "bad_time": bad_time,
            "duplicate": duplicate,
        },
    }


def gate(import_dir: Path, out_dir: Path, strict: bool):
    files = discover_files(import_dir)
    checks = [check_file(f) for f in files]

    total_rows = sum(c["rows"] for c in checks)
    issues = []
    for c in checks:
        for item in c["issues"]:
            issues.append({"file": c["file"], "check": item[0], "severity": item[1], "details": item[2]})

    errors = [x for x in issues if x["severity"] == "ERROR"]
    warns = [x for x in issues if x["severity"] == "WARN"]

    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    md_path = out_dir / f"quality_gate_{day}.md"
    js_path = out_dir / f"quality_gate_{day}.json"

    payload = {
        "generated_at": now(),
        "import_dir": str(import_dir),
        "file_count": len(files),
        "total_rows": total_rows,
        "error_count": len(errors),
        "warn_count": len(warns),
        "files": checks,
        "issues": issues,
    }
    js_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [f"# DataHub 入库门控报告 | {day}", ""]
    lines.append(f"- import_dir: {import_dir}")
    lines.append(f"- file_count: {len(files)}")
    lines.append(f"- total_rows: {total_rows}")
    lines.append(f"- error_count: {len(errors)}")
    lines.append(f"- warn_count: {len(warns)}")
    lines.append("")
    lines.append("## 文件检查")
    lines.append("")
    if checks:
        for c in checks:
            lines.append(f"- {c['file']} | rows={c['rows']} | issues={len(c['issues'])}")
    else:
        lines.append("- 无导入文件")

    lines.append("")
    lines.append("## 问题明细")
    lines.append("")
    if issues:
        for x in issues[:200]:
            lines.append(f"- [{x['severity']}] {x['file']} | {x['check']} | {x['details']}")
    else:
        lines.append("- [OK] 无门控问题")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        f"quality_gate: files={len(files)}, rows={total_rows}, errors={len(errors)}, warns={len(warns)}"
    )
    print(f"report_md={md_path}")
    print(f"report_json={js_path}")

    if strict and errors:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--import-dir", default="私有数据/import")
    parser.add_argument("--out-dir", default="日志/datahub_quality_gate")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    gate(Path(args.import_dir), Path(args.out_dir), args.strict)


if __name__ == "__main__":
    main()

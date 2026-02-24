#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
from pathlib import Path


def load_experiments(path):
    p = Path(path)
    if not p.exists():
        return {"updated_at": "", "experiments": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"updated_at": "", "experiments": []}
    if not isinstance(data, dict):
        return {"updated_at": "", "experiments": []}
    exps = data.get("experiments")
    if not isinstance(exps, list):
        exps = []
    data["experiments"] = exps
    return data


def latest_metrics(metrics_dir):
    p = Path(metrics_dir)
    if not p.exists():
        return "", ""
    files = sorted(p.glob("*.md"))
    if not files:
        return "", ""
    txt = files[-1].read_text(encoding="utf-8", errors="ignore")
    c = re.search(r"任务完成率:\s*([0-9]+(?:\.[0-9]+)?)%", txt)
    s = re.search(r"自动化成功率\(非ERROR\):\s*([0-9]+(?:\.[0-9]+)?)%", txt)
    return (float(c.group(1)) if c else 100.0, float(s.group(1)) if s else 100.0)


def eval_exp(exp, completion, success):
    metric = exp.get("metric", "completion_rate")
    if metric == "automation_success_rate":
        val = success
        pass_cond = val >= 97
    else:
        val = completion
        pass_cond = val >= 90

    if pass_cond:
        status = "won"
    elif val >= 85:
        status = "running"
    else:
        status = "lost"
    return val, status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments-file", default="目标系统/experiments.json")
    parser.add_argument("--metrics-dir", default="日志/指标")
    parser.add_argument("--out-dir", default="日志/实验评估")
    args = parser.parse_args()

    store = load_experiments(args.experiments_file)
    completion, success = latest_metrics(args.metrics_dir)

    won = lost = running = 0
    for exp in store["experiments"]:
        if exp.get("status") == "planned":
            exp["status"] = "running"
        val, status = eval_exp(exp, completion, success)
        exp["last_value"] = round(val, 1)
        if status == "won":
            exp["status"] = "won"
            won += 1
        elif status == "lost":
            exp["status"] = "lost"
            lost += 1
        else:
            running += 1

    store["updated_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = Path(args.experiments_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 实验评估 | {day}", ""]
    lines.append(f"- completion_rate: {completion:.1f}%")
    lines.append(f"- automation_success_rate: {success:.1f}%")
    lines.append("")
    lines.append(f"- won: {won}")
    lines.append(f"- running: {running}")
    lines.append(f"- lost: {lost}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"实验评估已生成: {out}")
    print(f"won={won},running={running},lost={lost}")


if __name__ == "__main__":
    main()

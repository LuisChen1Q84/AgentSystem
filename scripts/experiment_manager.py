#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
from pathlib import Path


def load_or_init(path):
    p = Path(path)
    if not p.exists():
        return {"updated_at": "", "experiments": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"updated_at": "", "experiments": []}
    if not isinstance(data, dict):
        return {"updated_at": "", "experiments": []}
    if "experiments" not in data or not isinstance(data["experiments"], list):
        data["experiments"] = []
    return data


def next_id(existing):
    if not existing:
        return "EXP-001"
    nums = []
    for x in existing:
        m = re.match(r"EXP-(\d+)$", str(x.get("id", "")))
        if m:
            nums.append(int(m.group(1)))
    n = max(nums) + 1 if nums else 1
    return f"EXP-{n:03d}"


def parse_top_action(decision_file):
    p = Path(decision_file)
    if not p.exists():
        return "维持当前节奏并执行主题流水线"
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("| 1 |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 3:
                return cells[2]
    return "维持当前节奏并执行主题流水线"


def suggest_experiment(top_action, policy_file):
    focus = "平衡推进"
    p = Path(policy_file)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            focus = data.get("execution", {}).get("daily_focus", focus)
        except json.JSONDecodeError:
            pass

    if "修复" in top_action or "清零" in top_action:
        return {
            "title": "错误率下降实验",
            "hypothesis": "优先修复失败动作TOP1后，7天自动化成功率提升到97%以上",
            "metric": "automation_success_rate",
            "target": ">=97%",
            "window_days": 7,
            "owner": "system",
            "focus": focus,
        }

    return {
        "title": "产能提升实验",
        "hypothesis": "按WIP上限执行并聚焦高价值任务，7天任务完成率提升",
        "metric": "completion_rate",
        "target": ">=90%",
        "window_days": 7,
        "owner": "system",
        "focus": focus,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-file", default="")
    parser.add_argument("--policy-file", default="目标系统/optimization_policy.json")
    parser.add_argument("--experiments-file", default="目标系统/experiments.json")
    parser.add_argument("--out-dir", default="日志/实验")
    args = parser.parse_args()

    store = load_or_init(args.experiments_file)
    top_action = parse_top_action(args.decision_file)
    exp = suggest_experiment(top_action, args.policy_file)
    exp["id"] = next_id(store["experiments"])
    exp["status"] = "planned"
    exp["created_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    store["experiments"].append(exp)
    store["updated_at"] = exp["created_at"]

    target = Path(args.experiments_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{today}.md"

    lines = [f"# 实验计划 | {today}", ""]
    lines.append("## 新增实验")
    lines.append("")
    lines.append(f"- ID: {exp['id']}")
    lines.append(f"- 标题: {exp['title']}")
    lines.append(f"- 假设: {exp['hypothesis']}")
    lines.append(f"- 指标: {exp['metric']}")
    lines.append(f"- 目标: {exp['target']}")
    lines.append(f"- 周期: {exp['window_days']}天")
    lines.append(f"- 当前焦点: {exp['focus']}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"实验计划已生成: {out}")
    print(f"experiment_id={exp['id']}")


if __name__ == "__main__":
    main()

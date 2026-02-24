#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


RISK_KEYS = ["agentsys.sh", "checks.sh", "task_store.py", "knowledge_index.py"]


def changed_files(root):
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    except Exception:
        return []
    files = []
    for line in out.splitlines():
        if len(line) >= 4:
            files.append(line[3:].strip())
    return files


def risk_score(files):
    score = 0
    score += min(len(files), 20)
    for f in files:
        if any(k in f for k in RISK_KEYS):
            score += 8
        if f.endswith(".sh"):
            score += 2
        if f.endswith(".py"):
            score += 1
    return score


def decide(score):
    if score >= 40:
        return "hold", "高风险，建议人工审核后发布"
    if score >= 20:
        return "canary", "中风险，建议灰度发布"
    return "auto", "低风险，可自动发布"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--state-file", default="目标系统/release_state.json")
    parser.add_argument("--out-dir", default="日志/发布控制")
    args = parser.parse_args()

    root = Path(args.root)
    files = changed_files(root)
    score = risk_score(files)
    mode, reason = decide(score)

    state = {
        "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "risk_score": score,
        "mode": mode,
        "reason": reason,
        "changed_files": files[:100],
    }

    st = Path(args.state_file)
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 发布控制报告 | {day}", ""]
    lines.append(f"- risk_score: {score}")
    lines.append(f"- mode: {mode}")
    lines.append(f"- reason: {reason}")
    lines.append(f"- state_file: {st}")
    lines.append("")
    lines.append("## 变更文件")
    lines.append("")
    if files:
        for f in files[:50]:
            lines.append(f"- {f}")
    else:
        lines.append("- (无工作区变更)")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"发布控制报告已生成: {out}")
    print(f"release_mode={mode}")


if __name__ == "__main__":
    main()

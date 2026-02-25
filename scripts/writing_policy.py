#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List


DEFAULT_POLICY = {
    "global": {"hard": [], "soft": [], "replacements": {}},
    "session": {"hard": [], "soft": [], "replacements": {}, "auto_confirm_on_topic_shift": True},
    "last_task": {"hard": [], "soft": [], "replacements": {}, "topic": "", "updated_at": ""},
}


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_csv_list(s: str) -> List[str]:
    if not s:
        return []
    out = []
    for x in s.split(","):
        v = x.strip()
        if v:
            out.append(v)
    return out


def parse_replacements(s: str) -> Dict[str, str]:
    if not s:
        return {}
    out: Dict[str, str] = {}
    for part in s.split(";"):
        p = part.strip()
        if not p or "->" not in p:
            continue
        src, dst = p.split("->", 1)
        src = src.strip()
        dst = dst.strip()
        if src:
            out[src] = dst
    return out


def load_policy(path: Path) -> dict:
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_POLICY))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(DEFAULT_POLICY))
    if not isinstance(raw, dict):
        return json.loads(json.dumps(DEFAULT_POLICY))

    out = json.loads(json.dumps(DEFAULT_POLICY))
    for layer in ("global", "session", "last_task"):
        obj = raw.get(layer, {})
        if isinstance(obj, dict):
            out[layer]["hard"] = [str(x) for x in obj.get("hard", []) if str(x).strip()]
            out[layer]["soft"] = [str(x) for x in obj.get("soft", []) if str(x).strip()]
            repl = obj.get("replacements", {})
            if isinstance(repl, dict):
                out[layer]["replacements"] = {str(k): str(v) for k, v in repl.items()}
    out["session"]["auto_confirm_on_topic_shift"] = bool(
        raw.get("session", {}).get("auto_confirm_on_topic_shift", True)
    )
    out["last_task"]["topic"] = str(raw.get("last_task", {}).get("topic", ""))
    out["last_task"]["updated_at"] = str(raw.get("last_task", {}).get("updated_at", ""))
    return out


def save_policy(path: Path, policy: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_rules(base: dict, overlay: dict) -> dict:
    out = {
        "hard": list(base.get("hard", [])),
        "soft": list(base.get("soft", [])),
        "replacements": dict(base.get("replacements", {})),
    }
    for term in overlay.get("hard", []):
        if term not in out["hard"]:
            out["hard"].append(term)
    for term in overlay.get("soft", []):
        if term not in out["soft"]:
            out["soft"].append(term)
    out["replacements"].update(overlay.get("replacements", {}))
    return out


def resolve_effective_rules(policy: dict, topic: str = "", task_override: dict | None = None) -> dict:
    effective = {"hard": [], "soft": [], "replacements": {}}
    effective = merge_rules(effective, policy.get("global", {}))
    effective = merge_rules(effective, policy.get("session", {}))
    effective = merge_rules(effective, policy.get("last_task", {}))

    has_task_override = bool(task_override and (task_override.get("hard") or task_override.get("soft") or task_override.get("replacements")))
    if has_task_override:
        effective = merge_rules(effective, task_override)

    last_topic = str(policy.get("last_task", {}).get("topic", "")).strip()
    cur_topic = (topic or "").strip()
    topic_shift = bool(cur_topic and last_topic and cur_topic != last_topic)
    prompt_recommended = bool(
        topic_shift
        and not has_task_override
        and bool(policy.get("session", {}).get("auto_confirm_on_topic_shift", True))
    )

    return {
        "effective": effective,
        "meta": {
            "topic": cur_topic,
            "last_topic": last_topic,
            "topic_shift": topic_shift,
            "prompt_recommended": prompt_recommended,
            "has_task_override": has_task_override,
        },
    }


def set_layer(policy: dict, layer: str, hard: List[str], soft: List[str], replacements: Dict[str, str], topic: str = ""):
    policy[layer]["hard"] = hard
    policy[layer]["soft"] = soft
    policy[layer]["replacements"] = replacements
    if layer == "last_task":
        policy[layer]["topic"] = topic or ""
        policy[layer]["updated_at"] = now()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="config/writing_policy.json")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show")
    sub.add_parser("clear-task")

    for name in ("set-global", "set-session", "set-task"):
        sp = sub.add_parser(name)
        sp.add_argument("--hard", default="")
        sp.add_argument("--soft", default="")
        sp.add_argument("--replace", default="", help="格式: 词A->替换A;词B->替换B")
        if name == "set-task":
            sp.add_argument("--topic", default="")

    rp = sub.add_parser("resolve")
    rp.add_argument("--topic", default="")
    rp.add_argument("--task-hard", default="")
    rp.add_argument("--task-soft", default="")
    rp.add_argument("--task-replace", default="")

    args = parser.parse_args()
    policy_path = Path(args.file)
    policy = load_policy(policy_path)

    if args.cmd == "show":
        print(json.dumps(policy, ensure_ascii=False, indent=2))
        return

    if args.cmd == "clear-task":
        set_layer(policy, "last_task", [], [], {}, topic="")
        save_policy(policy_path, policy)
        print(f"writing_policy task 层已清空: {policy_path}")
        return

    if args.cmd in {"set-global", "set-session", "set-task"}:
        layer = {"set-global": "global", "set-session": "session", "set-task": "last_task"}[args.cmd]
        hard = parse_csv_list(args.hard)
        soft = parse_csv_list(args.soft)
        repl = parse_replacements(args.replace)
        topic = getattr(args, "topic", "")
        set_layer(policy, layer, hard, soft, repl, topic=topic)
        save_policy(policy_path, policy)
        print(f"writing_policy 更新成功: layer={layer}, file={policy_path}")
        return

    if args.cmd == "resolve":
        override = {
            "hard": parse_csv_list(args.task_hard),
            "soft": parse_csv_list(args.task_soft),
            "replacements": parse_replacements(args.task_replace),
        }
        res = resolve_effective_rules(policy, topic=args.topic, task_override=override)
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

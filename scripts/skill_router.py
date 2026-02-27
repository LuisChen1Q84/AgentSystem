#!/usr/bin/env python3
"""Executable skill router bridge based on 工作流/技能路由.md."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

BOOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

try:
    from core.skill_intelligence import build_loop_closure
    from core.skill_guard import SkillQualityGuard
    from scripts import autonomy_generalist
    from scripts import mckinsey_ppt_engine
    from scripts.mcp_connector import Registry, Runtime, parse_params
    from scripts.image_creator_hub import load_cfg as load_image_hub_cfg
    from scripts.image_creator_hub import run_request as run_image_hub_request
    from scripts.stock_market_hub import run_report as run_stock_hub_report
    from scripts.stock_market_hub import load_cfg as load_stock_hub_cfg
    from scripts.stock_market_hub import pick_symbols as pick_stock_symbols
    from scripts.skill_parser import parse_all_skills, match_triggers, extract_parameters
    from scripts.skill_tracer import SkillTracer
except ModuleNotFoundError:  # direct script execution
    from core.skill_intelligence import build_loop_closure
    from core.skill_guard import SkillQualityGuard
    import autonomy_generalist  # type: ignore
    import mckinsey_ppt_engine  # type: ignore
    from mcp_connector import Registry, Runtime, parse_params
    from image_creator_hub import load_cfg as load_image_hub_cfg  # type: ignore
    from image_creator_hub import run_request as run_image_hub_request  # type: ignore
    from stock_market_hub import run_report as run_stock_hub_report  # type: ignore
    from stock_market_hub import load_cfg as load_stock_hub_cfg  # type: ignore
    from stock_market_hub import pick_symbols as pick_stock_symbols  # type: ignore
    from skill_parser import parse_all_skills, match_triggers, extract_parameters  # type: ignore
    from skill_tracer import SkillTracer  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
ROUTE_DOC = ROOT / "工作流" / "技能路由.md"
STOCK_HUB_CFG = ROOT / "config" / "stock_market_hub.toml"
IMAGE_HUB_CFG = ROOT / "config" / "image_creator_hub.toml"

# 技能追踪器
TRACER = SkillTracer()
GUARD = SkillQualityGuard()

STRONG_EXEC_KEYWORDS = {"xlsx", "excel", "表1", "表2", "填报日期", "更新这张表", "直接修改原文件"}
PLAN_WORDS = {"计划", "打算", "准备"}
SECTION_BONUS = {
    "MCP连接类": 3,
    "文档处理类": 2,
}
MARKET_WORDS = {
    "etf",
    "index",
    "stock",
    "kline",
    "support",
    "resistance",
    "buy",
    "sell",
    "指数",
    "行情",
    "k线",
    "恒生科技",
    "513180",
    "买卖点",
    "支撑",
    "压力",
}
IMAGE_WORDS = {
    "图像",
    "图片",
    "生成图",
    "海报",
    "手办",
    "肖像",
    "q版",
    "chibi",
    "城市微缩",
    "地标",
    "场景",
    "电影场景",
    "logo",
    "品牌店铺",
    "产品广告",
    "低多边形",
    "knolling",
    "表情包转3d",
    "裸眼3d",
}


class SkillRouterError(RuntimeError):
    pass


def _split_keywords(text: str) -> List[str]:
    parts = re.split(r"[、,，/\s]+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def parse_route_doc(path: Path = ROUTE_DOC) -> List[Dict[str, Any]]:
    if not path.exists():
        raise SkillRouterError(f"route doc not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()

    rules: List[Dict[str, Any]] = []
    section = ""
    in_table = False
    for line in lines:
        if line.startswith("### "):
            section = line.replace("### ", "").strip()
            in_table = False
            continue
        if line.strip().startswith("| 需求关键词"):
            in_table = True
            continue
        if in_table and line.strip().startswith("|-----------"):
            continue
        if in_table and line.strip().startswith("|"):
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) < 3:
                continue
            keywords = _split_keywords(cols[0])
            skill = cols[1]
            desc = cols[2]
            rules.append({"section": section, "keywords": keywords, "skill": skill, "description": desc})
            continue
        if in_table and line.strip() == "":
            in_table = False
    return rules


def route_text(text: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    low = text.lower()

    if any(k in low for k in STRONG_EXEC_KEYWORDS):
        return {
            "section": "冲突消解（新增）",
            "skill": "minimax-xlsx",
            "description": "强优先执行类",
            "keywords": [k for k in STRONG_EXEC_KEYWORDS if k in low],
            "score": 100,
        }

    if any(w in low for w in MARKET_WORDS):
        return {
            "section": "市场量化类",
            "skill": "stock-market-hub + mcp-freefirst",
            "description": "全球股票市场分析 + 量化回测 + 免费信源抓取",
            "keywords": [w for w in MARKET_WORDS if w in low],
            "score": 90,
        }

    if any(w in low for w in IMAGE_WORDS):
        return {
            "section": "图像创作类",
            "skill": "image-creator-hub",
            "description": "多子代理图像生成中枢",
            "keywords": [w for w in IMAGE_WORDS if w in low],
            "score": 88,
        }

    plan_hits = [w for w in PLAN_WORDS if w in low]
    best: Tuple[int, Dict[str, Any]] | None = None
    for rule in rules:
        hits = [k for k in rule["keywords"] if k.lower() in low]
        if not hits:
            continue
        score = len(hits) + SECTION_BONUS.get(rule["section"], 0)
        if plan_hits and any(k in low for k in STRONG_EXEC_KEYWORDS):
            score += 1
        cand = {
            "section": rule["section"],
            "skill": rule["skill"],
            "description": rule["description"],
            "keywords": hits,
            "score": score,
        }
        if best is None or score > best[0]:
            best = (score, cand)

    if best is not None:
        return best[1]

    return {
        "section": "默认行为",
        "skill": "clarify",
        "description": "需要澄清需求",
        "keywords": [],
        "score": 0,
    }


def route_text_enhanced(text: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    增强版路由：结合传统规则匹配 + 技能元数据触发匹配
    """
    # 1. 优先使用技能解析器的触发短语匹配
    try:
        skills = parse_all_skills(silent=True)
        trigger_matches = match_triggers(text, skills)

        if trigger_matches:
            # 使用最高分的触发匹配结果
            best_match = trigger_matches[0]
            skill_name = best_match["skill"]

            # 尝试提取参数
            skill_obj = next((s for s in skills if s.name == skill_name), None)
            params = {}
            if skill_obj:
                params = extract_parameters(text, skill_obj)

            return {
                "section": "技能元数据触发",
                "skill": skill_name,
                "description": f"通过触发短语匹配 (score: {best_match['score']})",
                "keywords": best_match["matched_triggers"],
                "score": best_match["score"] + 20,  # 触发匹配优先权更高
                "params": params,  # 提取的参数
                "calls": skill_obj.calls if skill_obj else [],  # 技能链
            }
    except Exception:
        # 如果解析失败，回退到传统路由
        pass

    # 2. 回退到传统规则匹配
    return route_text(text, rules)


def _server_from_skill(skill: str) -> str:
    s = skill.lower()
    if "filesystem" in s:
        return "filesystem"
    if "fetch" in s:
        return "fetch"
    if "sqlite" in s:
        return "sqlite"
    if "postgres" in s:
        return "sqlite"
    if "github" in s:
        return "github"
    if "brave" in s:
        return "brave-search"
    return "sequential-thinking"


def _default_call(server: str, text: str) -> Tuple[str, Dict[str, Any]]:
    if server == "filesystem":
        return "list_dir", {"path": ".", "max_entries": 50}
    if server == "fetch":
        return "get", {"url": "https://www.gov.cn"}
    if server == "sqlite":
        return "query", {"sql": "SELECT name FROM sqlite_master LIMIT 20"}
    if server == "github":
        return "search_code", {"query": "repo:owner/repo TODO"}
    if server == "brave-search":
        return "search", {"query": text[:120] or "支付监管"}
    return "think", {"problem": text or "请拆解任务"}


def execute_route(text: str, params_json: str) -> Dict[str, Any]:
    import time
    start_time = time.time()

    rules = parse_route_doc()
    # 使用增强版路由（结合技能元数据触发匹配）
    route = route_text_enhanced(text, rules)
    skill = route["skill"]
    user_params = parse_params(params_json)
    autonomous_force = bool(user_params.get("autonomous", False) or user_params.get("generalist", False))

    # 记录路由追踪
    duration_ms = int((time.time() - start_time) * 1000)
    trace_id = TRACER.record_route(text, route, duration_ms)
    route["trace_id"] = trace_id

    # 自主模式：可显式强制，也可在 clarify 场景下自动接管
    if autonomous_force or skill == "clarify":
        exec_start = time.time()
        try:
            auto = autonomy_generalist.run_request(text, user_params)
            TRACER.record_execution(trace_id, "autonomy-generalist", bool(auto.get("ok", False)), duration_ms=int((time.time() - exec_start) * 1000))
            return {
                "route": route,
                "execute": {
                    "type": "autonomous-generalist",
                    "forced": autonomous_force,
                    "reason": "forced" if autonomous_force else "clarify_fallback",
                },
                "result": auto,
                "meta": {
                    "mode": "autonomous-generalist",
                    "next_actions": [
                        "补充任务约束可提升执行质量",
                        "将高质量结果沉淀为技能触发短语",
                    ],
                },
                "loop_closure": build_loop_closure(
                    skill="autonomy-generalist",
                    status="completed" if auto.get("ok") else "advisor",
                    reason="" if auto.get("ok") else "autonomy_failed",
                    evidence={"forced": autonomous_force, "candidates": len(auto.get("candidates", []))},
                    next_actions=["复盘本次策略命中并优化触发词"],
                ),
            }
        except Exception as e:
            TRACER.record_execution(trace_id, "autonomy-generalist", False, str(e), duration_ms=int((time.time() - exec_start) * 1000))
            if skill == "clarify":
                return {
                    "route": route,
                    "execute": {"type": "clarify", "message": "无法明确匹配技能，请补充目标和输入数据"},
                    "loop_closure": build_loop_closure(
                        skill=skill,
                        status="advisor",
                        reason="clarify_required",
                        evidence={"autonomy_error": str(e)},
                        next_actions=["补充目标、输入和期望输出格式"],
                    ),
                }
            raise

    guard = GUARD.decide(skill)
    route["quality_guard"] = guard.to_dict()

    # 在线质量守门：低分/低置信度技能自动降级为 advisor
    if not guard.allow_execute:
        return {
            "route": route,
            "execute": {
                "type": "advisor",
                "message": f"技能 {skill} 已被质量守门降级为建议模式",
                "reason": guard.reason,
            },
            "meta": {
                "mode": "advisor",
                "next_actions": [
                    "make skills-scorecard",
                    "make skills-optimize auto=1 close=1",
                ],
            },
            "loop_closure": build_loop_closure(
                skill=skill,
                status="advisor",
                reason=guard.reason,
                evidence={"quality_guard": guard.to_dict()},
                next_actions=["提升技能评分后再执行 operator 模式"],
            ),
        }

    if skill.startswith("stock-market-hub"):
        hub_cfg = load_stock_hub_cfg(STOCK_HUB_CFG)
        symbols = pick_stock_symbols(hub_cfg, text, str(user_params.get("symbols", "")))
        universe = str(user_params.get("universe", "")).strip() or str(
            hub_cfg.get("defaults", {}).get("default_universe", "global_core")
        )
        no_sync = bool(user_params.get("no_sync", False))
        exec_start = time.time()
        try:
            hub = run_stock_hub_report(hub_cfg, text, universe, symbols, no_sync)
            TRACER.record_execution(trace_id, skill, True, duration_ms=int((time.time() - exec_start) * 1000))
            result = {
                "route": route,
                "execute": {"type": "stock-market-hub", "symbols": symbols, "universe": universe, "no_sync": no_sync},
                "result": hub,
                "meta": {
                    "mode": "free-first-global-stock",
                    "risk_tags": ["non_realtime", "public_web_sources_only", "not_investment_advice"],
                    "next_actions": [
                        "make stock-hub q='你的问题'",
                        "make stock-run universe='global_core' limit=30",
                        "make mcp-observe days=7",
                    ],
                },
                "loop_closure": build_loop_closure(
                    skill=skill,
                    status="completed",
                    evidence={"symbols": symbols, "universe": universe, "coverage_rate": hub.get("freefirst", {}).get("coverage_rate", 0)},
                    next_actions=["按质量闸门检查 limited/deep 模式"],
                ),
            }
            return result
        except Exception as e:
            TRACER.record_execution(trace_id, skill, False, str(e))
            raise

    if skill == "mckinsey-ppt":
        exec_start = time.time()
        try:
            result = mckinsey_ppt_engine.run_request(text, user_params)
            TRACER.record_execution(trace_id, skill, True, duration_ms=int((time.time() - exec_start) * 1000))
            return {
                "route": route,
                "execute": {"type": "mckinsey-ppt", "engine": "mckinsey_ppt_engine"},
                "result": result,
                "meta": {
                    "mode": "deck-spec",
                    "next_actions": [
                        "review deck_spec_*.json and fill evidence",
                        "convert spec to pptx in next step",
                    ],
                },
                "loop_closure": build_loop_closure(
                    skill=skill,
                    status="completed",
                    evidence={"assets": len(result.get("deliver_assets", {}).get("items", []))},
                    next_actions=["补齐关键数据证据后再进入视觉精修"],
                ),
            }
        except Exception as e:
            TRACER.record_execution(trace_id, skill, False, str(e), duration_ms=int((time.time() - exec_start) * 1000))
            raise

    if skill.startswith("image-creator-hub"):
        image_cfg = load_image_hub_cfg(IMAGE_HUB_CFG)
        exec_start = time.time()
        try:
            result = run_image_hub_request(image_cfg, text, user_params)
            TRACER.record_execution(trace_id, skill, True, duration_ms=int((time.time() - exec_start) * 1000))
            return {
                "route": route,
                "execute": {
                    "type": "image-creator-hub",
                    "config": str(IMAGE_HUB_CFG),
                },
                "result": result,
                "meta": {
                    "mode": "image-generation",
                    "next_actions": [
                        "make image-hub text='试试看低多边形风格'",
                        "make skill-execute text='给我做一个Q版品牌店铺图' params='{\"brand\":\"Nike\"}'",
                    ],
                },
                "loop_closure": build_loop_closure(
                    skill=skill,
                    status="generated" if result.get("ok") else "failed",
                    evidence={"backend": result.get("backend", ""), "mode": result.get("mode", ""), "guard": guard.to_dict()},
                    next_actions=["若效果不佳，补充 reference_image 或更换 style_id"],
                ),
            }
        except Exception as e:
            TRACER.record_execution(trace_id, skill, False, str(e))
            raise

    # Digest 模块处理
    if skill == "digest":
        import subprocess

        # 解析用户意图，决定执行什么命令
        text_lower = text.lower()

        # 判断操作类型（优先处理“采集/收集”，避免“采集新闻”被误判为show）
        if "采集" in text or "收集" in text:
            # 根据关键词选择预设源
            if "商业" in text or "business" in text_lower:
                preset = "business"
            elif "金融" in text or "finance" in text_lower:
                preset = "finance"
            elif "科技" in text or "tech" in text_lower:
                preset = "tech"
            elif "ai" in text_lower or "人工智能" in text:
                preset = "ai"
            else:
                preset = "business"  # 默认商业新闻
            cmd = ["python3", "scripts/digest/main.py", "collect", "rss", "--preset", preset, "--limit", "20"]
        elif "摘要" in text or "generate" in text_lower:
            cmd = ["python3", "scripts/digest/main.py", "digest", "generate", "--type", "daily"]
        elif "新闻" in text or "资讯" in text or "有什么" in text:
            cmd = ["python3", "scripts/digest/main.py", "digest", "show", "--type", "daily"]
        else:
            # 默认显示今日摘要
            cmd = ["python3", "scripts/digest/main.py", "digest", "show", "--type", "daily"]

        exec_start = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120
            )
            output = result.stdout if result.returncode == 0 else result.stderr
            if result.returncode == 0 and not output.strip():
                output = "暂无可展示的摘要或数据，请先执行采集或生成操作。"
            TRACER.record_execution(trace_id, skill, result.returncode == 0, None if result.returncode == 0 else output.strip(), duration_ms=int((time.time() - exec_start) * 1000))
        except subprocess.TimeoutExpired:
            output = "执行超时，请稍后再试"
            TRACER.record_execution(trace_id, skill, False, "timeout", duration_ms=int((time.time() - exec_start) * 1000))
        except Exception as e:
            output = f"执行错误: {str(e)}"
            TRACER.record_execution(trace_id, skill, False, str(e), duration_ms=int((time.time() - exec_start) * 1000))

        return {
            "route": route,
            "execute": {"type": "digest", "cmd": " ".join(cmd)},
            "result": output,
            "meta": {
                "mode": "digest",
                "next_actions": [
                    "make skill-execute text='生成本周摘要'",
                    "make skill-execute text='采集科技新闻'",
                ],
            },
            "loop_closure": build_loop_closure(
                skill=skill,
                status="completed" if isinstance(output, str) and "执行错误" not in output else "failed",
                evidence={"cmd": cmd},
                next_actions=["若摘要为空，先执行 collect 再 generate"],
            ),
        }

    if "mcp-connector" in skill:
        server = _server_from_skill(skill)
        tool, base_params = _default_call(server, text)
        base_params.update(user_params)
        if server == "filesystem" and "path" in base_params:
            p = Path(str(base_params["path"]))
            if p.suffix:
                tool = "read_file"
                base_params.pop("max_entries", None)

        runtime = Runtime(Registry())
        exec_start = time.time()
        try:
            result = runtime.call(server, tool, base_params, route_meta={"source": "skill-router", **route})
            TRACER.record_execution(trace_id, skill, True, duration_ms=int((time.time() - exec_start) * 1000))
        except Exception as e:
            TRACER.record_execution(trace_id, skill, False, str(e), duration_ms=int((time.time() - exec_start) * 1000))
            raise
        low = text.lower()
        market_mode = any(w in low for w in MARKET_WORDS)
        freefirst = {
            "mode": "free-first",
            "risk_tags": ["non_realtime", "public_web_sources_only"] if market_mode else ["public_web_sources_only"],
            "next_actions": [
                "make mcp-freefirst-sync q='你的问题'",
                "make mcp-freefirst-report",
            ] if market_mode else ["make mcp-observe days=7"],
        }
        return {
            "route": route,
            "execute": {"type": "mcp", "server": server, "tool": tool, "params": base_params},
            "result": result,
            "meta": freefirst,
            "loop_closure": build_loop_closure(
                skill=skill,
                status="completed",
                evidence={"server": server, "tool": tool, "quality_guard": guard.to_dict()},
                next_actions=["结果不足时切换更具体 skill 或补充 params-json"],
            ),
        }

    return {
        "route": route,
        "execute": {
            "type": "skill-hint",
            "message": f"命中技能 {skill}，建议进入对应工作流执行",
        },
        "loop_closure": build_loop_closure(
            skill=skill,
            status="ok",
            evidence={"quality_guard": guard.to_dict()},
            next_actions=["进入对应工作流并携带 params-json"],
        ),
    }


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Skill router executable bridge")
    sub = p.add_subparsers(dest="command")

    rt = sub.add_parser("route", help="route text")
    rt.add_argument("--text", required=True)

    ex = sub.add_parser("execute", help="route and execute")
    ex.add_argument("--text", required=True)
    ex.add_argument("--params-json", default="{}")

    au = sub.add_parser("autonomous", help="force autonomous-generalist execution")
    au.add_argument("--text", required=True)
    au.add_argument("--params-json", default="{}")

    sub.add_parser("dump", help="dump parsed rules")
    return p


def print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: List[str] | None = None) -> int:
    parser = build_cli()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2

    try:
        if args.command == "dump":
            print_json({"rules": parse_route_doc()})
            return 0
        if args.command == "route":
            print_json(route_text_enhanced(args.text, parse_route_doc()))
            return 0
        if args.command == "execute":
            print_json(execute_route(args.text, args.params_json))
            return 0
        if args.command == "autonomous":
            params = parse_params(args.params_json)
            params["autonomous"] = True
            print_json(autonomy_generalist.run_request(args.text, params))
            return 0
        raise SkillRouterError(f"unknown command: {args.command}")
    except Exception as e:
        print_json({"ok": False, "error": str(e), "trace": traceback.format_exc(limit=2)})
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Skill Tracer - 技能执行追踪系统

记录技能路由和执行的完整路径，便于调试和分析

功能：
- 记录每次技能调用的详细信息
- 生成结构化 JSONL 日志
- 提供统计和分析功能

Usage:
    python3 scripts/skill_tracer.py trace --text "分析支付监管" --skill policy-pbc
    python3 scripts/skill_tracer.py stats --days 7
    python3 scripts/skill_tracer.py view --date 2026-02-27
"""

import argparse
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_DIR = Path(__file__).parent
LOG_DIR = SCRIPT_DIR.parent / "日志" / "skill_traces"


class SkillTracer:
    """技能追踪器"""

    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self, date: str = None) -> Path:
        """获取日志文件路径"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"{date}.jsonl"

    def record(self, trace_data: Dict[str, Any]) -> str:
        """
        记录一次技能调用

        Args:
            trace_data: 追踪数据

        Returns:
            trace_id: 追踪ID
        """
        # 生成追踪ID
        trace_id = trace_data.get("trace_id") or str(uuid.uuid4())[:8]
        trace_data["trace_id"] = trace_id

        # 添加时间戳
        trace_data["timestamp"] = trace_data.get("timestamp") or datetime.now().isoformat()

        # 写入日志文件
        log_file = self._get_log_file()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_data, ensure_ascii=False) + "\n")

        return trace_id

    def record_route(self, input_text: str, route_result: Dict[str, Any], duration_ms: int = None) -> str:
        """
        记录路由结果

        Args:
            input_text: 输入文本
            route_result: 路由结果
            duration_ms: 执行耗时（毫秒）

        Returns:
            trace_id
        """
        trace_data = {
            "type": "route",
            "input_text": input_text,
            "route": {
                "skill": route_result.get("skill"),
                "score": route_result.get("score"),
                "matched_triggers": route_result.get("keywords", []),
                "params": route_result.get("params", {}),
                "calls": route_result.get("calls", []),
            },
            "duration_ms": duration_ms,
        }
        return self.record(trace_data)

    def record_execution(self, trace_id: str, skill: str, success: bool, error: str = None, duration_ms: int = None):
        """
        记录执行结果

        Args:
            trace_id: 追踪ID
            skill: 技能名称
            success: 是否成功
            error: 错误信息
            duration_ms: 执行耗时
        """
        trace_data = {
            "type": "execution",
            "trace_id": trace_id,
            "skill": skill,
            "success": success,
            "error": error,
            "duration_ms": duration_ms,
        }
        return self.record(trace_data)

    def query(self, date: str = None, skill: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        查询追踪记录

        Args:
            date: 日期 (YYYY-MM-DD)
            skill: 技能名称过滤
            limit: 返回数量限制

        Returns:
            追踪记录列表
        """
        log_file = self._get_log_file(date)
        if not log_file.exists():
            return []

        records = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if skill and record.get("route", {}).get("skill") != skill:
                        continue
                    records.append(record)
                except json.JSONDecodeError:
                    continue

        return records[-limit:]

    def stats(self, days: int = 7) -> Dict[str, Any]:
        """
        统计技能使用情况

        Args:
            days: 统计天数

        Returns:
            统计数据
        """
        total_routes = 0
        skill_counts = {}
        total_duration = 0
        success_count = 0
        failure_count = 0

        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            records = self.query(date=date)

            for record in records:
                if record.get("type") == "route":
                    total_routes += 1
                    skill = record.get("route", {}).get("skill", "unknown")
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
                    if record.get("duration_ms"):
                        total_duration += record.get("duration_ms", 0)

                elif record.get("type") == "execution":
                    if record.get("success"):
                        success_count += 1
                    else:
                        failure_count += 1

        return {
            "period_days": days,
            "total_routes": total_routes,
            "skill_counts": skill_counts,
            "avg_duration_ms": total_duration // total_routes if total_routes > 0 else 0,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": f"{success_count / (success_count + failure_count) * 100:.1f}%" if (success_count + failure_count) > 0 else "N/A",
        }


def main():
    parser = argparse.ArgumentParser(description="AgentSystem 技能追踪器")
    parser.add_argument("command", nargs="?", help="子命令: trace, stats, view")
    parser.add_argument("--text", "-t", help="输入文本")
    parser.add_argument("--skill", "-s", help="技能名称")
    parser.add_argument("--days", "-d", type=int, default=7, help="统计天数")
    parser.add_argument("--date", help="查看指定日期 (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=10, help="返回数量")

    args = parser.parse_args()

    tracer = SkillTracer()

    if args.command == "trace":
        # 记录追踪
        if not args.text:
            print("Error: --text is required")
            return

        route_result = {
            "skill": args.skill or "unknown",
            "score": 0,
            "keywords": [],
            "params": {},
            "calls": [],
        }
        trace_id = tracer.record_route(args.text, route_result)
        print(f"Traced: {trace_id}")
        return

    if args.command == "stats":
        # 统计
        stats = tracer.stats(args.days)
        print(f"\n技能使用统计 (最近 {stats['period_days']} 天)")
        print("=" * 50)
        print(f"总路由次数: {stats['total_routes']}")
        print(f"平均耗时: {stats['avg_duration_ms']} ms")
        print(f"成功率: {stats['success_rate']}")
        print(f"\n技能使用分布:")
        for skill, count in sorted(stats["skill_counts"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {skill}: {count}")
        return

    if args.command == "view":
        # 查看记录
        records = tracer.query(date=args.date, limit=args.limit)
        print(f"\n追踪记录 ({args.date or '今天'})")
        print("=" * 50)
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            print("-" * 30)
        return

    # 默认显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()

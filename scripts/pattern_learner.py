#!/usr/bin/env python3
"""
交互模式学习系统
负责从工具调用失败和成功经验中提取模式

使用方式:
    python3 scripts/pattern_learner.py add --symptom "TypeError" --solution "添加类型提示"
    python3 scripts/pattern_learner.py search "TypeError"
    python3 scripts/pattern_learner.py list
    python3 scripts/pattern_learner.py stats
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


# 配置路径
AGENTSYS_ROOT = Path(__file__).parent.parent
PATTERNS_DIR = AGENTSYS_ROOT / "日志" / "patterns"
PATTERNS_DB = PATTERNS_DIR / "patterns.db"


def init_db():
    """初始化数据库"""
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(PATTERNS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            pattern_id TEXT PRIMARY KEY,
            description TEXT,
            category TEXT,
            context_json TEXT,
            solution_json TEXT,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_category ON patterns(category)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_last_seen ON patterns(last_seen)
    """)
    conn.commit()
    return conn


def generate_pattern_id(description: str, category: str = "general") -> str:
    """生成模式ID"""
    raw = f"{category}:{description}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def add_pattern(description: str, category: str, context: dict, solution: dict,
                initial_status: str = "success") -> str:
    """添加或更新模式"""
    conn = init_db()
    pattern_id = generate_pattern_id(description, category)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")

    # 检查是否已存在
    existing = conn.execute(
        "SELECT success_count, fail_count FROM patterns WHERE pattern_id = ?",
        (pattern_id,)
    ).fetchone()

    if existing:
        success_count, fail_count = existing
        if initial_status == "success":
            success_count += 1
        else:
            fail_count += 1

        conn.execute("""
            UPDATE patterns SET
                success_count = ?,
                fail_count = ?,
                last_seen = ?,
                updated_at = ?
            WHERE pattern_id = ?
        """, (success_count, fail_count, today, now, pattern_id))
    else:
        conn.execute("""
            INSERT INTO patterns (pattern_id, description, category, context_json,
                solution_json, success_count, fail_count, first_seen, last_seen,
                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern_id, description, category,
            json.dumps(context, ensure_ascii=False),
            json.dumps(solution, ensure_ascii=False),
            1 if initial_status == "success" else 0,
            1 if initial_status == "fail" else 0,
            today, today, now, now
        ))

    conn.commit()
    conn.close()

    print(f"✓ 模式已记录: {pattern_id}")
    return pattern_id


def search_patterns(query: str = None, category: str = None, limit: int = 10):
    """搜索模式"""
    conn = init_db()

    sql = "SELECT pattern_id, description, category, success_count, fail_count, last_seen FROM patterns"
    params = []

    conditions = []
    if query:
        conditions.append("(description LIKE ? OR context_json LIKE ? OR solution_json LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
    if category:
        conditions.append("category = ?")
        params.append(category)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += f" ORDER BY (success_count - fail_count) DESC, last_seen DESC LIMIT {limit}"

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    if not rows:
        print("未找到匹配的模式")
        return

    print(f"找到 {len(rows)} 个模式:\n")
    for row in rows:
        pattern_id, desc, cat, success, fail, last_seen = row
        rate = success / (success + fail) if (success + fail) > 0 else 0
        print(f"[{pattern_id}] {desc}")
        print(f"  类别: {cat} | 成功率: {rate:.0%} | 最后出现: {last_seen}")
        print()


def list_patterns(limit: int = 20):
    """列出所有模式"""
    conn = init_db()

    rows = conn.execute("""
        SELECT pattern_id, description, category, success_count, fail_count, last_seen
        FROM patterns
        ORDER BY (success_count + fail_count) DESC
        LIMIT ?
    """, (limit,)).fetchall()

    conn.close()

    if not rows:
        print("暂无模式记录")
        return

    print(f"共 {len(rows)} 个模式:\n")
    for row in rows:
        pattern_id, desc, cat, success, fail, last_seen = row
        rate = success / (success + fail) if (success + fail) > 0 else 0
        print(f"{pattern_id} | {desc[:40]:40} | {cat:10} | {rate:.0%}")


def get_pattern(pattern_id: str) -> dict:
    """获取单个模式详情"""
    conn = init_db()

    row = conn.execute("""
        SELECT pattern_id, description, category, context_json, solution_json,
            success_count, fail_count, first_seen, last_seen
        FROM patterns WHERE pattern_id = ?
    """, (pattern_id,)).fetchone()

    conn.close()

    if not row:
        return None

    return {
        "pattern_id": row[0],
        "description": row[1],
        "category": row[2],
        "context": json.loads(row[3]),
        "solution": json.loads(row[4]),
        "success_count": row[5],
        "fail_count": row[6],
        "first_seen": row[7],
        "last_seen": row[8]
    }


def stats():
    """统计模式库"""
    conn = init_db()

    total = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    total_success = conn.execute("SELECT SUM(success_count) FROM patterns").fetchone()[0] or 0
    total_fail = conn.execute("SELECT SUM(fail_count) FROM patterns").fetchone()[0] or 0

    top_categories = conn.execute("""
        SELECT category, COUNT(*) as cnt, SUM(success_count) as succ
        FROM patterns GROUP BY category ORDER BY cnt DESC
    """).fetchall()

    recent = conn.execute("""
        SELECT description, last_seen FROM patterns
        ORDER BY last_seen DESC LIMIT 5
    """).fetchall()

    conn.close()

    total_ops = total_success + total_fail
    success_rate = total_success / total_ops * 100 if total_ops > 0 else 0

    print(f"""=== 模式库统计 ===

总量: {total} 个模式
成功: {total_success} 次
失败: {total_fail} 次
成功率: {success_rate:.1f}%

按类别:
""")

    for cat, cnt, succ in top_categories:
        print(f"  {cat}: {cnt} 个")

    print("\n最近模式:")
    for desc, last in recent:
        print(f"  {last}: {desc[:50]}")


def cleanup(days: int = 30):
    """清理旧模式"""
    conn = init_db()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    deleted = conn.execute(
        "DELETE FROM patterns WHERE last_seen < ? AND success_count = 0",
        (cutoff,)
    ).rowcount

    conn.commit()
    conn.close()

    print(f"✓ 已清理 {deleted} 个过期模式")


def extract_error_pattern(error_msg: str) -> dict:
    """从错误信息中提取模式

    常见错误类型:
    - TypeError: 类型相关
    - SyntaxError: 语法错误
    - FileNotFoundError: 文件不存在
    - PermissionError: 权限错误
    - TimeoutError: 超时
    """
    patterns = {
        "TypeError": {
            "category": "type_error",
            "context_template": {"error_type": "TypeError", "message": error_msg}
        },
        "SyntaxError": {
            "category": "syntax_error",
            "context_template": {"error_type": "SyntaxError", "message": error_msg}
        },
        "FileNotFoundError": {
            "category": "file_error",
            "context_template": {"error_type": "FileNotFoundError", "message": error_msg}
        },
        "PermissionError": {
            "category": "permission_error",
            "context_template": {"error_type": "PermissionError", "message": error_msg}
        },
    }

    for error_type, pattern in patterns.items():
        if error_type in error_msg:
            return pattern

    return {
        "category": "unknown_error",
        "context_template": {"error_type": "Unknown", "message": error_msg}
    }


def main():
    parser = argparse.ArgumentParser(description="交互模式学习系统")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # 添加模式
    add = sub.add_parser("add", help="添加新模式")
    add.add_argument("--description", "-d", required=True, help="模式描述")
    add.add_argument("--category", "-c", default="general", help="分类")
    add.add_argument("--symptom", "-s", help="症状/错误信息")
    add.add_argument("--solution", "-o", help="解决方案")
    add.add_argument("--status", default="success", choices=["success", "fail"],
                     help="初始状态")

    # 搜索模式
    search = sub.add_parser("search", help="搜索模式")
    search.add_argument("query", nargs="?", help="搜索关键词")
    search.add_argument("--category", "-c", help="按分类筛选")
    search.add_argument("--limit", "-l", type=int, default=10, help="结果数量")

    # 列出模式
    sub.add_parser("list", help="列出所有模式")

    # 模式详情
    show = sub.add_parser("show", help="查看模式详情")
    show.add_argument("pattern_id", help="模式ID")

    # 统计
    sub.add_parser("stats", help="模式库统计")

    # 清理
    clean = sub.add_parser("cleanup", help="清理旧模式")
    clean.add_argument("--days", "-d", type=int, default=30, help="保留天数")

    args = parser.parse_args()

    if args.cmd == "add":
        context = {}
        if args.symptom:
            # 尝试从错误信息中提取模式
            error_pattern = extract_error_pattern(args.symptom)
            context = error_pattern["context_template"]
            if args.category == "general":
                args.category = error_pattern["category"]

        solution = {}
        if args.solution:
            solution = {"action": args.solution}

        add_pattern(args.description, args.category, context, solution, args.status)

    elif args.cmd == "search":
        search_patterns(args.query, args.category, args.limit)

    elif args.cmd == "list":
        list_patterns()

    elif args.cmd == "show":
        pattern = get_pattern(args.pattern_id)
        if pattern:
            print(json.dumps(pattern, ensure_ascii=False, indent=2))
        else:
            print("模式不存在")

    elif args.cmd == "stats":
        stats()

    elif args.cmd == "cleanup":
        cleanup(args.days)


if __name__ == "__main__":
    main()

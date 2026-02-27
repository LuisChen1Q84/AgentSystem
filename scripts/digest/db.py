#!/usr/bin/env python3
"""
Digest Module Database
SQLite 数据库管理
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


# 配置
AGENTSYS_ROOT = Path(__file__).parent.parent.parent
DB_PATH = AGENTSYS_ROOT / "数据" / "digest" / "digest.db"


def get_db():
    """获取数据库连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()

    # 信息源表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digest_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            config TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 原始内容表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digest_raw_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            title TEXT,
            url TEXT,
            content TEXT,
            author TEXT,
            fetched_at TEXT DEFAULT (datetime('now')),
            published_at TEXT,
            score INTEGER,
            signal TEXT,
            coin_symbol TEXT,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (source_id) REFERENCES digest_sources(id) ON DELETE CASCADE,
            UNIQUE(source_id, url)
        )
    """)

    # 尝试添加新字段（如果不存在）
    try:
        conn.execute("ALTER TABLE digest_raw_items ADD COLUMN score INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE digest_raw_items ADD COLUMN signal TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE digest_raw_items ADD COLUMN coin_symbol TEXT")
    except sqlite3.OperationalError:
        pass

    # 摘要表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digest_digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            content TEXT,
            source_ids TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 书签表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digest_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


# ===== Source 操作 =====

def add_source(name: str, source_type: str, config: dict = None) -> int:
    """添加信息源"""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO digest_sources (name, type, config) VALUES (?, ?, ?)",
        (name, source_type, json.dumps(config) if config else None)
    )
    conn.commit()
    source_id = cursor.lastrowid
    conn.close()
    return source_id


def get_sources(active_only: bool = True) -> list:
    """获取信息源列表"""
    conn = get_db()
    sql = "SELECT * FROM digest_sources"
    if active_only:
        sql += " WHERE is_active = 1"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_source(source_id: int) -> dict:
    """获取单个信息源"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM digest_sources WHERE id = ?",
        (source_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_source(source_id: int, **kwargs) -> bool:
    """更新信息源"""
    allowed = ['name', 'type', 'config', 'is_active']
    kwargs = {k: v for k, v in kwargs.items() if k in allowed}
    if not kwargs:
        return False

    if "config" in kwargs:
        kwargs["config"] = json.dumps(kwargs["config"], ensure_ascii=False)

    keys = list(kwargs.keys())
    set_clause = ", ".join([f"{k} = ?" for k in keys])
    values = [kwargs[k] for k in keys] + [source_id]

    conn = get_db()
    conn.execute(
        f"UPDATE digest_sources SET {set_clause} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()
    return True


def delete_source(source_id: int) -> bool:
    """删除信息源"""
    conn = get_db()
    conn.execute("DELETE FROM digest_sources WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()
    return True


# ===== Raw Items 操作 =====

def add_raw_item(source_id: int, title: str, url: str, content: str = "",
                 author: str = "", published_at: str = None, metadata: dict = None,
                 score: int = None, signal: str = None, coin_symbol: str = None) -> int:
    """添加原始内容"""
    conn = get_db()
    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO digest_raw_items
               (source_id, title, url, content, author, published_at, metadata, score, signal, coin_symbol)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, title, url, content, author, published_at,
             json.dumps(metadata) if metadata else '{}', score, signal, coin_symbol)
        )
        conn.commit()
        item_id = cursor.lastrowid if cursor.rowcount else None
    except sqlite3.IntegrityError:
        item_id = None
    conn.close()
    return item_id


def get_raw_items(source_id: int = None, since: str = None, limit: int = 100) -> list:
    """获取原始内容"""
    conn = get_db()
    sql = "SELECT * FROM digest_raw_items"
    params = []

    conditions = []
    if source_id:
        conditions.append("source_id = ?")
        params.append(source_id)
    if since:
        conditions.append("fetched_at > ?")
        params.append(since)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY fetched_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ===== Digest 操作 =====

def add_digest(digest_type: str, content: str, source_ids: list = None) -> int:
    """添加摘要"""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO digest_digests (type, content, source_ids) VALUES (?, ?, ?)",
        (digest_type, content, json.dumps(source_ids) if source_ids else None)
    )
    conn.commit()
    digest_id = cursor.lastrowid
    conn.close()
    return digest_id


def get_digests(digest_type: str = None, limit: int = 10) -> list:
    """获取摘要列表"""
    conn = get_db()
    sql = "SELECT * FROM digest_digests"
    params = []

    if digest_type:
        sql += " WHERE type = ?"
        params.append(digest_type)

    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_latest_digest(digest_type: str = None) -> dict:
    """获取最新摘要"""
    conn = get_db()
    sql = "SELECT * FROM digest_digests"
    params = []

    if digest_type:
        sql += " WHERE type = ?"
        params.append(digest_type)

    sql += " ORDER BY created_at DESC LIMIT 1"

    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


# ===== Marks 操作 =====

def add_mark(url: str, title: str = "", note: str = "") -> int:
    """添加书签"""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO digest_marks (url, title, note) VALUES (?, ?, ?)",
        (url, title, note)
    )
    conn.commit()
    mark_id = cursor.lastrowid
    conn.close()
    return mark_id


def get_marks(limit: int = 50) -> list:
    """获取书签列表"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM digest_marks ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_mark(mark_id: int) -> bool:
    """删除书签"""
    conn = get_db()
    conn.execute("DELETE FROM digest_marks WHERE id = ?", (mark_id,))
    conn.commit()
    conn.close()
    return True


if __name__ == "__main__":
    init_db()
    print(f"数据库初始化完成: {DB_PATH}")

#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


IDENT_RE = re.compile(r"^[a-z0-9_\-]{1,64}$")


class APIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class RateLimiter:
    def __init__(self, limit: int, window_sec: int):
        self.limit = max(1, int(limit))
        self.window_sec = max(1, int(window_sec))
        self._lock = threading.Lock()
        self._buckets = {}

    def allow(self, key: str, now_ts: float | None = None) -> bool:
        now_ts = time.time() if now_ts is None else float(now_ts)
        cutoff = now_ts - self.window_sec
        with self._lock:
            bucket = self._buckets.get(key, [])
            bucket = [t for t in bucket if t >= cutoff]
            if len(bucket) >= self.limit:
                self._buckets[key] = bucket
                return False
            bucket.append(now_ts)
            self._buckets[key] = bucket
            return True


def parse_int(qs, key: str, default: int, lo: int, hi: int) -> int:
    raw = qs.get(key, [str(default)])[0]
    try:
        value = int(raw)
    except ValueError as exc:
        raise APIError(400, f"invalid {key}: must be integer") from exc
    if value < lo or value > hi:
        raise APIError(400, f"invalid {key}: must be in [{lo}, {hi}]")
    return value


def parse_ident(qs, key: str) -> str:
    value = (qs.get(key, [""])[0] or "").strip().lower()
    if not value:
        return ""
    if not IDENT_RE.fullmatch(value):
        raise APIError(400, f"invalid {key}: only a-z0-9_- allowed")
    return value


def parse_metric(path: str) -> str:
    metric = path.split("/metric/", 1)[1].strip().lower()
    if not metric:
        raise APIError(400, "invalid metric")
    if not IDENT_RE.fullmatch(metric):
        raise APIError(400, "invalid metric: only a-z0-9_- allowed")
    return metric


def _run_gold(run_query, days: int, dataset: str):
    if dataset:
        rows = run_query(
            """
            SELECT event_date, dataset_id, metric, records, entities, total_value, avg_value
            FROM gold_daily_metrics
            WHERE event_date >= date('now', ?) AND dataset_id = ?
            ORDER BY event_date DESC, records DESC
            """,
            (f"-{days} day", dataset),
        )
    else:
        rows = run_query(
            """
            SELECT event_date, dataset_id, metric, records, entities, total_value, avg_value
            FROM gold_daily_metrics
            WHERE event_date >= date('now', ?)
            ORDER BY event_date DESC, records DESC
            """,
            (f"-{days} day",),
        )

    return {
        "days": days,
        "dataset": dataset or None,
        "items": [
            {
                "event_date": r[0],
                "dataset_id": r[1],
                "metric": r[2],
                "records": r[3],
                "entities": r[4],
                "total_value": r[5],
                "avg_value": r[6],
            }
            for r in rows
        ],
    }


def _run_metric(run_query, metric: str, days: int, dataset: str):
    if dataset:
        rows = run_query(
            """
            SELECT event_date, dataset_id, records, entities, total_value, avg_value
            FROM gold_daily_metrics
            WHERE metric = ? AND dataset_id = ? AND event_date >= date('now', ?)
            ORDER BY event_date DESC
            """,
            (metric, dataset, f"-{days} day"),
        )
    else:
        rows = run_query(
            """
            SELECT event_date, dataset_id, records, entities, total_value, avg_value
            FROM gold_daily_metrics
            WHERE metric = ? AND event_date >= date('now', ?)
            ORDER BY event_date DESC
            """,
            (metric, f"-{days} day"),
        )

    return {
        "metric": metric,
        "days": days,
        "dataset": dataset or None,
        "items": [
            {
                "event_date": r[0],
                "dataset_id": r[1],
                "records": r[2],
                "entities": r[3],
                "total_value": r[4],
                "avg_value": r[5],
            }
            for r in rows
        ],
    }


def _run_trade_core(run_query, days: int, dataset: str):
    if dataset:
        rows = run_query(
            """
            SELECT event_date, dataset_id, txn_count, txn_amount, benefit_amount, fee_income
            FROM gold_trade_core
            WHERE event_date >= date('now', ?) AND dataset_id = ?
            ORDER BY event_date DESC
            """,
            (f"-{days} day", dataset),
        )
    else:
        rows = run_query(
            """
            SELECT event_date, dataset_id, txn_count, txn_amount, benefit_amount, fee_income
            FROM gold_trade_core
            WHERE event_date >= date('now', ?)
            ORDER BY event_date DESC
            """,
            (f"-{days} day",),
        )

    return {
        "days": days,
        "dataset": dataset or None,
        "items": [
            {
                "event_date": r[0],
                "dataset_id": r[1],
                "txn_count": r[2],
                "txn_amount": r[3],
                "benefit_amount": r[4],
                "fee_income": r[5],
            }
            for r in rows
        ],
    }


def _run_summary(run_query, days: int, dataset: str):
    if dataset:
        rows = run_query(
            """
            SELECT dataset_id,
                   COUNT(*) AS metric_rows,
                   COUNT(DISTINCT metric) AS metric_count,
                   COALESCE(SUM(records), 0) AS total_records,
                   COALESCE(SUM(total_value), 0) AS total_value
            FROM gold_daily_metrics
            WHERE event_date >= date('now', ?) AND dataset_id = ?
            GROUP BY dataset_id
            ORDER BY total_records DESC
            """,
            (f"-{days} day", dataset),
        )
    else:
        rows = run_query(
            """
            SELECT dataset_id,
                   COUNT(*) AS metric_rows,
                   COUNT(DISTINCT metric) AS metric_count,
                   COALESCE(SUM(records), 0) AS total_records,
                   COALESCE(SUM(total_value), 0) AS total_value
            FROM gold_daily_metrics
            WHERE event_date >= date('now', ?)
            GROUP BY dataset_id
            ORDER BY total_records DESC
            """,
            (f"-{days} day",),
        )

    return {
        "days": days,
        "dataset": dataset or None,
        "items": [
            {
                "dataset_id": r[0],
                "metric_rows": r[1],
                "metric_count": r[2],
                "total_records": r[3],
                "total_value": r[4],
            }
            for r in rows
        ],
    }


def process_request(path: str, query_string: str, headers: dict, client_ip: str, config: dict, run_query):
    parsed_qs = parse_qs(query_string)

    is_health = path == "/health"
    if config.get("require_auth", False) and not is_health:
        token = (headers.get("x-api-key") or headers.get("X-API-Key") or "").strip()
        if not token:
            raise APIError(401, "missing api key")
        if token != config.get("api_key", ""):
            raise APIError(401, "invalid api key")

    limiter = config.get("limiter")
    if limiter is not None and not is_health:
        if not limiter.allow(client_ip):
            raise APIError(429, "rate limit exceeded")

    if is_health:
        return 200, {"status": "ok"}

    if path == "/gold":
        days = parse_int(parsed_qs, "days", default=30, lo=1, hi=3650)
        dataset = parse_ident(parsed_qs, "dataset")
        return 200, _run_gold(run_query, days, dataset)

    if path.startswith("/metric/"):
        metric = parse_metric(path)
        days = parse_int(parsed_qs, "days", default=30, lo=1, hi=3650)
        dataset = parse_ident(parsed_qs, "dataset")
        return 200, _run_metric(run_query, metric, days, dataset)

    if path == "/trade-core":
        days = parse_int(parsed_qs, "days", default=30, lo=1, hi=3650)
        dataset = parse_ident(parsed_qs, "dataset")
        return 200, _run_trade_core(run_query, days, dataset)

    if path == "/summary":
        days = parse_int(parsed_qs, "days", default=30, lo=1, hi=3650)
        dataset = parse_ident(parsed_qs, "dataset")
        return 200, _run_summary(run_query, days, dataset)

    raise APIError(404, "not found")


class Handler(BaseHTTPRequestHandler):
    db_path = ""
    api_config = {"api_key": "", "require_auth": False, "limiter": None}

    def log_message(self, fmt, *args):
        return

    def _json(self, code, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _query_rows(self, sql: str, params: tuple):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def do_GET(self):
        parsed = urlparse(self.path)
        headers = dict(self.headers.items())
        client_ip = self.client_address[0] if self.client_address else "unknown"
        try:
            code, payload = process_request(
                parsed.path,
                parsed.query,
                headers,
                client_ip,
                self.api_config,
                self._query_rows,
            )
            self._json(code, payload)
        except APIError as exc:
            self._json(exc.status, {"error": exc.message})
        except Exception:
            self._json(500, {"error": "internal error"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--api-key", default=os.environ.get("DATAHUB_API_KEY", ""))
    parser.add_argument("--require-auth", action="store_true")
    parser.add_argument("--rate-limit", type=int, default=120, help="max requests per window per IP")
    parser.add_argument("--rate-window", type=int, default=60, help="window seconds")
    args = parser.parse_args()

    require_auth = bool(args.require_auth or args.api_key)
    limiter = RateLimiter(limit=args.rate_limit, window_sec=args.rate_window) if args.rate_limit > 0 else None

    Handler.db_path = args.db
    Handler.api_config = {
        "api_key": args.api_key,
        "require_auth": require_auth,
        "limiter": limiter,
    }

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"DataHub API running on http://{args.host}:{args.port} (auth={'on' if require_auth else 'off'}, rate={args.rate_limit}/{args.rate_window}s)")
    httpd.serve_forever()


if __name__ == "__main__":
    main()

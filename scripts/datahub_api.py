#!/usr/bin/env python3
import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    db_path = ""

    def _json(self, code, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/health":
            self._json(200, {"status": "ok"})
            return

        if path == "/gold":
            days = int(qs.get("days", ["30"])[0])
            dataset = (qs.get("dataset", [""])[0] or "").strip().lower()
            conn = sqlite3.connect(self.db_path)
            try:
                if dataset:
                    rows = conn.execute(
                        """
                        SELECT event_date, dataset_id, metric, records, entities, total_value, avg_value
                        FROM gold_daily_metrics
                        WHERE event_date >= date('now', ?) AND dataset_id = ?
                        ORDER BY event_date DESC, records DESC
                        """,
                        (f"-{days} day", dataset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT event_date, dataset_id, metric, records, entities, total_value, avg_value
                        FROM gold_daily_metrics
                        WHERE event_date >= date('now', ?)
                        ORDER BY event_date DESC, records DESC
                        """,
                        (f"-{days} day",),
                    ).fetchall()
            finally:
                conn.close()

            data = [
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
            ]
            self._json(200, {"items": data})
            return

        if path.startswith("/metric/"):
            metric = path.split("/metric/", 1)[1].strip().lower()
            days = int(qs.get("days", ["30"])[0])
            dataset = (qs.get("dataset", [""])[0] or "").strip().lower()
            conn = sqlite3.connect(self.db_path)
            try:
                if dataset:
                    rows = conn.execute(
                        """
                        SELECT event_date, dataset_id, records, entities, total_value, avg_value
                        FROM gold_daily_metrics
                        WHERE metric = ? AND dataset_id = ? AND event_date >= date('now', ?)
                        ORDER BY event_date DESC
                        """,
                        (metric, dataset, f"-{days} day"),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT event_date, dataset_id, records, entities, total_value, avg_value
                        FROM gold_daily_metrics
                        WHERE metric = ? AND event_date >= date('now', ?)
                        ORDER BY event_date DESC
                        """,
                        (metric, f"-{days} day"),
                    ).fetchall()
            finally:
                conn.close()

            self._json(
                200,
                {
                    "metric": metric,
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
                },
            )
            return

        if path == "/trade-core":
            days = int(qs.get("days", ["30"])[0])
            dataset = (qs.get("dataset", [""])[0] or "").strip().lower()
            conn = sqlite3.connect(self.db_path)
            try:
                if dataset:
                    rows = conn.execute(
                        """
                        SELECT event_date, dataset_id, txn_count, txn_amount, benefit_amount, fee_income
                        FROM gold_trade_core
                        WHERE event_date >= date('now', ?) AND dataset_id = ?
                        ORDER BY event_date DESC
                        """,
                        (f"-{days} day", dataset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT event_date, dataset_id, txn_count, txn_amount, benefit_amount, fee_income
                        FROM gold_trade_core
                        WHERE event_date >= date('now', ?)
                        ORDER BY event_date DESC
                        """,
                        (f"-{days} day",),
                    ).fetchall()
            finally:
                conn.close()
            self._json(200, {"items": [
                {
                    "event_date": r[0],
                    "dataset_id": r[1],
                    "txn_count": r[2],
                    "txn_amount": r[3],
                    "benefit_amount": r[4],
                    "fee_income": r[5],
                }
                for r in rows
            ]})
            return

        self._json(404, {"error": "not found"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    Handler.db_path = args.db
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"DataHub API running on http://{args.host}:{args.port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()

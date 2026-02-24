#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import sqlite3
import uuid
from pathlib import Path


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def infer_dataset_id(path: Path) -> str:
    n = path.name.lower()
    if "table1" in n or "表1" in n:
        return "table1"
    if "table2" in n or "表2" in n:
        return "table2"
    if "table3" in n or "表3" in n:
        return "table3"
    return "unknown"


def parse_payload_field(v):
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    s = str(v).strip()
    if not s:
        return {}
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {"_raw": s}
    except json.JSONDecodeError:
        return {"_raw": s}


def pick_value(*vals):
    for v in vals:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return ""


def load_csv(path):
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            payload_obj = parse_payload_field(r.get("payload"))
            dataset_id = str(r.get("dataset_id") or payload_obj.get("dataset_id") or infer_dataset_id(path)).strip() or "unknown"
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "event_time": str(pick_value(r.get("event_time"), r.get("timestamp"), "")),
                    "entity_id": str(pick_value(r.get("entity_id"), r.get("user_id"), r.get("id"), "")),
                    "metric": str(pick_value(r.get("metric"), r.get("event"), r.get("type"), "")),
                    "value": str(pick_value(r.get("value"), r.get("amount"), "")),
                    "payload": payload_obj,
                }
            )
    return rows


def load_jsonl(path):
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
        dataset_id = str(obj.get("dataset_id") or payload.get("dataset_id") or infer_dataset_id(path)).strip() or "unknown"
        rows.append(
            {
                "dataset_id": dataset_id,
                "event_time": str(pick_value(obj.get("event_time"), obj.get("timestamp"), "")),
                "entity_id": str(pick_value(obj.get("entity_id"), obj.get("user_id"), obj.get("id"), "")),
                "metric": str(pick_value(obj.get("metric"), obj.get("event"), obj.get("type"), "")),
                "value": str(pick_value(obj.get("value"), obj.get("amount"), "")),
                "payload": payload,
            }
        )
    return rows


def discover_files(import_dir):
    p = Path(import_dir)
    if not p.exists():
        return []
    files = []
    files.extend(sorted(p.glob("*.csv")))
    files.extend(sorted(p.glob("*.jsonl")))
    return files


def file_fingerprint(path: Path):
    st = path.stat()
    return int(st.st_size), int(st.st_mtime)


def should_ingest(conn, path: Path):
    size, mtime = file_fingerprint(path)
    row = conn.execute(
        "SELECT file_size, mtime FROM ingest_registry WHERE source_file = ?",
        (str(path),),
    ).fetchone()
    if not row:
        return True, size, mtime
    return not (row[0] == size and row[1] == mtime), size, mtime


def mark_ingested(conn, path: Path, size: int, mtime: int, run_id: str):
    conn.execute(
        """
        INSERT INTO ingest_registry (source_file, file_size, mtime, last_run_id, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_file) DO UPDATE SET
          file_size=excluded.file_size,
          mtime=excluded.mtime,
          last_run_id=excluded.last_run_id,
          updated_at=excluded.updated_at
        """,
        (str(path), size, mtime, run_id, now()),
    )


def ingest(db, import_dir):
    run_id = dt.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    files = discover_files(import_dir)
    if not files:
        return run_id, 0, 0, 0

    conn = sqlite3.connect(db)
    inserted_files = inserted_rows = skipped_files = 0
    batch = []
    batch_size = 5000
    try:
        for f in files:
            do_ingest, size, mtime = should_ingest(conn, f)
            if not do_ingest:
                skipped_files += 1
                continue

            if f.suffix == ".csv":
                rows = load_csv(f)
                source_type = "csv"
            elif f.suffix == ".jsonl":
                rows = load_jsonl(f)
                source_type = "jsonl"
            else:
                continue
            inserted_files += 1

            for r in rows:
                batch.append(
                    (
                        run_id,
                        r["dataset_id"],
                        str(f),
                        source_type,
                        r["event_time"],
                        r["entity_id"],
                        r["metric"],
                        r["value"],
                        json.dumps(r["payload"], ensure_ascii=False),
                        now(),
                    )
                )
                if len(batch) >= batch_size:
                    conn.executemany(
                        """
                        INSERT INTO bronze_events (
                            run_id, dataset_id, source_file, source_type, raw_event_time, raw_entity_id,
                            raw_metric, raw_value, raw_payload, ingested_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    batch.clear()
                inserted_rows += 1
            mark_ingested(conn, f, size, mtime, run_id)

        if batch:
            conn.executemany(
                """
                INSERT INTO bronze_events (
                    run_id, dataset_id, source_file, source_type, raw_event_time, raw_entity_id,
                    raw_metric, raw_value, raw_payload, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )

        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'ingest', 'DONE', ?, ?)",
            (run_id, f"files={inserted_files},rows={inserted_rows},skipped={skipped_files}", now()),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id, inserted_files, inserted_rows, skipped_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--import-dir", default="私有数据/import")
    args = parser.parse_args()

    run_id, f_cnt, r_cnt, s_cnt = ingest(args.db, args.import_dir)
    print(f"DataHub ingest完成: run_id={run_id}, files={f_cnt}, rows={r_cnt}, skipped={s_cnt}")


if __name__ == "__main__":
    main()

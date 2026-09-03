"""CLI utility to export attendance records to CSV or JSON."""

import csv
import json
import sqlite3
import argparse
from typing import List, Dict, Any


def fetch_attendance(db_path: str, date_filter: str = None) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = """
        SELECT a.id, s.name, s.student_id, s.roll_number, s.class_section,
               a.status, a.method, a.confidence, a.timestamp
        FROM attendance_records a
        JOIN students s ON a.student_id = s.student_id
    """
    params = []
    if date_filter:
        query += " WHERE DATE(a.timestamp) = DATE(?)"
        params.append(date_filter)
    query += " ORDER BY a.timestamp DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def export_to_csv(records: List[Dict[str, Any]], out_path: str):
    if not records:
        print("No records found to export.")
        return
    keys = list(records[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)
    print(f"Exported {len(records)} records to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Attendance Logs")
    parser.add_argument("--db", default="data/attendance_system.db", help="Database path")
    parser.add_argument("--date", default=None, help="Filter date (YYYY-MM-DD)")
    parser.add_argument("--out", default="attendance_report.csv", help="Output CSV path")
    args = parser.parse_args()
    recs = fetch_attendance(args.db, args.date)
    export_to_csv(recs, args.out)

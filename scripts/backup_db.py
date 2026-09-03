"""Automated SQLite database snapshot backup script."""

import os
import shutil
import datetime
import argparse


def backup_database(db_path: str = "data/attendance_system.db", dest_dir: str = "data/backups") -> str:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at {db_path}")
    
    os.makedirs(dest_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"attendance_backup_{ts}.db"
    dest_path = os.path.join(dest_dir, backup_name)
    shutil.copy2(db_path, dest_path)
    print(f"Backup created successfully: {dest_path}")
    return dest_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup SQLite Attendance Database")
    parser.add_argument("--db", default="data/attendance_system.db", help="Path to database file")
    parser.add_argument("--out", default="data/backups", help="Output backup directory")
    args = parser.parse_args()
    backup_database(args.db, args.out)

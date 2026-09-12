"""
Database management module for the AI Attendance System.
Handles SQLite schema creation, connection pooling, and transactional operations.
"""

import os
import sqlite3
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger("attendance.database")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "attendance_system.db")

def init_db(db_path: str = DB_PATH) -> None:
    """Initialize database directories and tables."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Teachers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        fingerprint_id INTEGER UNIQUE,
        rfid_card TEXT,
        photo_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    try:
        cursor.execute("ALTER TABLE teachers ADD COLUMN photo_path TEXT;")
    except Exception:
        pass

    # Students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        roll_number TEXT NOT NULL,
        class_section TEXT NOT NULL,
        photo_path TEXT,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN email TEXT;")
    except Exception:
        pass

    # Weekly Timetable Routines (Monday to Saturday)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timetable_routines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        subject TEXT NOT NULL,
        teacher_id TEXT,
        teacher_name TEXT,
        room_number TEXT DEFAULT 'Room 101',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Face Embeddings table (Vector storage for enrolled faces)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS face_embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        embedding_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
    );
    """)

    # Lecture Sessions (Gated strictly by Teacher Fingerprint Auth)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lecture_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_code TEXT UNIQUE NOT NULL,
        teacher_id TEXT NOT NULL,
        course_code TEXT NOT NULL,
        course_name TEXT NOT NULL,
        room_number TEXT NOT NULL DEFAULT 'Room 101',
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        is_active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
    );
    """)

    # Attendance Records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        entry_time TIMESTAMP NOT NULL,
        exit_time TIMESTAMP,
        last_seen TIMESTAMP NOT NULL,
        confidence REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'PRESENT',
        FOREIGN KEY (session_id) REFERENCES lecture_sessions(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(student_id),
        UNIQUE(session_id, student_id)
    );
    """)

    # System & Hardware Audit Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT 'INFO',
        message TEXT NOT NULL,
        metadata_json TEXT
    );
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialized successfully at {db_path}")

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Return a database connection with row factory enabled."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

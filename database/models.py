"""
Data access object and models for Teachers, Students, Sessions, and Attendance.
Provides high-performance SQLite queries and serialization.
"""

import os
import json
import sqlite3
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from database.db import get_connection

logger = logging.getLogger("attendance.models")

class DatabaseManager:
    """Encapsulates all database operations for the attendance system."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        if self.db_path:
            return get_connection(self.db_path)
        return get_connection()

    # --- TEACHER OPERATIONS ---

    def register_teacher(self, teacher_id: str, name: str, department: str, fingerprint_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO teachers (teacher_id, name, department, fingerprint_id)
                VALUES (?, ?, ?, ?)
            """, (teacher_id, name, department, fingerprint_id))
            conn.commit()
            return True

    def get_teacher_by_fingerprint(self, fingerprint_id: int) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM teachers WHERE fingerprint_id = ?", (fingerprint_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_teacher_by_id(self, teacher_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM teachers WHERE teacher_id = ?", (teacher_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_teachers(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM teachers ORDER BY name ASC")
            return [dict(row) for row in cursor.fetchall()]

    # --- STUDENT & BIOMETRIC OPERATIONS ---

    def register_student(self, student_id: str, name: str, roll_number: str,
                         class_section: str, photo_path: Optional[str] = None) -> bool:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO students (student_id, name, roll_number, class_section, photo_path)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, name, roll_number, class_section, photo_path))
            conn.commit()
            return True

    def add_face_embedding(self, student_id: str, embedding: List[float]) -> bool:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO face_embeddings (student_id, embedding_json)
                VALUES (?, ?)
            """, (student_id, json.dumps(embedding)))
            conn.commit()
            return True

    def get_all_enrolled_faces(self) -> List[Dict[str, Any]]:
        """Returns list of student face vectors with student metadata for fast in-memory matcher."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.student_id, s.name, s.roll_number, s.class_section, s.photo_path,
                       fe.id as embedding_id, fe.embedding_json
                FROM students s
                JOIN face_embeddings fe ON s.student_id = fe.student_id
            """)
            results = []
            for row in cursor.fetchall():
                results.append({
                    "student_id": row["student_id"],
                    "name": row["name"],
                    "roll_number": row["roll_number"],
                    "class_section": row["class_section"],
                    "photo_path": row["photo_path"],
                    "embedding": json.loads(row["embedding_json"])
                })
            return results

    def list_students(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, count(fe.id) as embeddings_count 
                FROM students s 
                LEFT JOIN face_embeddings fe ON s.student_id = fe.student_id
                GROUP BY s.student_id
                ORDER BY s.roll_number ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def delete_student(self, student_id: str) -> bool:
        """Deletes a student, their embeddings, attendance records, and photo file."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT photo_path FROM students WHERE student_id = ?", (student_id,))
            row = cursor.fetchone()
            photo_path = row["photo_path"] if row and row["photo_path"] else None

            cursor.execute("DELETE FROM attendance_records WHERE student_id = ?", (student_id,))
            cursor.execute("DELETE FROM face_embeddings WHERE student_id = ?", (student_id,))
            cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
            conn.commit()

            if photo_path and os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except Exception as e:
                    logger.warning(f"Failed to delete photo {photo_path}: {e}")
            return True

    def delete_all_students(self) -> bool:
        """Deletes all students, face embeddings, attendance records, and face images."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance_records")
            cursor.execute("DELETE FROM face_embeddings")
            cursor.execute("DELETE FROM students")
            conn.commit()

            faces_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faces")
            if os.path.exists(faces_dir):
                for f in os.listdir(faces_dir):
                    fp = os.path.join(faces_dir, f)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except Exception as e:
                            logger.warning(f"Failed to delete {fp}: {e}")
            return True

    # --- SESSION MANAGEMENT ---

    def create_lecture_session(self, teacher_id: str, course_code: str,
                               course_name: str, room_number: str = "Room 101") -> Dict[str, Any]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Deactivate any previous active sessions first
            cursor.execute("""
                UPDATE lecture_sessions 
                SET is_active = 0, end_time = CURRENT_TIMESTAMP 
                WHERE is_active = 1
            """)
            
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session_code = f"SES-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            cursor.execute("""
                INSERT INTO lecture_sessions (session_code, teacher_id, course_code, course_name, room_number, start_time, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (session_code, teacher_id, course_code, course_name, room_number, now_iso))
            conn.commit()
            
            session_id = cursor.lastrowid
            return self.get_session_by_id(session_id)

    def get_active_session(self) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ls.*, t.name as teacher_name, t.department as teacher_department, t.fingerprint_id
                FROM lecture_sessions ls
                JOIN teachers t ON ls.teacher_id = t.teacher_id
                WHERE ls.is_active = 1
                LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None

    def end_active_session(self) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            active = self.get_active_session()
            if not active:
                return None
            
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE lecture_sessions 
                SET is_active = 0, end_time = ? 
                WHERE id = ?
            """, (now_iso, active["id"]))
            conn.commit()
            return self.get_session_by_id(active["id"])

    def get_session_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ls.*, t.name as teacher_name, t.department as teacher_department
                FROM lecture_sessions ls
                JOIN teachers t ON ls.teacher_id = t.teacher_id
                WHERE ls.id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # --- ATTENDANCE LOGGING ---

    def record_or_update_attendance(self, session_id: int, student_id: str,
                                    confidence: float, status: str = "PRESENT") -> Tuple[Dict[str, Any], bool]:
        """
        Records student arrival or updates their last_seen / exit_time.
        Returns (record_dict, is_new_entry).
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM attendance_records 
                WHERE session_id = ? AND student_id = ?
            """, (session_id, student_id))
            existing = cursor.fetchone()

            if existing:
                # Update exit_time and last_seen
                cursor.execute("""
                    UPDATE attendance_records 
                    SET exit_time = ?, last_seen = ?, confidence = MAX(confidence, ?)
                    WHERE id = ?
                """, (now_iso, now_iso, confidence, existing["id"]))
                conn.commit()
                cursor.execute("SELECT * FROM attendance_records WHERE id = ?", (existing["id"],))
                row = cursor.fetchone()
                return (dict(row) if row else dict(existing)), False
            else:
                # New entry log
                cursor.execute("""
                    INSERT INTO attendance_records 
                    (session_id, student_id, entry_time, exit_time, last_seen, confidence, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, student_id, now_iso, now_iso, now_iso, confidence, status))
                conn.commit()
                record_id = cursor.lastrowid
                cursor.execute("SELECT * FROM attendance_records WHERE id = ?", (record_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row), True
                return {
                    "id": record_id,
                    "session_id": session_id,
                    "student_id": student_id,
                    "entry_time": now_iso,
                    "last_seen": now_iso,
                    "confidence": confidence,
                    "status": status
                }, True

    def get_session_attendance(self, session_id: int) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ar.*, s.name as student_name, s.roll_number, s.class_section, s.photo_path
                FROM attendance_records ar
                JOIN students s ON ar.student_id = s.student_id
                WHERE ar.session_id = ?
                ORDER BY ar.entry_time DESC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_attendance_analytics(self) -> Dict[str, Any]:
        """Calculates attendance trends (Daily, Weekly, Monthly) for dashboard graphs."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # Total unique enrolled students
            cursor.execute("SELECT count(*) as total FROM students")
            total_students = cursor.fetchone()["total"]

            # Total sessions
            cursor.execute("SELECT count(*) as total FROM lecture_sessions")
            total_sessions = cursor.fetchone()["total"]

            # Attendance records count by date (Daily trend for past 7 active days)
            cursor.execute("""
                SELECT DATE(entry_time) as date, count(DISTINCT student_id) as present_count
                FROM attendance_records
                GROUP BY DATE(entry_time)
                ORDER BY date DESC LIMIT 7
            """)
            daily_rows = cursor.fetchall()

            # Weekly attendance aggregation
            cursor.execute("""
                SELECT strftime('%W', entry_time) as week_number, count(DISTINCT student_id) as count
                FROM attendance_records
                GROUP BY week_number
                ORDER BY week_number DESC LIMIT 4
            """)
            weekly_rows = cursor.fetchall()

            # Monthly attendance aggregation
            cursor.execute("""
                SELECT strftime('%Y-%m', entry_time) as month, count(DISTINCT student_id) as count
                FROM attendance_records
                GROUP BY month
                ORDER BY month DESC LIMIT 6
            """)
            monthly_rows = cursor.fetchall()

            return {
                "total_enrolled": total_students,
                "total_sessions": total_sessions,
                "daily_trend": [{"date": r["date"], "count": r["present_count"]} for r in reversed(daily_rows)],
                "weekly_trend": [{"week": f"Week {r['week_number']}", "count": r["count"]} for r in reversed(weekly_rows)],
                "monthly_trend": [{"month": r["month"], "count": r["count"]} for r in reversed(monthly_rows)]
            }

    # --- SYSTEM LOGGING ---

    def log_event(self, event_type: str, message: str, level: str = "INFO", metadata: Optional[Dict] = None):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_logs (event_type, level, message, metadata_json)
                VALUES (?, ?, ?, ?)
            """, (event_type, level, message, json.dumps(metadata or {})))
            conn.commit()

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def clear_all_data(self):
        """Clears all records for a fresh production deployment."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance_records")
            cursor.execute("DELETE FROM lecture_sessions")
            cursor.execute("DELETE FROM face_embeddings")
            cursor.execute("DELETE FROM students")
            cursor.execute("DELETE FROM teachers")
            cursor.execute("DELETE FROM system_logs")
            conn.commit()
            logger.info("Production database cleaned. Ready for real registrations.")

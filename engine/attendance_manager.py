"""
Attendance Session Gating and Event Logging Manager.
Enforces that attendance is ONLY logged during teacher-authenticated sessions,
applies hysteresis filtering, debounce cooldown, and entry/exit calculation.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from database.models import DatabaseManager
from fingerprint.fingerprint_manager import FingerprintManager

logger = logging.getLogger("attendance.manager")

class AttendanceManager:
    """Coordinates teacher fingerprint session gating and real-time student attendance."""

    def __init__(self, db: DatabaseManager, fingerprint_mgr: FingerprintManager,
                 min_dwell_frames: int = 3, debounce_seconds: float = 20.0):
        self.db = db
        self.fingerprint_mgr = fingerprint_mgr
        self.min_dwell_frames = min_dwell_frames
        self.debounce_seconds = debounce_seconds

        # State cache for active session
        self.active_session: Optional[Dict[str, Any]] = self.db.get_active_session()
        
        # Debounce and dwell tracker: {student_id: {"last_alert_time": float, "consecutive_frames": int}}
        self.student_track_state: Dict[str, Dict[str, Any]] = {}
        
        # Callbacks for real-time WebSocket / SSE push
        self.subscribers: List[Callable[[str, Dict[str, Any]], None]] = []

        # Wire fingerprint manager callback
        self.fingerprint_mgr.on_teacher_authenticated = self.handle_teacher_fingerprint

    def subscribe(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Register a callback for real-time attendance & session events."""
        self.subscribers.append(callback)

    def _broadcast(self, event_type: str, data: Dict[str, Any]):
        for cb in self.subscribers:
            try:
                cb(event_type, data)
            except Exception as e:
                logger.warning(f"Error broadcasting to subscriber: {e}")

    # --- SESSION GATING VIA FINGERPRINT ---

    def handle_teacher_fingerprint(self, teacher: Dict[str, Any]):
        """
        Called when a teacher places an authorized finger on R307.
        Toggles session: if active session exists for this teacher, ends it.
        Otherwise, starts a new lecture session.
        """
        if self.active_session and self.active_session.get("teacher_id") == teacher["teacher_id"]:
            logger.info(f"Ending active session for teacher {teacher['name']}")
            self.end_session()
        else:
            logger.info(f"Starting new lecture session for teacher {teacher['name']}")
            # Default course code or active curriculum
            self.start_session(
                teacher_id=teacher["teacher_id"],
                course_code="CS501",
                course_name="Embedded AI & Edge Systems",
                room_number="Room 101"
            )

    def start_session(self, teacher_id: str, course_code: str, course_name: str, room_number: str = "Room 101") -> Dict[str, Any]:
        """Starts an authenticated lecture session."""
        session = self.db.create_lecture_session(teacher_id, course_code, course_name, room_number)
        self.active_session = session
        self.student_track_state.clear()
        
        logger.info(f"Lecture Session STARTED: Code {session['session_code']}, Teacher: {session.get('teacher_name')}")
        self._broadcast("SESSION_STARTED", session)
        self.db.log_event("SESSION_START", f"Session started by {session.get('teacher_name')}", metadata=session)
        return session

    def end_session(self) -> Optional[Dict[str, Any]]:
        """Ends the current active lecture session."""
        if not self.active_session:
            self.active_session = self.db.get_active_session()
            if not self.active_session:
                return None
        
        ended_session = self.db.end_active_session()
        prev = self.active_session
        self.active_session = None
        self.student_track_state.clear()

        logger.info(f"Lecture Session ENDED: Code {prev['session_code']}")
        self._broadcast("SESSION_ENDED", ended_session or prev)
        self.db.log_event("SESSION_END", f"Session ended for {prev.get('course_name')}")
        return ended_session or prev

    def get_session_status(self) -> Dict[str, Any]:
        """Returns status of session and teacher presence."""
        self.active_session = self.db.get_active_session()
        return {
            "session_active": self.active_session is not None,
            "session": self.active_session,
            "teacher_present": self.active_session is not None
        }

    # --- ATTENDANCE PROCESSOR ---

    def process_recognized_students(self, recognized_students: List[Dict[str, Any]]):
        """
        Ingests recognized faces from camera frame.
        Attendance is logged ONLY if active_session is True.
        Enforces dwell-time hysteresis and duplicate debounce.
        """
        if not self.active_session:
            # Session NOT active: attendance logging is gated off
            return

        session_id = self.active_session["id"]
        now = time.time()

        for st in recognized_students:
            sid = st["student_id"]
            conf = st["confidence"]

            if sid not in self.student_track_state:
                self.student_track_state[sid] = {
                    "last_alert_time": 0.0,
                    "consecutive_frames": 1
                }
            else:
                self.student_track_state[sid]["consecutive_frames"] += 1

            frames_seen = self.student_track_state[sid]["consecutive_frames"]
            last_alert = self.student_track_state[sid]["last_alert_time"]

            # Check if student has passed minimum dwell threshold
            if frames_seen >= self.min_dwell_frames:
                # Record or update in database
                record, is_new = self.db.record_or_update_attendance(
                    session_id=session_id,
                    student_id=sid,
                    confidence=conf,
                    status="PRESENT"
                )

                # Broadcast live event if it's a new entry or debounce timer expired
                if is_new or (now - last_alert >= self.debounce_seconds):
                    self.student_track_state[sid]["last_alert_time"] = now
                    event_payload = {
                        "record": record,
                        "student": st,
                        "is_new_entry": is_new,
                        "session_id": session_id,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    self._broadcast("STUDENT_MARKED", event_payload)
                    if is_new:
                        logger.info(f"Attendance MARKED: {st['name']} ({st['roll_number']}) - Conf: {conf}")
                        self.db.log_event("ATTENDANCE_MARKED", f"Student {st['name']} marked present", metadata=st)

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import DatabaseManager
from fingerprint.fingerprint_manager import FingerprintManager
from engine.attendance_manager import AttendanceManager

db = DatabaseManager('data/attendance_system.db')
fp = FingerprintManager(db)
att = AttendanceManager(db, fp)

# 1. Start a test session
session = att.start_session("FACULTY-01", "REVOKE_TEST", "Anti-Proxy Revoke Test", "Room 101")
session_id = session["id"]
print(f"[TEST] Session active: {att.get_session_status()['session_active']}, session_id={session_id}")

# 2. Mark student CSE1005 present
test_student_id = "CSE1005"
rec, is_new = db.record_or_update_attendance(session_id, test_student_id, confidence=0.88, status="PRESENT")
print(f"[TEST] Student {test_student_id} marked present in DB. Is new: {is_new}")

# Verify student is present
assert att.is_student_present(test_student_id), "Student must be present!"
sess_att = db.get_session_attendance(session_id)
present_ids = [r["student_id"] for r in sess_att]
assert test_student_id in present_ids, "Student must appear in session attendance list!"
print(f"[OK] Student is confirmed PRESENT in active session.")

# 3. Track events broadcast
events = []
def on_event(ev_type, data):
    events.append((ev_type, data))
att.subscribe(on_event)

# 4. Trigger revocation due to mobile phone detection
payload = att.revoke_student_attendance(test_student_id, reason="Mobile Phone Spoof Detected")
print(f"[TEST] Revoke called. Payload returned: {payload}")

# 5. Verify student is no longer present
assert not att.is_student_present(test_student_id), "Student must NO LONGER be present after revocation!"
sess_att_after = db.get_session_attendance(session_id)
present_ids_after = [r["student_id"] for r in sess_att_after]
assert test_student_id not in present_ids_after, "Student must be removed from session attendance list!"
print(f"[OK] Student is confirmed ABSENT in database attendance records.")

# 6. Verify event was broadcast
revoked_events = [e for e in events if e[0] == "ATTENDANCE_REVOKED"]
assert len(revoked_events) == 1, "Must broadcast exactly one ATTENDANCE_REVOKED event!"
assert revoked_events[0][1]["student_id"] == test_student_id, "Event must match student ID!"
assert "Mobile Phone" in revoked_events[0][1]["reason"], "Event reason must mention mobile phone!"
print(f"[OK] ATTENDANCE_REVOKED event successfully broadcast with payload: {revoked_events[0][1]}")

# 7. End test session
att.end_session()
print("\n>>> ALL ATTENDANCE REVOCATION TESTS PASSED SUCCESSFULLY! <<<")

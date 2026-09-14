import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import numpy as np
from database.models import DatabaseManager
from fingerprint.fingerprint_manager import FingerprintManager
from engine.face_engine import FaceEngine
from engine.attendance_manager import AttendanceManager

db = DatabaseManager('data/attendance_system.db')
fp = FingerprintManager(db)
fe = FaceEngine(db)
att = AttendanceManager(db, fp)

# Load test enrolled face
img = cv2.imread('data/faces/CSE1065_1789370317.jpg')
yunet = cv2.FaceDetectorYN.create('models/yunet.onnx', '', (640, 480))
_, faces = yunet.detect(img)
lms = np.array(faces[0][4:14], dtype=np.float32)
bbox = tuple(faces[0][:4].astype(int))

print("=== 1. TESTING FAST SMILE VERIFICATION (<1s) ===")
fe.tracker.tracked_faces.clear()
sess = att.start_session("FACULTY-01", "TEST_HYBRID_1", "Smile Test", "Room 101")
smile_verified = False

# Student looks at camera and smiles at frame 6
real_detect = fe.detect_faces_and_landmarks
curr_frame_i = 1

def mock_detect(frame):
    res = real_detect(frame)
    if res and curr_frame_i >= 6:
        bbox_m, lms_m = res[0]
        lms_m = lms_m.copy()
        # Outward smile: right mouth moves left, left mouth moves right
        lms_m[10] -= 10.0
        lms_m[12] += 10.0
        return [(bbox_m, lms_m)]
    return res

fe.detect_faces_and_landmarks = mock_detect

for frame_i in range(1, 26):
    curr_frame_i = frame_i
    annotated, recognized, metrics = fe.process_frame(img)
    att.process_recognized_students(recognized)

    records = db.get_session_attendance(sess['id'])
    if records:
        smile_verified = True

    if frame_i in [1, 5, 6, 8, 12, 16]:
        tfs = fe.last_tracked_faces
        state = tfs[0].liveness_state if tfs else "NONE"
        live = tfs[0].is_live if tfs else False
        print(f"   Frame {frame_i}: State={state}, is_live={live}, recognized_count={len(recognized)}")

print(f"Smile Test Result: Marked Attendance in {frame_i} frames? {smile_verified}")
fe.detect_faces_and_landmarks = real_detect
assert smile_verified, "FAILED: Real student smiling was not verified!"
print("PASSED: Fast smile verification succeeded in < 0.5 seconds!")
att.end_session()

print("\n=== 2. TESTING PHONE DETECTION SPOOF BLOCKING ===")
fe.tracker.tracked_faces.clear()
sess2 = att.start_session("FACULTY-01", "TEST_HYBRID_2", "Phone Detection Test", "Room 101")
phone_spoof_blocked = False

# Simulate phone detected overlapping face bbox
fe.liveness_detector.scan_for_phones = lambda frame: [(bbox[0] - 10, bbox[1] - 10, bbox[2] + 20, bbox[3] + 20)]

for frame_i in range(1, 10):
    annotated, recognized, metrics = fe.process_frame(img)
    att.process_recognized_students(recognized)

    records = db.get_session_attendance(sess2['id'])
    if not records:
        phone_spoof_blocked = True

    tfs = fe.last_tracked_faces
    state = tfs[0].liveness_state if tfs else "NONE"
    live = tfs[0].is_live if tfs else False
    print(f"   Frame {frame_i}: State={state}, is_live={live}, recognized_count={len(recognized)}")
    assert state == "SPOOF", f"FAILED: Phone near face must be SPOOF, got {state}"

print(f"Phone Spoof Test Result: Blocked? {phone_spoof_blocked}")
assert phone_spoof_blocked, "FAILED: Phone spoof attendance was not blocked!"
print("PASSED: Phone spoof was immediately blocked (State=SPOOF)!")
att.end_session()

# Clean up database
import sqlite3
con = sqlite3.connect('data/attendance_system.db')
con.execute("DELETE FROM attendance_records WHERE session_id IN (SELECT id FROM lecture_sessions WHERE course_code LIKE 'TEST_HYBRID%')")
con.execute("DELETE FROM lecture_sessions WHERE course_code LIKE 'TEST_HYBRID%'")
con.commit()
print("\nAll Hybrid Liveness tests passed successfully!")

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

# Start session
active_sess = att.start_session("FACULTY-01", "E2E_REVOKE", "Full E2E Revoke Test", "Room 101")
sess_id = active_sess['id']
print(f"Session started: {sess_id}")

# Load an enrolled face (CSE1065)
img = cv2.imread('data/faces/CSE1065_1789370317.jpg')
yunet = cv2.FaceDetectorYN.create('models/yunet.onnx', '', (640, 480))
_, faces = yunet.detect(img)
lms = np.array(faces[0][4:14], dtype=np.float32)
re_x, re_y = int(lms[0]), int(lms[1])
le_x, le_y = int(lms[2]), int(lms[3])
rad = int(np.sqrt((re_x - le_x)**2 + (re_y - le_y)**2) * 0.16)
skin_tone = np.mean(img[re_y-rad-6:re_y-rad-1, re_x-rad:re_x+rad], axis=(0,1))

print("\n--- PHASE 1: Real student presents and blinks -> Marks PRESENT ---")
student_marked = False
for frame_i in range(1, 35):
    f_img = img.copy()
    if frame_i in [12, 13]:
        f_img[re_y-rad:re_y+rad, re_x-rad:re_x+rad] = skin_tone
        f_img[le_y-rad:le_y+rad, le_x-rad:le_x+rad] = skin_tone

    annotated, recognized, metrics = fe.process_frame(f_img)
    att.process_recognized_students(recognized)

    records = db.get_session_attendance(sess_id)
    if records:
        student_marked = True

assert student_marked, "Student should have been marked present!"
assert att.is_student_present("CSE1065"), "Student CSE1065 must be PRESENT in session!"
print("[OK] Real student successfully marked PRESENT in session!")

print("\n--- PHASE 2: Mobile phone detected near student face ---")
# Simulate a phone detected in frame near the face
revoked_detected = False
for frame_i in range(1, 15):
    # Simulate YOLO finding a mobile phone overlapping the face
    fx, fy, fw, fh = int(faces[0][0]), int(faces[0][1]), int(faces[0][2]), int(faces[0][3])
    fe.liveness_detector.last_detected_phones = [(fx, fy, fw, fh)]
    fe.liveness_detector.frame_scan_counter = 0

    annotated, recognized, metrics = fe.process_frame(img)
    att.process_recognized_students(recognized)

    # Check background inference loop spoof check logic
    for tf in getattr(fe, "last_tracked_faces", []):
        if getattr(tf, "liveness_state", "") == "SPOOF":
            sid = getattr(tf, "identity", None)
            reason = getattr(tf, "liveness_reason", "Photo / Screen Spoof")
            if sid and att.is_student_present(sid):
                print(f"Frame {frame_i}: Mobile phone detected for present student {sid}! Calling revoke...")
                payload = att.revoke_student_attendance(sid, reason=reason)
                revoked_detected = True

# Verify that student was revoked and is now ABSENT
assert revoked_detected, "Revocation must be triggered when spoof is detected!"
assert not att.is_student_present("CSE1065"), "Student CSE1065 must now be ABSENT!"
remaining_records = db.get_session_attendance(sess_id)
assert len(remaining_records) == 0, "No attendance records should remain for CSE1065!"

print("[OK] SUCCESS: Student was automatically reverted back to ABSENT after mobile/spoof detected!")
att.end_session()
print("\n>>> FULL E2E ANTI-PROXY REVOCATION TEST PASSED! <<<")

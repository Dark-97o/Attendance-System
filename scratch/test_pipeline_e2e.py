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

# Start a dummy test session
active = att.start_session("FACULTY-01", "TEST101", "Test Subject", "Room 101")
print(f"Session started: {att.get_session_status()['session_active']}")

# Load an enrolled face
img = cv2.imread('data/faces/CSE1065_1789370317.jpg')
yunet = cv2.FaceDetectorYN.create('models/yunet.onnx', '', (640, 480))
_, faces = yunet.detect(img)
lms = np.array(faces[0][4:14], dtype=np.float32)

print("\n--- PHASE 1: Presenting Static Phone Photo (45 frames) ---")
marked_present = False
for frame_i in range(1, 46):
    # Simulate slight phone movement in hand
    jitter = np.random.uniform(-0.5, 0.5, size=lms.shape)
    annotated, recognized, metrics = fe.process_frame(img)
    att.process_recognized_students(recognized)
    
    # Check if anything was marked
    records = db.get_session_attendance(active['id'])
    if records:
        marked_present = True
        break
            
    if frame_i in [1, 10, 20, 39, 41, 45]:
        tfs = fe.last_tracked_faces
        tf_state = tfs[0].liveness_state if tfs else "NONE"
        tf_live = tfs[0].is_live if tfs else False
        print(f"Frame {frame_i}: State={tf_state}, is_live={tf_live}, recognized_count={len(recognized)}")

print(f"\nSTATIC PHOTO ATTACK RESULT: Marked Attendance? {marked_present}")
assert not marked_present, "FAILED: Static phone photo was marked present!"
print("PASSED: Static phone photo was successfully BLOCKED from marking attendance!")

print("\n--- PHASE 2: Presenting Real Student with Natural Blink ---")
# Reset tracker for clean student test
fe.tracker.tracked_faces.clear()
active2 = att.start_session("FACULTY-01", "TEST102", "Real Student Test", "Room 101")
student_marked = False

# We simulate 25 frames where student naturally blinks at frames 12-13
re_x, re_y = int(lms[0]), int(lms[1])
le_x, le_y = int(lms[2]), int(lms[3])
rad = int(np.sqrt((re_x - le_x)**2 + (re_y - le_y)**2) * 0.16)

# Extract skin tone from forehead above eye to simulate closed eyelid skin
skin_tone = np.mean(img[re_y-rad-6:re_y-rad-1, re_x-rad:re_x+rad], axis=(0,1))

for frame_i in range(1, 35):
    f_img = img.copy()
    if frame_i in [12, 13]:
        # Eye closes during natural human blink: eyelid covers pupil
        f_img[re_y-rad:re_y+rad, re_x-rad:re_x+rad] = skin_tone
        f_img[le_y-rad:le_y+rad, le_x-rad:le_x+rad] = skin_tone

    annotated, recognized, metrics = fe.process_frame(f_img)
    att.process_recognized_students(recognized)

    records = db.get_session_attendance(active2['id'])
    if records:
        student_marked = True

    if frame_i in [1, 10, 14, 18, 25, 32]:
        tfs = fe.last_tracked_faces
        tf_state = tfs[0].liveness_state if tfs else "NONE"
        tf_live = tfs[0].is_live if tfs else False
        print(f"Frame {frame_i}: State={tf_state}, is_live={tf_live}, recognized_count={len(recognized)}")

print(f"\nREAL STUDENT RESULT: Marked Attendance? {student_marked}")
assert student_marked, "FAILED: Real student was not marked present after blinking!"
print("PASSED: Real student verified and marked present!")

# Clean up
att.end_session()
print("\nAll pipeline security tests passed successfully.")

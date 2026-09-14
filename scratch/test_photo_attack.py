"""
Simulate a student attempting proxy attendance with a mobile phone photo
vs a real student standing in front of the camera.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
from database.models import DatabaseManager
from engine.face_engine import FaceEngine

def test_attack_simulation():
    print("--- SIMULATING PHONE PHOTO ATTACK ---")
    face_eng = FaceEngine(DatabaseManager())
    real_face = cv2.imread(os.path.join("data", "faces", "CSE1065_1789370317.jpg"))

    # 1. Simulate phone photo shown for 25 frames (static image with slight hand movement)
    spoof_detected = False
    for frame_idx in range(25):
        # Slight hand drift (0-2 pixels)
        drift_x = int(np.sin(frame_idx * 0.2) * 2)
        drift_y = int(np.cos(frame_idx * 0.2) * 2)
        M = np.float32([[1, 0, drift_x], [0, 1, drift_y]])
        drifted = cv2.warpAffine(real_face, M, (real_face.shape[1], real_face.shape[0]))

        ann, rec, metrics = face_eng.process_frame(drifted)
        tf = face_eng.last_tracked_faces[0] if face_eng.last_tracked_faces else None
        if tf:
            state = getattr(tf, "liveness_state", "PENDING")
            if state == "SPOOF":
                spoof_detected = True
                print(f"Frame {frame_idx}: SPOOF DETECTED! Reason: {tf.liveness_reason}")
                print(f"Recognized students marked: {len(rec)} (MUST BE 0)")
                assert len(rec) == 0, "Photo must NEVER be recognized as an attendee!"
                break

    assert spoof_detected, "Phone photo attack must be flagged as SPOOF after dwell timeout!"
    print("[PASS] Phone photo proxy attempt was successfully BLOCKED and flagged as SPOOF!")

if __name__ == "__main__":
    test_attack_simulation()

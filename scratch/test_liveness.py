"""
Diagnostic test script for upgraded LivenessDetector (Eye Blink + 3D Yaw + Screen Texture).
Verifies:
1. Real student image texture vs high-frequency screen grid.
2. Natural eye blink detection (open-close-open dip signature) vs static frozen eyes.
3. 3D head yaw perspective movement vs flat 2D photo.
4. FaceEngine end-to-end integration and liveness state machine.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
from engine.liveness import LivenessDetector
from database.models import DatabaseManager
from engine.face_engine import FaceEngine

def test_liveness():
    print("--- TESTING UPGRADED LIVENESS DETECTOR ---")
    detector = LivenessDetector()

    # 1. Test texture analysis
    real_face_path = os.path.join(os.path.dirname(__file__), "..", "data", "faces", "CSE1065_1789370317.jpg")
    real_face = cv2.imread(real_face_path)
    tex_live, tex_score, tex_reason = detector.evaluate_texture_liveness(real_face)
    print(f"Real Student Photo -> Live: {tex_live}, Score: {tex_score}, Reason: {tex_reason}")
    assert tex_live is True, "Real student photo must pass texture check"

    # Simulated screen moiré: high-frequency alternating grid noise
    grid_mock = np.zeros((160, 160, 3), dtype=np.uint8)
    grid_mock[::2, :] = 255
    grid_mock[:, ::2] = 255
    tex_live_grid, tex_score_grid, tex_reason_grid = detector.evaluate_texture_liveness(grid_mock)
    print(f"Screen Grid Mock -> Live: {tex_live_grid}, Score: {tex_score_grid}, Reason: {tex_reason_grid}")
    assert tex_live_grid is False, "Screen grid mock must be caught by FFT filter"

    # 2. Test Eye Blink Detection
    # Static eyes on phone: constant openness metric across 15 frames
    static_eye_history = [85.0 + np.random.uniform(-1, 1) for _ in range(15)]
    is_blink_static = detector.detect_eye_blink(static_eye_history)
    print(f"Static Eyes (Phone Photo) -> Blink Detected: {is_blink_static}")
    assert is_blink_static is False, "Static eyes must NOT trigger a blink"

    # Living person blink: baseline ~85, dips to ~35 for 2 frames, then recovers to ~85
    blink_eye_history = [85.0, 84.0, 86.0, 85.0, 38.0, 35.0, 78.0, 86.0, 85.0, 84.0]
    is_blink_live = detector.detect_eye_blink(blink_eye_history)
    print(f"Natural Blink (Living Person) -> Blink Detected: {is_blink_live}")
    assert is_blink_live is True, "Natural blink must be detected successfully"

    # 3. Test 3D Perspective Yaw Movement
    # Static 2D photo on phone: yaw ratio is rigid and fixed
    static_yaw = [0.92 + np.random.uniform(-0.005, 0.005) for _ in range(15)]
    is_3d_static = detector.detect_3d_yaw_movement(static_yaw)
    print(f"Static 2D Phone Photo -> 3D Yaw Movement: {is_3d_static}")
    assert is_3d_static is False, "Static 2D photo must NOT trigger 3D perspective shift"

    # Living person turning head slightly: yaw changes from 0.88 to 1.05
    living_yaw = [0.88, 0.89, 0.91, 0.94, 0.98, 1.02, 1.05, 1.03, 0.99, 0.95]
    is_3d_live = detector.detect_3d_yaw_movement(living_yaw)
    print(f"Living Head Turn -> 3D Yaw Movement: {is_3d_live}")
    assert is_3d_live is True, "Natural 3D head movement must be detected successfully"

    # 4. Test FaceEngine end-to-end integration
    print("\n--- TESTING FACE ENGINE INTEGRATION ---")
    db = DatabaseManager()
    face_eng = FaceEngine(db)
    assert hasattr(face_eng, "liveness_detector"), "FaceEngine must have liveness_detector"
    print("FaceEngine initialized with upgraded liveness detector successfully!")

    # Test processing a frame
    ann_frame, rec_students, metrics = face_eng.process_frame(real_face)
    print(f"Processed enrolled image -> Output shape: {ann_frame.shape}, recognized students: {len(rec_students)}")
    for tf in face_eng.last_tracked_faces:
        print(f"Tracked Face: id={tf.track_id}, state={tf.liveness_state}, reason={tf.liveness_reason}")

    print("\n[PASS] ALL ADVANCED ANTI-SPOOFING & LIVENESS TESTS PASSED!")

if __name__ == "__main__":
    test_liveness()

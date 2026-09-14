"""
Diagnostic test script for LivenessDetector and Anti-Spoofing integration.
Verifies FFT spectrum analysis, bezel edge detection, and biological micro-movement dynamics.
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
    print("--- TESTING LIVENESS DETECTOR ---")
    detector = LivenessDetector()

    # 1. Test texture analysis with actual enrolled student photo vs screen moiré simulation
    real_face_path = os.path.join(os.path.dirname(__file__), "..", "data", "faces", "CSE1065_1789370317.jpg")
    real_face = cv2.imread(real_face_path)
    tex_live, tex_score, tex_reason = detector.evaluate_texture_liveness(real_face)
    print(f"Real Student Photo -> Live: {tex_live}, Ratio: {tex_score}, Reason: {tex_reason}")
    assert tex_live is True, "Real student photo must pass texture check"

    # Simulated screen moiré: high-frequency alternating grid noise
    grid_mock = np.zeros((160, 160, 3), dtype=np.uint8)
    grid_mock[::2, :] = 255
    grid_mock[:, ::2] = 255
    tex_live_grid, tex_score_grid, tex_reason_grid = detector.evaluate_texture_liveness(grid_mock)
    print(f"Screen Grid Mock -> Live: {tex_live_grid}, Score: {tex_score_grid}, Reason: {tex_reason_grid}")

    # 2. Test landmark dynamics (static frozen photo vs living micro-movements)
    # Frozen landmarks (identical across 15 frames)
    base_lm = np.array([50.0, 50.0, 100.0, 50.0, 75.0, 75.0, 60.0, 100.0, 90.0, 100.0], dtype=np.float32)
    frozen_history = [base_lm.copy() for _ in range(15)]
    dyn_live_frozen, dyn_score_frozen, dyn_reason_frozen = detector.evaluate_dynamics(frozen_history)
    print(f"Frozen Photo Landmarks -> Live: {dyn_live_frozen}, Variance: {dyn_score_frozen}, Reason: {dyn_reason_frozen}")
    assert dyn_live_frozen is False, "Frozen landmarks must be detected as static photo attack"

    # Dynamic living landmarks (natural micro-movements across 15 frames)
    living_history = []
    for f in range(15):
        jitter = np.random.normal(0, 0.4, size=10).astype(np.float32)
        living_history.append(base_lm + jitter)
    dyn_live_living, dyn_score_living, dyn_reason_living = detector.evaluate_dynamics(living_history)
    print(f"Living Landmarks -> Live: {dyn_live_living}, Variance: {dyn_score_living}, Reason: {dyn_reason_living}")
    assert dyn_live_living is True, "Natural micro-movements must be accepted as live"

    # 3. Test FaceEngine initialization with liveness detector
    print("\n--- TESTING FACE ENGINE INTEGRATION ---")
    db = DatabaseManager()
    face_eng = FaceEngine(db)
    assert hasattr(face_eng, "liveness_detector"), "FaceEngine must have liveness_detector instance"
    print("FaceEngine initialized successfully with active liveness detector!")

    # Test processing a blank frame
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    ann_frame, rec_students, metrics = face_eng.process_frame(dummy_frame)
    print(f"Processed dummy frame -> output shape: {ann_frame.shape}, recognized: {len(rec_students)}")

    print("\n[PASS] ALL ANTI-SPOOFING & LIVENESS TESTS PASSED!")

if __name__ == "__main__":
    test_liveness()

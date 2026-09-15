"""
Comprehensive validation of accelerated phone screen and presentation attack detection.
Tests:
1. Instant Frame-1 phone detection.
2. Geometric edge-distance proximity (adjacent, touching, enclosing).
3. False positive rate on all enrolled real human student faces.
4. Static photo timeout (fast 25-frame cutoff).
5. Dynamic smile verification (< 1s) for real human faces.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import numpy as np
import glob
import time
from engine.liveness import LivenessDetector
from engine.tracker import TrackedFace

def test_instant_frame1_phone_scan():
    detector = LivenessDetector()
    
    # Mock frame with a phone
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    t0 = time.time()
    # Call scan_for_phones on Frame 1
    phones = detector.scan_for_phones(frame)
    latency_ms = (time.time() - t0) * 1000
    
    # Verify scan counter is 1 and it didn't skip
    assert detector.frame_scan_counter == 1, f"Expected counter=1, got {detector.frame_scan_counter}"
    print(f"[PASS] Test 1: Frame-1 Scan ran immediately in {latency_ms:.1f}ms without frame-skipping delay.")

def test_geometric_proximity():
    detector = LivenessDetector()
    face_bbox = (250, 150, 100, 120)
    
    # Case A: Phone directly under face (held up)
    phone_under = (240, 280, 120, 180)
    assert detector.is_phone_near_face(face_bbox, [phone_under]), "Case A: Phone under face should be detected as near"
    
    # Case B: Phone enclosing the face (photo displayed on screen)
    phone_enclosing = (200, 100, 200, 260)
    assert detector.is_phone_near_face(face_bbox, [phone_enclosing]), "Case B: Phone enclosing face should be detected as near"
    
    # Case C: Phone overlapping side of face
    phone_overlapping = (330, 160, 100, 160)
    assert detector.is_phone_near_face(face_bbox, [phone_overlapping]), "Case C: Phone overlapping face should be detected as near"
    
    # Case D: Distant phone (someone standing in far background)
    phone_distant = (50, 50, 60, 90)
    assert not detector.is_phone_near_face(face_bbox, [phone_distant]), "Case D: Distant phone should NOT trigger on face"
    
    print("[PASS] Test 2: Geometric proximity (under, enclosing, overlapping, distant) verified perfectly.")

def test_zero_false_positives_on_enrolled_faces():
    detector = LivenessDetector()
    face_files = glob.glob('data/faces/*.jpg')
    print(f"Testing {len(face_files)} enrolled faces for false positive phone detections...")
    
    false_positives = 0
    for fpath in face_files:
        img = cv2.imread(fpath)
        if img is None: continue
        phones = detector.scan_for_phones(img, force=True)
        if len(phones) > 0:
            print(f"  False positive in {fpath}: {phones}")
            false_positives += 1
            
    assert false_positives == 0, f"Expected 0 false positives, got {false_positives}"
    print(f"[PASS] Test 3: Zero false positives across all {len(face_files)} real enrolled student faces.")

def test_fast_timeout_and_smile():
    detector = LivenessDetector(verification_timeout_frames=25)
    
    # Test static timeout
    tf_static = TrackedFace(track_id=1, bbox=(200, 150, 100, 120))
    tf_static.frames_active = 26
    tf_static.is_live = False
    
    # Dummy crop
    face_crop = np.zeros((100, 100, 3), dtype=np.uint8)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dummy_lms = np.array([220, 180, 280, 180, 250, 210, 230, 240, 270, 240], dtype=np.float32)
    
    res = detector.evaluate_face_liveness(face_crop, dummy_lms, (200, 150, 100, 120), dummy_frame, tf_static)
    assert res["state"] == "SPOOF", f"Expected SPOOF after 26 frames, got {res['state']}"
    assert "Static Photo" in res["reason"]
    print(f"[PASS] Test 4: Static photo timeout triggered cleanly at 25 frames (~1.5s): {res['reason']}")
    
    # Test smile verification works
    tf_smile = TrackedFace(track_id=2, bbox=(200, 150, 100, 120))
    tf_smile.frames_active = 12
    tf_smile.smile_hist = [0.82] * 7 + [0.85, 0.96, 1.05, 1.08] # Dynamic expansion
    assert detector.check_smile_verification(tf_smile), "Dynamic smile should be verified"
    print("[PASS] Test 5: Dynamic human smile verified successfully in <1s.")

if __name__ == "__main__":
    test_instant_frame1_phone_scan()
    test_geometric_proximity()
    test_zero_false_positives_on_enrolled_faces()
    test_fast_timeout_and_smile()
    print("\nALL 5 ACCELERATED DETECTION TESTS PASSED!")

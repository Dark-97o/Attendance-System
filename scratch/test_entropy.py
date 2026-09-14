"""Test gradient entropy of enrolled student photos to calibrate threshold."""
import sys, cv2, numpy as np, os
sys.path.insert(0, '.')
from engine.liveness import LivenessDetector
from engine.face_engine import FaceEngine
from database.models import DatabaseManager

ld = LivenessDetector()
db = DatabaseManager('data/attendance_system.db')
fe = FaceEngine(db)

print('=== Gradient Entropy for Enrolled Student Photos ===')
entropies = []
for sid, meta in fe.student_metadata.items():
    p = meta.get('photo_path')
    if not p or not os.path.exists(p):
        continue
    img = cv2.imread(p)
    if img is None:
        continue
    faces = fe.detect_faces_and_landmarks(img)
    if not faces:
        print(f"  {meta['name']}: No face detected")
        continue
    bbox, _ = faces[0]
    x, y, w, h = bbox
    crop = img[y:y+h, x:x+w]
    is_real, entropy = ld.evaluate_flat_surface(crop)
    entropies.append(entropy)
    verdict = "OK" if is_real else "BLOCKED (false positive!)"
    print(f"  {meta['name']}: entropy={entropy:.3f} -> {verdict}")

if entropies:
    print(f"\nMin entropy: {min(entropies):.3f}, Max: {max(entropies):.3f}, Mean: {float(np.mean(entropies)):.3f}")
    print(f"Threshold is 2.0. Any enrolled photo with entropy < 2.0 would be a FALSE POSITIVE.")

# Also test smile verification fix with static smiling photo
from collections import deque
print('\n=== Testing FIXED Smile Verification ===')

class FakeFace:
    def __init__(self, hist):
        self.track_id = 99
        self.smile_hist = deque(hist, maxlen=30)

# Static smiling photo: constant high ratio
f1 = FakeFace([1.05]*15)
r1 = ld.check_smile_verification(f1)
print(f"Static SMILING photo (constant ratio 1.05): passes={r1}  (should be False)")

# Static neutral photo
f2 = FakeFace([0.88]*15)
r2 = ld.check_smile_verification(f2)
print(f"Static NEUTRAL photo (constant ratio 0.88): passes={r2}  (should be False)")

# Real human smile: starts neutral (0.87), then smiles (1.05)
f3 = FakeFace([0.87]*8 + [1.02]*5)
r3 = ld.check_smile_verification(f3)
print(f"Real human smile (0.87->1.02 expansion): passes={r3}  (should be True)")

# Barely smiling real human
f4 = FakeFace([0.84]*8 + [0.97]*5)
r4 = ld.check_smile_verification(f4)
print(f"Moderate real smile (0.84->0.97): passes={r4}  (should be True)")

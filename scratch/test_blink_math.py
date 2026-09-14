import cv2
import numpy as np

def analyze_eye_patch(frame, eye_center, eye_w, eye_h):
    h, w = frame.shape[:2]
    cx, cy = int(eye_center[0]), int(eye_center[1])
    hw, hh = int(eye_w / 2), int(eye_h / 2)
    x1, y1 = max(0, cx - hw), max(0, cy - hh)
    x2, y2 = min(w, cx + hw), min(h, cy + hh)
    if (x2 - x1) < 4 or (y2 - y1) < 4:
        return 0.0, 0.0, 0.0
    
    patch = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    
    # Pupil darkness relative to patch mean
    mean_val = float(np.mean(gray))
    min_val = float(np.min(gray))
    pupil_contrast = max(0.0, mean_val - min_val)
    
    # Eye openness metric: open eye has dark pupil inside brighter sclera/skin
    # When eye closes, pupil is occluded by eyelid skin, so min_val approaches mean_val
    std_val = float(np.std(gray))
    
    # Vertical gradient across eyelid boundary
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge_y = float(np.mean(np.abs(sobel_y)))
    
    openness_score = (pupil_contrast * 0.5) + (std_val * 0.3) + (edge_y * 0.2)
    return openness_score, pupil_contrast, std_val

# Test on live snapshot
img = cv2.imread('scratch/live_snapshot.jpg')
yunet = cv2.FaceDetectorYN.create('models/yunet.onnx', '', (640, 480))
_, faces = yunet.detect(img)
if faces is not None and len(faces) > 0:
    lms = faces[0][4:14]
    re = (lms[0], lms[1])
    le = (lms[2], lms[3])
    eye_dist = np.linalg.norm(np.array(re) - np.array(le))
    ew = eye_dist * 0.35
    eh = eye_dist * 0.22
    r_score, r_cont, r_std = analyze_eye_patch(img, re, ew, eh)
    l_score, l_cont, l_std = analyze_eye_patch(img, le, ew, eh)
    print(f"Right eye: score={r_score:.2f}, contrast={r_cont:.2f}, std={r_std:.2f}")
    print(f"Left eye:  score={l_score:.2f}, contrast={l_cont:.2f}, std={l_std:.2f}")

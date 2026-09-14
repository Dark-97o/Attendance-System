import cv2
import numpy as np
from collections import deque

def detect_screen_bezel(full_frame, bbox):
    h, w = full_frame.shape[:2]
    x, y, bw, bh = bbox
    # Check outer margin around face bbox
    mx1 = max(0, int(x - bw * 0.25))
    my1 = max(0, int(y - bh * 0.25))
    mx2 = min(w, int(x + bw * 1.25))
    my2 = min(h, int(y + bh * 1.25))
    margin = full_frame[my1:my2, mx1:mx2]
    if margin.size == 0 or margin.shape[0] < 30 or margin.shape[1] < 30:
        return False, 0
    gray = cv2.cvtColor(margin, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=45, minLineLength=35, maxLineGap=8)
    line_count = len(lines) if lines is not None else 0
    # Also check if lines are strictly horizontal or vertical (phone bezel characteristic)
    bezel_lines = 0
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            # Nearly vertical or horizontal
            if dx < 4 or dy < 4 or (dx / (dy + 1e-5) > 5) or (dy / (dx + 1e-5) > 5):
                bezel_lines += 1
    return bezel_lines >= 4, bezel_lines

print("Testing screen bezel detection on enrolled photos...")
import glob
for f in glob.glob('data/faces/*.jpg')[:5]:
    img = cv2.imread(f)
    yunet = cv2.FaceDetectorYN.create('models/yunet.onnx', '', (640, 480))
    _, faces = yunet.detect(img)
    if faces is not None:
        bbox = faces[0][:4].astype(int)
        is_bezel, count = detect_screen_bezel(img, bbox)
        print(f"{f}: Bezel lines={count}, is_bezel={is_bezel}")

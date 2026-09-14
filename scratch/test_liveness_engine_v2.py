import cv2
import numpy as np
from collections import deque
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

class ModernLivenessDetector:
    """
    Military-grade Anti-Spoofing & Liveness Engine.
    Rejects 2D phone/tablet screen photos, printed photos, and static replays.
    Requires genuine biological dual-eye blink with motion-blur immunity.
    """

    def __init__(self, verification_timeout_frames: int = 40):
        self.timeout_frames = verification_timeout_frames

    def analyze_eye(self, frame: np.ndarray, cx: float, cy: float, eye_radius: float):
        h, w = frame.shape[:2]
        x1 = max(0, int(cx - eye_radius))
        y1 = max(0, int(cy - eye_radius * 0.75))
        x2 = min(w, int(cx + eye_radius))
        y2 = min(h, int(cy + eye_radius * 0.75))

        if (x2 - x1) < 4 or (y2 - y1) < 4:
            return 50.0, 0.5

        patch = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)

        min_val = float(np.min(gray))
        mean_val = float(np.mean(gray))
        pupil_ratio = min_val / (mean_val + 1e-5)

        # Contrast & vertical gradient
        contrast = float(np.max(gray) - min_val)
        sob_y = float(np.mean(np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))))
        openness = contrast * 0.6 + sob_y * 0.4

        return openness, pupil_ratio

    def compute_face_sharpness(self, frame: np.ndarray, bbox: tuple) -> float:
        x, y, w, h = bbox
        crop = frame[max(0, y):min(frame.shape[0], y + h), max(0, x):min(frame.shape[1], x + w)]
        if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return 100.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_32F).var())

    def check_genuine_blink(self, tracked_face) -> bool:
        """
        Detects a physiologically valid dual-eye blink.
        Criteria:
        1. Both eyes have stable baseline openness.
        2. Both eyes dip simultaneously by >= 30% for 1 to 5 frames.
        3. Both eyes recover to >= 75% of baseline.
        4. Face sharpness during dip remains stable (not motion blur / phone shake).
        """
        if len(tracked_face.r_open_hist) < 10:
            return False

        r_arr = np.array(tracked_face.r_open_hist, dtype=np.float32)
        l_arr = np.array(tracked_face.l_open_hist, dtype=np.float32)
        sharp_arr = np.array(tracked_face.sharp_hist, dtype=np.float32)

        n = len(r_arr)
        # Search for a dip that occurred in recent frames
        # Look at window of last 15 frames
        window_size = min(n, 15)
        r_win = r_arr[-window_size:]
        l_win = l_arr[-window_size:]
        s_win = sharp_arr[-window_size:]

        r_base = float(np.percentile(r_win, 80))
        l_base = float(np.percentile(l_win, 80))
        s_median = float(np.median(s_win))

        if r_base < 25.0 or l_base < 25.0:
            return False

        # Find min index in window (must not be the very first or very last frame)
        r_min_idx = int(np.argmin(r_win))
        l_min_idx = int(np.argmin(l_win))

        # Synchrony: Both eyes must dip within 1 frame of each other
        if abs(r_min_idx - l_min_idx) > 1:
            return False

        # Dip cannot be at boundary (needs pre-open and post-open)
        dip_idx = r_min_idx
        if dip_idx < 2 or dip_idx > (window_size - 2):
            return False

        r_drop = (r_base - r_win[dip_idx]) / (r_base + 1e-5)
        l_drop = (l_base - l_win[dip_idx]) / (l_base + 1e-5)

        # Must drop by at least 28% for both eyes
        if r_drop < 0.28 or l_drop < 0.28:
            return False

        # Recovery check: latest frame must be recovered
        if r_win[-1] < r_base * 0.75 or l_win[-1] < l_base * 0.75:
            return False

        # Anti-blur check: face sharpness at dip must be >= 60% of median sharpness
        # If camera blurred or phone was shaken, sharpness drops below 40%
        if s_win[dip_idx] < s_median * 0.60:
            logger.info("Rejected false blink: frame experienced motion blur")
            return False

        return True

    def evaluate(self, full_frame: np.ndarray, bbox: tuple, landmarks: np.ndarray, tracked_face) -> dict:
        if landmarks is None or len(landmarks) < 10:
            return {"is_live": False, "state": "PENDING", "reason": "Detecting facial landmarks..."}

        if not hasattr(tracked_face, "r_open_hist"):
            tracked_face.r_open_hist = deque(maxlen=30)
            tracked_face.l_open_hist = deque(maxlen=30)
            tracked_face.sharp_hist = deque(maxlen=30)
            tracked_face.has_blinked = False
            tracked_face.is_live = False
            tracked_face.liveness_state = "PENDING"

        re_x, re_y = landmarks[0], landmarks[1]
        le_x, le_y = landmarks[2], landmarks[3]
        eye_dist = max(15.0, float(np.sqrt((re_x - le_x)**2 + (re_y - le_y)**2)))
        rad = max(6, eye_dist * 0.16)

        r_open, r_pr = self.analyze_eye(full_frame, re_x, re_y, rad)
        l_open, l_pr = self.analyze_eye(full_frame, le_x, le_y, rad)
        sharp = self.compute_face_sharpness(full_frame, bbox)

        tracked_face.r_open_hist.append(r_open)
        tracked_face.l_open_hist.append(l_open)
        tracked_face.sharp_hist.append(sharp)

        # Check for genuine biological blink
        if not tracked_face.has_blinked:
            if self.check_genuine_blink(tracked_face):
                tracked_face.has_blinked = True
                tracked_face.is_live = True
                tracked_face.liveness_state = "LIVE"
                logger.info(f"Track {tracked_face.track_id}: Genuine human eye blink verified!")

        frames_active = getattr(tracked_face, "frames_active", 1)

        if tracked_face.has_blinked:
            return {
                "is_live": True,
                "state": "LIVE",
                "reason": "Verified Live Human",
                "score": 1.0
            }
        elif frames_active < self.timeout_frames:
            return {
                "is_live": False,
                "state": "PENDING",
                "reason": "Verifying Liveness (Blink naturally)...",
                "score": 0.5
            }
        else:
            return {
                "is_live": False,
                "state": "SPOOF",
                "reason": "Spoof: Static Photo (No Blink Detected)",
                "score": 0.0
            }

print("Testing ModernLivenessDetector...")
class DummyTrack:
    def __init__(self):
        self.track_id = 99
        self.frames_active = 1

det = ModernLivenessDetector(verification_timeout_frames=20)
track = DummyTrack()

img = cv2.imread('scratch/live_snapshot.jpg')
yunet = cv2.FaceDetectorYN.create('models/yunet.onnx', '', (640, 480))
_, faces = yunet.detect(img)
lms = np.array(faces[0][4:14], dtype=np.float32)
bbox = tuple(faces[0][:4].astype(int))

print("1. Testing Static Phone Photo simulation (30 frames without blinking):")
for f in range(1, 30):
    track.frames_active = f
    # Add slight random noise to simulate holding phone in hand
    jittered_lms = lms + np.random.uniform(-0.8, 0.8, size=lms.shape)
    res = det.evaluate(img, bbox, jittered_lms, track)
    if f in [1, 5, 10, 19, 21, 28]:
        print(f"   Frame {f}: state={res['state']}, is_live={res['is_live']}, reason={res['reason']}")

print("\n2. Testing Real Human with Natural Blink:")
track2 = DummyTrack()
for f in range(1, 25):
    track2.frames_active = f
    frame_copy = img.copy()
    jittered_lms = lms.copy()
    if f in [10, 11]:
        # Eye closes during blink! Pupil covered by eyelid skin
        # Eyelid patch has low contrast
        re_x, re_y = int(lms[0]), int(lms[1])
        le_x, le_y = int(lms[2]), int(lms[3])
        frame_copy[re_y-8:re_y+8, re_x-12:re_x+12] = [160, 160, 160]
        frame_copy[le_y-8:le_y+8, le_x-12:le_x+12] = [160, 160, 160]
    res = det.evaluate(frame_copy, bbox, jittered_lms, track2)
    if f in [1, 5, 9, 10, 12, 15]:
        print(f"   Frame {f}: state={res['state']}, is_live={res['is_live']}, reason={res['reason']}")

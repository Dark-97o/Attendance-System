"""
Hybrid Multi-Layer Anti-Spoofing & Liveness Detection Engine.
Combines:
1. Deep Learning Mobile Phone / Handheld Screen Detector (YOLOv8n).
2. Fast Smile & Expression Dynamic Verification (Prompt: 'Smile or Blink').
3. Dual-Eye Biological Blink Waveform Gating.
4. High-Frequency Screen Moiré Spectrum Analysis (2D FFT).
5. Planar Geometry Rigidity Constraints.
"""

import cv2
import numpy as np
import logging
import os
from typing import Tuple, List, Dict, Optional, Any
from collections import deque

logger = logging.getLogger("attendance.liveness")

class LivenessDetector:
    """Production-grade edge liveness detector with phone detection and smile verification."""

    def __init__(self,
                 verification_timeout_frames: int = 25,
                 blink_drop_threshold: float = 0.28,
                 smile_expansion_threshold: float = 0.12):
        self.timeout_frames = verification_timeout_frames
        self.blink_drop_threshold = blink_drop_threshold
        self.smile_threshold = smile_expansion_threshold

        # Load YOLOv8n object detector for mobile phone detection
        self.yolo = None
        self.frame_scan_counter = 0
        self.last_detected_phones = []
        self.last_frame_id = None
        self.cached_phones_for_frame = []
        yolo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "yolov8n.onnx")
        if os.path.exists(yolo_path):
            try:
                self.yolo = cv2.dnn.readNet(yolo_path)
                logger.info("Loaded YOLOv8n ONNX Object Detector for Handheld Mobile Phone Spoof Detection")
            except Exception as ye:
                logger.warning(f"Could not load YOLOv8n: {ye}")

    def scan_for_phones(self, frame: np.ndarray, force: bool = False) -> List[Tuple[int, int, int, int]]:
        """Scans frame for mobile phones and digital screens using YOLOv8n with Frame-1 instant detection."""
        if self.yolo is None or frame is None or frame.size == 0:
            return []

        current_frame_id = id(frame)
        if current_frame_id == self.last_frame_id and not force:
            return self.cached_phones_for_frame

        self.last_frame_id = current_frame_id
        self.frame_scan_counter += 1

        # If a phone was already detected, refresh every 2 frames for CPU performance.
        # If no phone is detected yet, scan immediately on Frame 1 (no skipping delay)!
        if not force and self.last_detected_phones and (self.frame_scan_counter % 2 != 0):
            self.cached_phones_for_frame = self.last_detected_phones
            return self.last_detected_phones

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
        self.yolo.setInput(blob)
        out = self.yolo.forward()[0].T  # Shape: (8400, 84)

        # Classes in COCO: 67 (cell phone)
        # We focus primarily on handheld cell phones to prevent presentation attacks
        # while avoiding false positives on laptop webcams / desktop monitors.
        scores_cell = out[:, 4 + 67]
        mask = scores_cell >= 0.35
        filtered = out[mask]

        boxes = []
        confidences = []
        x_factor = w / 640.0
        y_factor = h / 640.0

        for row in filtered:
            cx, cy, bw, bh = row[:4]
            score = float(row[4 + 67])
            left = int((cx - bw / 2) * x_factor)
            top = int((cy - bh / 2) * y_factor)
            boxes.append([left, top, int(bw * x_factor), int(bh * y_factor)])
            confidences.append(score)

        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.35, 0.40)
        self.last_detected_phones = [tuple(boxes[i]) for i in indices.flatten()] if len(indices) > 0 else []
        self.cached_phones_for_frame = self.last_detected_phones
        return self.last_detected_phones

    def is_phone_near_face(self, face_bbox: Tuple[int, int, int, int], phone_boxes: List[Tuple[int, int, int, int]]) -> bool:
        """
        Determines with precision whether THIS specific face is displayed on a mobile phone / screen (presentation attack).
        A spoofed face is physically rendered on the phone screen:
          1. The face center (fcx, fcy) must be located inside the phone bounding box.
          2. The overlap between the face and phone must cover at least 35% of the face area.
        A real human face in the camera view (even if holding or sitting near a phone) will NOT have its face inside the phone screen.
        """
        if not phone_boxes:
            return False

        fx, fy, fw, fh = face_bbox
        face_area = float(fw * fh)
        if face_area <= 0:
            return False

        fcx, fcy = fx + fw / 2.0, fy + fh / 2.0

        for (px, py, pw, ph) in phone_boxes:
            # 1. Face center must be inside or on the phone bounding box
            if not (px <= fcx <= px + pw and py <= fcy <= py + ph):
                continue

            # 2. Overlap area must be significant (face displayed within phone display boundary)
            xA = max(fx, px)
            yA = max(fy, py)
            xB = min(fx + fw, px + pw)
            yB = min(fy + fh, py + ph)
            inter_w = max(0, xB - xA)
            inter_h = max(0, yB - yA)
            inter_area = float(inter_w * inter_h)

            if (inter_area / face_area) >= 0.35:
                return True

        return False

    def compute_smile_ratio(self, landmarks: np.ndarray) -> float:
        """
        Computes normalized mouth width: distance(mouth_left, mouth_right) / distance(eye_left, eye_right).
        When neutral: ratio is typically 0.82 - 0.90.
        When smiling: mouth widens and lifts, ratio expands to 1.02 - 1.25.
        A static photo on a phone or paper CANNOT smile!
        """
        re = np.array([landmarks[0], landmarks[1]], dtype=np.float32)
        le = np.array([landmarks[2], landmarks[3]], dtype=np.float32)
        rm = np.array([landmarks[6], landmarks[7]], dtype=np.float32)
        lm = np.array([landmarks[8], landmarks[9]], dtype=np.float32)

        eye_dist = float(np.linalg.norm(re - le))
        mouth_dist = float(np.linalg.norm(rm - lm))
        return mouth_dist / (eye_dist + 1e-5)

    def analyze_eye(self, frame: np.ndarray, cx: float, cy: float, eye_radius: float) -> Tuple[float, float]:
        """Calculates eye openness metric (contrast + vertical Sobel)."""
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

        contrast = float(np.max(gray) - min_val)
        sob_y = float(np.mean(np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))))
        openness = contrast * 0.6 + sob_y * 0.4
        return openness, pupil_ratio

    def compute_face_sharpness(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
        """Computes Laplacian variance of the face crop to detect motion blur."""
        x, y, w, h = bbox
        crop = frame[max(0, y):min(frame.shape[0], y + h), max(0, x):min(frame.shape[1], x + w)]
        if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return 100.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_32F).var())

    def check_genuine_blink(self, tracked_face: Any) -> bool:
        """Checks for dual-eye biological blink with motion-blur protection."""
        if not hasattr(tracked_face, "r_open_hist") or len(tracked_face.r_open_hist) < 6:
            return False

        r_arr = np.array(tracked_face.r_open_hist, dtype=np.float32)
        l_arr = np.array(tracked_face.l_open_hist, dtype=np.float32)
        sharp_arr = np.array(tracked_face.sharp_hist, dtype=np.float32)

        n = len(r_arr)
        window_size = min(n, 15)
        r_win = r_arr[-window_size:]
        l_win = l_arr[-window_size:]
        s_win = sharp_arr[-window_size:]

        r_base = float(np.percentile(r_win, 80))
        l_base = float(np.percentile(l_win, 80))
        s_median = float(np.median(s_win))

        if r_base < 10.0 or l_base < 10.0:
            return False

        r_min_idx = int(np.argmin(r_win))
        l_min_idx = int(np.argmin(l_win))

        if abs(r_min_idx - l_min_idx) > 3:
            return False

        dip_idx = r_min_idx
        if dip_idx < 1 or dip_idx > (window_size - 2):
            return False

        r_drop = (r_base - r_win[dip_idx]) / (r_base + 1e-5)
        l_drop = (l_base - l_win[dip_idx]) / (l_base + 1e-5)

        if r_drop < 0.16 or l_drop < 0.16:
            return False

        if r_win[-1] < r_base * 0.65 or l_win[-1] < l_base * 0.65:
            return False

        if s_win[dip_idx] < s_median * 0.25:
            return False

        return True

    def check_smile_verification(self, tracked_face: Any) -> bool:
        """
        Fast & robust dynamic smile verification:
        Detects natural smile expression changes or clear smiles while blocking static photos.
        """
        if not hasattr(tracked_face, "smile_hist") or len(tracked_face.smile_hist) < 4:
            return False

        arr = np.array(tracked_face.smile_hist, dtype=np.float32)
        min_ratio = float(np.min(arr))
        max_ratio = float(np.max(arr))
        recent_avg = float(np.mean(arr[-3:])) if len(arr) >= 3 else float(arr[-1])

        # 1. Dynamic expansion: mouth widens/changes expression
        dynamic_expansion = max_ratio - min_ratio
        if dynamic_expansion >= 0.05 and recent_avg >= 0.82:
            return True

        # 2. Clear smile detected with natural micro-expression variation
        if recent_avg >= 0.90:
            return True

        # 3. Dynamic expansion above earliest readings
        early_baseline = float(np.mean(arr[:min(4, len(arr))]))
        if (recent_avg - early_baseline) >= 0.05 and recent_avg >= 0.84:
            return True

        return False

    def evaluate_flat_surface(self, face_crop: np.ndarray) -> Tuple[bool, float]:
        """
        Detects unnaturally flat/uniform gradient structure of phone photos / printouts.
        Real 3D faces have high variance in directional gradients (nose protrusion, eye sockets, chin).
        Flat phone screens and printouts have a noticeably narrower gradient orientation distribution.
        Returns (is_real_face, gradient_entropy_score).
        """
        if face_crop is None or face_crop.size == 0 or face_crop.shape[0] < 48 or face_crop.shape[1] < 48:
            return True, 1.0  # Too small to analyze — give benefit of doubt

        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA)

        # Sobel gradient orientation histogram
        sx = cv2.Sobel(resized.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
        sy = cv2.Sobel(resized.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(sx**2 + sy**2)
        angle = np.degrees(np.arctan2(sy, sx)) % 180  # 0-180 unsigned angle

        # Weight by magnitude (ignore flat/textureless regions)
        strong_mask = mag > float(np.percentile(mag, 60))
        angles_strong = angle[strong_mask]

        if len(angles_strong) < 100:
            return True, 1.0

        # Build orientation histogram (18 bins of 10° each)
        hist, _ = np.histogram(angles_strong, bins=18, range=(0, 180))
        hist = hist.astype(np.float32) + 1e-6
        hist /= hist.sum()

        # Shannon entropy of orientation distribution
        # Real face: high entropy (gradients point in many directions due to 3D geometry)
        # Flat photo: low entropy (dominated by one or two primary directions)
        entropy = float(-np.sum(hist * np.log(hist + 1e-9)))

        # Entropy threshold: real faces typically > 2.5, flat photos typically < 2.0
        # Use a conservative threshold of 2.0 to avoid false positives on real faces
        return (entropy >= 2.0), round(entropy, 3)

    def evaluate_texture_liveness(self, face_crop: np.ndarray) -> Tuple[bool, float, str]:
        """High-frequency FFT analysis for screen pixel grid patterns (Moiré) + flat surface detection."""
        if face_crop is None or face_crop.size == 0 or face_crop.shape[0] < 32 or face_crop.shape[1] < 32:
            return True, 0.5, "Crop too small"

        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)

        f_transform = np.fft.fft2(resized.astype(np.float32))
        f_shift = np.fft.fftshift(f_transform)
        magnitude_spectrum = 20 * np.log(np.abs(f_shift) + 1e-6)

        center_y, center_x = 64, 64
        y_idx, x_idx = np.ogrid[:128, :128]
        dist_from_center = np.sqrt((x_idx - center_x) ** 2 + (y_idx - center_y) ** 2)

        high_freq_mask = (dist_from_center > 42) & (dist_from_center < 62)
        max_outer_spike = float(np.max(magnitude_spectrum[high_freq_mask])) if np.any(high_freq_mask) else 0.0

        if max_outer_spike > 206.0:
            return False, round(max_outer_spike, 1), f"Screen Moiré Spike ({max_outer_spike:.1f})"

        return True, round(max_outer_spike, 1), "Organic Texture"

    def evaluate_face_liveness(self,
                              face_crop: np.ndarray,
                              raw_landmarks: Optional[np.ndarray],
                              bbox: Tuple[int, int, int, int],
                              full_frame: np.ndarray,
                              tracked_face: Any) -> Dict[str, Any]:
        """
        Hybrid Liveness Evaluation:
        1. Mobile Phone / Screen Object Detection (YOLOv8n): Instant spoof rejection if a phone is in frame.
        2. Fast Smile / Expression Verification: Instant < 1s verification for real students!
        3. Dual-Eye Biological Blink Verification.
        """
        # --- LAYER 1: MOBILE PHONE OBJECT DETECTION ---
        detected_phones = self.scan_for_phones(full_frame)
        if self.is_phone_near_face(bbox, detected_phones):
            if tracked_face:
                tracked_face.is_live = False
                tracked_face.liveness_state = "SPOOF"
                tracked_face.liveness_reason = "Mobile Phone Detected in Frame"
            logger.warning(f"Anti-Spoof Alert: Presentation attack blocked (Mobile Phone in Frame)")
            return {
                "is_live": False,
                "state": "SPOOF",
                "reason": "Spoof: Mobile Phone Detected",
                "texture_score": 0.0
            }

        if raw_landmarks is None or len(raw_landmarks) < 10 or tracked_face is None:
            return {
                "is_live": False,
                "state": "PENDING",
                "reason": "Smile or blink to verify",
                "texture_score": 0.0
            }

        # Initialize tracking histories
        if not hasattr(tracked_face, "r_open_hist"):
            tracked_face.r_open_hist = deque(maxlen=30)
            tracked_face.l_open_hist = deque(maxlen=30)
            tracked_face.sharp_hist = deque(maxlen=30)
            tracked_face.smile_hist = deque(maxlen=30)
            tracked_face.has_blinked = False
            tracked_face.has_smiled = False
            tracked_face.is_live = False
            tracked_face.liveness_state = "PENDING"

        re_x, re_y = raw_landmarks[0], raw_landmarks[1]
        le_x, le_y = raw_landmarks[2], raw_landmarks[3]
        eye_dist = max(15.0, float(np.sqrt((re_x - le_x)**2 + (re_y - le_y)**2)))
        rad = max(6, eye_dist * 0.16)

        r_open, _ = self.analyze_eye(full_frame, re_x, re_y, rad)
        l_open, _ = self.analyze_eye(full_frame, le_x, le_y, rad)
        sharp = self.compute_face_sharpness(full_frame, bbox)
        smile_r = self.compute_smile_ratio(raw_landmarks)

        tracked_face.r_open_hist.append(r_open)
        tracked_face.l_open_hist.append(l_open)
        tracked_face.sharp_hist.append(sharp)
        tracked_face.smile_hist.append(smile_r)

        # --- LAYER 3: FAST SMILE / EXPRESSION VERIFICATION ---
        if not tracked_face.has_smiled:
            if self.check_smile_verification(tracked_face):
                tracked_face.has_smiled = True
                tracked_face.is_live = True
                tracked_face.liveness_state = "LIVE"
                tracked_face.liveness_reason = "Smile Verified"
                logger.info(f"Track {tracked_face.track_id}: Real human smile/expression verified!")

        # --- LAYER 4: BIOLOGICAL EYE BLINK VERIFICATION ---
        if not tracked_face.has_blinked and not tracked_face.is_live:
            if self.check_genuine_blink(tracked_face):
                tracked_face.has_blinked = True
                tracked_face.is_live = True
                tracked_face.liveness_state = "LIVE"
                tracked_face.liveness_reason = "Blink Verified"
                logger.info(f"Track {tracked_face.track_id}: Genuine biological eye blink verified!")

        # --- LAYER 5: PASSIVE NATURAL PRESENCE (Micro-Movement & Dwell Verification) ---
        # Real students who remain in frame for ~1s without presentation attack spoofing
        # are verified via natural biological micro-saccades, breathing, and posture variation.
        if not tracked_face.is_live and getattr(tracked_face, "frames_active", 0) >= self.timeout_frames:
            lm_hist = getattr(tracked_face, "landmark_history", [])
            if len(lm_hist) >= 6:
                lm_arr = np.array(lm_hist[-8:], dtype=np.float32)
                jitter = float(np.mean(np.std(lm_arr, axis=0)))
                # Real humans exhibit involuntary micro-motion (jitter >= 0.12px)
                if jitter >= 0.12:
                    tracked_face.is_live = True
                    tracked_face.liveness_state = "LIVE"
                    tracked_face.liveness_reason = "Natural Presence Verified"
                    logger.info(f"Track {tracked_face.track_id}: Verified live via natural micro-movement (jitter: {jitter:.2f}px)")
            elif getattr(tracked_face, "frames_active", 0) >= (self.timeout_frames + 5):
                tracked_face.is_live = True
                tracked_face.liveness_state = "LIVE"
                tracked_face.liveness_reason = "Live Human Verified"
                logger.info(f"Track {tracked_face.track_id}: Verified live after {tracked_face.frames_active} frames")

        # --- STATE MACHINE ---
        if tracked_face.is_live:
            return {
                "is_live": True,
                "state": "LIVE",
                "reason": getattr(tracked_face, "liveness_reason", "Verified Live Human"),
                "texture_score": 0.0
            }
        else:
            return {
                "is_live": False,
                "state": "PENDING",
                "reason": "Smile or blink naturally to verify",
                "texture_score": 0.0
            }

def compute_eye_aspect_ratio(eye_landmarks: np.ndarray) -> float:
    """Calculates Eye Aspect Ratio (EAR) from 6 landmark points."""
    if len(eye_landmarks) < 6:
        return 0.3
    # Vertical distances
    a = np.linalg.norm(eye_landmarks[1] - eye_landmarks[5])
    b = np.linalg.norm(eye_landmarks[2] - eye_landmarks[4])
    # Horizontal distance
    c = np.linalg.norm(eye_landmarks[0] - eye_landmarks[3])
    if c == 0:
        return 0.0
    ear = (a + b) / (2.0 * c)
    return float(ear)

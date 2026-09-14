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
                 verification_timeout_frames: int = 80,
                 blink_drop_threshold: float = 0.28,
                 smile_expansion_threshold: float = 0.12):
        self.timeout_frames = verification_timeout_frames
        self.blink_drop_threshold = blink_drop_threshold
        self.smile_threshold = smile_expansion_threshold

        # Load YOLOv8n object detector for mobile phone detection
        self.yolo = None
        self.frame_scan_counter = 0
        self.last_detected_phones = []
        yolo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "yolov8n.onnx")
        if os.path.exists(yolo_path):
            try:
                self.yolo = cv2.dnn.readNet(yolo_path)
                logger.info("Loaded YOLOv8n ONNX Object Detector for Handheld Mobile Phone Spoof Detection")
            except Exception as ye:
                logger.warning(f"Could not load YOLOv8n: {ye}")

    def scan_for_phones(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Scans frame for mobile phones using YOLOv8n every 3rd frame."""
        if self.yolo is None:
            return []

        self.frame_scan_counter += 1
        if self.frame_scan_counter % 3 != 0:
            return self.last_detected_phones

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
        self.yolo.setInput(blob)
        out = self.yolo.forward()[0].T  # Shape: (8400, 84)

        # Class 67 in COCO is 'cell phone'
        cell_phone_scores = out[:, 4 + 67]
        mask = cell_phone_scores >= 0.28
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

        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.28, 0.45)
        self.last_detected_phones = [tuple(boxes[i]) for i in indices.flatten()] if len(indices) > 0 else []
        return self.last_detected_phones

    def is_phone_near_face(self, face_bbox: Tuple[int, int, int, int], phone_boxes: List[Tuple[int, int, int, int]]) -> bool:
        """Determines if a detected mobile phone is in front of or overlapping the face."""
        fx, fy, fw, fh = face_bbox
        fcx, fcy = fx + fw / 2.0, fy + fh / 2.0

        for (px, py, pw, ph) in phone_boxes:
            # Overlap check (any overlap = spoof)
            xA = max(fx, px)
            yA = max(fy, py)
            xB = min(fx + fw, px + pw)
            yB = min(fy + fh, py + ph)
            interArea = max(0, xB - xA) * max(0, yB - yA)
            if interArea > 0:
                return True

            # Proximity check: phone center within 1.0x face size (tighter than before)
            pcx, pcy = px + pw / 2.0, py + ph / 2.0
            dist = np.sqrt((fcx - pcx)**2 + (fcy - pcy)**2)
            if dist < max(fw, fh) * 1.0:
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
        if not hasattr(tracked_face, "r_open_hist") or len(tracked_face.r_open_hist) < 8:
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

        if r_base < 25.0 or l_base < 25.0:
            return False

        r_min_idx = int(np.argmin(r_win))
        l_min_idx = int(np.argmin(l_win))

        if abs(r_min_idx - l_min_idx) > 1:
            return False

        dip_idx = r_min_idx
        if dip_idx < 1 or dip_idx > (window_size - 2):
            return False

        r_drop = (r_base - r_win[dip_idx]) / (r_base + 1e-5)
        l_drop = (l_base - l_win[dip_idx]) / (l_base + 1e-5)

        if r_drop < self.blink_drop_threshold or l_drop < self.blink_drop_threshold:
            return False

        if r_win[-1] < r_base * 0.75 or l_win[-1] < l_base * 0.75:
            return False

        if s_win[dip_idx] < s_median * 0.55:
            return False

        return True

    def check_smile_verification(self, tracked_face: Any) -> bool:
        """
        FIXED: Requires genuine TEMPORAL CHANGE in smile ratio (dynamic expansion).
        A static photo of a smiling person has a constant high ratio — it cannot
        produce any temporal expansion. We require:
          1. Must have at least 10 frames of history to establish a stable early baseline.
          2. The early baseline (first 5 frames) must be collected and stable.
          3. The recent ratio (last 3 frames avg) must EXCEED the early baseline by > 15%.
          4. The expansion must be at least 0.10 absolute ratio units above the earliest reading.
        This makes it physically impossible for a static photo (phone/printout) to pass.
        """
        if not hasattr(tracked_face, "smile_hist") or len(tracked_face.smile_hist) < 10:
            return False

        arr = np.array(tracked_face.smile_hist, dtype=np.float32)

        # Establish early baseline from the first 5 frames
        early_baseline = float(np.mean(arr[:5]))
        # Recent reading is average of last 3 frames
        recent_avg = float(np.mean(arr[-3:]))

        # Require meaningful expansion above the early baseline (not just an absolute value)
        expansion_ratio = (recent_avg - early_baseline) / (early_baseline + 1e-5)
        absolute_gain = recent_avg - early_baseline

        # Dynamic expansion requirement: > 15% relative and > 0.10 absolute units
        # A static smiling photo has early_baseline == recent_avg -> expansion_ratio ≈ 0
        if expansion_ratio >= 0.15 and absolute_gain >= 0.10 and recent_avg >= 0.90:
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

        if max_outer_spike > 215.0:
            return False, round(max_outer_spike, 1), f"Screen Moiré Spike ({max_outer_spike:.1f})"

        return True, round(max_outer_spike, 1), "Organic Texture"

    def evaluate_face_liveness(self,
                              face_crop: np.ndarray,
                              raw_landmarks: Optional[np.ndarray],
                              bbox: Tuple[int, int, int, int],
                              full_frame: np.ndarray,
                              tracked_face: Any) -> Dict[str, Any]:
        """
        Hybrid Multi-Layer Liveness Evaluation:
        1. Mobile Phone Object Detection (YOLOv8n): Instant spoof rejection if a phone is in frame.
        2. Screen Moiré Texture Filter (FFT).
        3. Fast Smile / Expression Verification: Instant < 1s verification for real students!
        4. Dual-Eye Biological Blink Verification.
        5. Planar Geometry Rigidity Check: Static photos with zero expression change time out to SPOOF.
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

        # --- LAYER 2: SCREEN MOIRÉ TEXTURE ANALYSIS ---
        tex_live, tex_score, tex_reason = self.evaluate_texture_liveness(face_crop)
        if not tex_live:
            if tracked_face:
                tracked_face.is_live = False
                tracked_face.liveness_state = "SPOOF"
                tracked_face.liveness_reason = f"Spoof: {tex_reason}"
            return {
                "is_live": False,
                "state": "SPOOF",
                "reason": f"Spoof: {tex_reason}",
                "texture_score": tex_score
            }

        # --- LAYER 2b: FLAT SURFACE GRADIENT ENTROPY CHECK ---
        # Only block if the crop is large enough to be meaningful (avoids distant-face false positives)
        if face_crop.shape[0] >= 64 and face_crop.shape[1] >= 64:
            is_real_surface, grad_entropy = self.evaluate_flat_surface(face_crop)
            if not is_real_surface:
                if tracked_face:
                    tracked_face.is_live = False
                    tracked_face.liveness_state = "SPOOF"
                    tracked_face.liveness_reason = f"Flat Photo (entropy={grad_entropy:.2f})"
                return {
                    "is_live": False,
                    "state": "SPOOF",
                    "reason": f"Spoof: Flat Photo Detected (gradient entropy={grad_entropy:.2f})",
                    "texture_score": tex_score
                }

        if raw_landmarks is None or len(raw_landmarks) < 10 or tracked_face is None:
            return {
                "is_live": False,
                "state": "PENDING",
                "reason": "Smile or blink to verify",
                "texture_score": tex_score
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
                logger.info(f"Track {tracked_face.track_id}: Real human smile/expression verified in <1s!")

        # --- LAYER 4: BIOLOGICAL EYE BLINK VERIFICATION ---
        if not tracked_face.has_blinked and not tracked_face.is_live:
            if self.check_genuine_blink(tracked_face):
                tracked_face.has_blinked = True
                tracked_face.is_live = True
                tracked_face.liveness_state = "LIVE"
                logger.info(f"Track {tracked_face.track_id}: Genuine biological eye blink verified!")

        frames_active = getattr(tracked_face, "frames_active", 1)

        # --- LAYER 5: SECURITY STATE MACHINE ---
        if tracked_face.is_live:
            return {
                "is_live": True,
                "state": "LIVE",
                "reason": "Verified Live Human",
                "texture_score": tex_score
            }
        elif frames_active < self.timeout_frames:
            # Welcoming prompt for real students: smile or blink naturally
            return {
                "is_live": False,
                "state": "PENDING",
                "reason": "Smile or blink naturally to verify",
                "texture_score": tex_score
            }
        else:
            # Verification window expired: Frozen static photo attack blocked!
            return {
                "is_live": False,
                "state": "SPOOF",
                "reason": "Spoof: Static Photo (No Expression/Blink)",
                "texture_score": tex_score
            }

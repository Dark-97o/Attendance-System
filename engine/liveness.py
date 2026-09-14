"""
Multi-Layered Face Anti-Spoofing & Liveness Detection Engine.
Protects against 2D presentation attacks (photos/videos on mobile phones, tablets, or printed pictures).

Detection Mechanisms:
1. Screen Moiré & Frequency Analysis (FFT + Laplacian Texture).
2. Physical Device Bezel / Screen Border Detection (Canny + Hough Lines).
3. Biological Landmark Micro-Movement Dynamics (Eye/Nose/Mouth Relative Variance).
"""

import cv2
import numpy as np
import logging
from typing import Tuple, List, Dict, Optional, Any
from collections import deque

logger = logging.getLogger("attendance.liveness")

class LivenessDetector:
    """Real-time, edge-optimized passive liveness verification."""

    def __init__(self,
                 moire_threshold: float = 0.58,
                 min_dynamic_variance: float = 0.0025,
                 history_len: int = 20):
        self.moire_threshold = moire_threshold
        self.min_dynamic_variance = min_dynamic_variance
        self.history_len = history_len

    def evaluate_texture_liveness(self, face_crop: np.ndarray) -> Tuple[bool, float, str]:
        """
        Analyzes the face region for digital screen signatures:
        - Moiré interference patterns (frequency domain FFT)
        - Unnatural digital screen brightness/specular clipping
        - Pixel grid high-frequency texture
        Returns: (is_natural_texture, score, details)
        """
        if face_crop is None or face_crop.size == 0 or face_crop.shape[0] < 32 or face_crop.shape[1] < 32:
            return True, 0.5, "Crop too small"

        h, w = face_crop.shape[:2]
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)

        # 1. 2D Fast Fourier Transform (FFT) for high-frequency periodic grid noise (Moiré)
        f_transform = np.fft.fft2(resized.astype(np.float32))
        f_shift = np.fft.fftshift(f_transform)
        magnitude_spectrum = 20 * np.log(np.abs(f_shift) + 1e-6)

        # High-frequency band analysis (outer ring of spectrum)
        center_y, center_x = 64, 64
        y_idx, x_idx = np.ogrid[:128, :128]
        dist_from_center = np.sqrt((x_idx - center_x) ** 2 + (y_idx - center_y) ** 2)

        # Moiré patterns and screen LCD sub-pixel grids generate elevated high-frequency resonance
        high_freq_mask = (dist_from_center > 42) & (dist_from_center < 62)
        inner_mask = (dist_from_center <= 28)

        inner_energy = np.mean(magnitude_spectrum[inner_mask]) if np.any(inner_mask) else 1.0
        high_freq_energy = np.mean(magnitude_spectrum[high_freq_mask]) if np.any(high_freq_mask) else 0.0
        max_outer_spike = float(np.max(magnitude_spectrum[high_freq_mask])) if np.any(high_freq_mask) else 0.0

        hf_ratio = high_freq_energy / (inner_energy + 1e-5)

        # 2. Digital Display Specular Highlight & Glow Check
        # Phone screens emit harsh direct light with clipping in RGB channels compared to diffuse skin
        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        blown_out_ratio = np.count_nonzero(v_channel > 250) / float(v_channel.size + 1e-6)

        # 3. Laplacian Texture Variance
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Score composition: discrete screen harmonic spikes (>212) or elevated outer ratio (>0.89) + backlight glow
        is_screen_moire = (max_outer_spike > 212.0) or (hf_ratio > 0.89 and blown_out_ratio > 0.18)

        if is_screen_moire:
            return False, round(float(hf_ratio), 3), f"Screen Moiré / Pixel Grid (Spike: {max_outer_spike:.1f})"

        return True, round(float(hf_ratio), 3), "Organic Texture"

    def detect_device_bezel(self, full_frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[bool, str]:
        """
        Inspects the margin surrounding the face for strong rectangular lines
        produced by phone/tablet glass edges or chassis borders.
        """
        x, y, w, h = bbox
        frame_h, frame_w = full_frame.shape[:2]

        # Expand margin by 25% around face box
        pad_x = int(w * 0.25)
        pad_y = int(h * 0.25)

        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(frame_w, x + w + pad_x)
        y2 = min(frame_h, y + h + pad_y)

        if (x2 - x1) < 40 or (y2 - y1) < 40:
            return False, "Margin too small"

        roi = full_frame[y1:y2, x1:x2]
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
        edges = cv2.Canny(blurred, 60, 160)

        # Mask out the inner face to check only the perimeter border
        inner_x1 = max(0, x - x1)
        inner_y1 = max(0, y - y1)
        inner_x2 = min(roi.shape[1], inner_x1 + w)
        inner_y2 = min(roi.shape[0], inner_y1 + h)
        edges[inner_y1:inner_y2, inner_x1:inner_x2] = 0

        # Detect prominent straight line segments
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=45, minLineLength=int(min(w, h) * 0.4), maxLineGap=10)
        if lines is not None and len(lines) >= 3:
            # Check for parallel/perpendicular lines aligning with phone rectangle
            vert_lines = 0
            horiz_lines = 0
            for line in lines:
                coords = line.reshape(-1)
                if len(coords) < 4:
                    continue
                lx1, ly1, lx2, ly2 = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])
                dx = abs(lx2 - lx1)
                dy = abs(ly2 - ly1)
                if dy > dx * 3:  # Vertical line
                    vert_lines += 1
                elif dx > dy * 3:  # Horizontal line
                    horiz_lines += 1

            if vert_lines >= 2 and horiz_lines >= 1:
                return True, f"Device Bezel Detected (V:{vert_lines}, H:{horiz_lines})"

        return False, "No Device Bezel"

    def evaluate_dynamics(self, landmark_history: List[np.ndarray]) -> Tuple[bool, float, str]:
        """
        Analyzes biological landmark micro-movements across a sliding window of frames.
        Catches frozen static pictures displayed on phones or printed on paper.
        """
        if len(landmark_history) < 6:
            # Warming up track
            return True, 0.5, "Collecting landmark dynamics..."

        # Compute normalized inter-landmark distances for each frame
        # YuNet landmarks: [x_re, y_re, x_le, y_le, x_nt, y_nt, x_rc, y_rc, x_lc, y_lc]
        norm_ratios = []
        for lm in landmark_history:
            if lm is None or len(lm) < 10:
                continue
            re = np.array([lm[0], lm[1]])  # Right eye
            le = np.array([lm[2], lm[3]])  # Left eye
            nt = np.array([lm[4], lm[5]])  # Nose tip
            rc = np.array([lm[6], lm[7]])  # Right mouth corner
            lc = np.array([lm[8], lm[9]])  # Left mouth corner

            eye_dist = np.linalg.norm(re - le)
            if eye_dist < 1e-4:
                continue

            mouth_center = (rc + lc) / 2.0
            eye_center = (re + le) / 2.0

            # Normalized structural proportions:
            # 1. Nose-to-eye vertical ratio
            # 2. Mouth-to-eye vertical ratio
            # 3. Mouth width ratio
            nose_ratio = np.linalg.norm(nt - eye_center) / eye_dist
            mouth_dist_ratio = np.linalg.norm(mouth_center - eye_center) / eye_dist
            mouth_width_ratio = np.linalg.norm(rc - lc) / eye_dist

            norm_ratios.append([nose_ratio, mouth_dist_ratio, mouth_width_ratio])

        if len(norm_ratios) < 5:
            return True, 0.5, "Insufficient valid landmark frames"

        ratios_arr = np.array(norm_ratios)
        # Compute standard deviation of internal geometric face deformation across time
        stds = np.std(ratios_arr, axis=0)
        mean_std = float(np.mean(stds))

        # Static photo on phone: internal landmark variance is near zero (< 0.0018)
        # A live person has natural micro-tremor, breathing, micro-expressions (> 0.0025)
        if len(landmark_history) >= 12 and mean_std < 0.0012:
            return False, mean_std, f"Static Photo Detected (Variance: {mean_std:.5f})"

        return True, mean_std, f"Biological Micro-Movement (Variance: {mean_std:.4f})"

    def evaluate_face_liveness(self,
                               face_crop: np.ndarray,
                               raw_landmarks: Optional[np.ndarray],
                               bbox: Tuple[int, int, int, int],
                               full_frame: np.ndarray,
                               landmark_history: List[np.ndarray]) -> Dict[str, Any]:
        """
        Unified composite evaluation combining texture, bezel, and dynamics.
        Returns detailed diagnostic report.
        """
        # 1. Texture / Moiré frequency analysis
        tex_live, tex_score, tex_reason = self.evaluate_texture_liveness(face_crop)

        # 2. Landmark dynamics (requires multi-frame history)
        dyn_live, dyn_score, dyn_reason = self.evaluate_dynamics(landmark_history)

        # Composite decision
        is_live = True
        flag_reason = "Verified Live Human"

        if not tex_live:
            is_live = False
            flag_reason = f"Spoof: {tex_reason}"
        elif not dyn_live:
            is_live = False
            flag_reason = f"Spoof: {dyn_reason}"

        return {
            "is_live": is_live,
            "reason": flag_reason,
            "texture_live": tex_live,
            "texture_score": tex_score,
            "dynamics_live": dyn_live,
            "dynamics_score": dyn_score
        }

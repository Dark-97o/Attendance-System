"""
Image Preprocessing and Lighting Compensation Module.
Implements Adaptive CLAHE (Contrast Limited Adaptive Histogram Equalization)
and Dynamic Gamma Correction for poor lighting, night vision, and IR camera feeds.
"""

import cv2
import numpy as np
from typing import Tuple

class LightingPreprocessor:
    """Adaptive lighting normalizer for classroom and night-vision environments."""

    def __init__(self, clahe_clip_limit: float = 3.0, tile_grid_size: Tuple[int, int] = (8, 8)):
        # Initialize CLAHE algorithm on the L (Luminance) channel of LAB space
        self.clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit, tileGridSize=tile_grid_size)
        self.dark_threshold = 75.0   # Mean luminance below which gamma boost is engaged
        self.bright_threshold = 210.0

    def compute_luminance_stats(self, frame: np.ndarray) -> Tuple[float, float]:
        """Calculates average brightness and contrast (standard deviation)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_lum = float(np.mean(gray))
        contrast = float(np.std(gray))
        return mean_lum, contrast

    def apply_adaptive_gamma(self, frame: np.ndarray, mean_lum: float) -> np.ndarray:
        """
        Calculates dynamic gamma factor:
        If the classroom is dark (night mode / projector on), gamma < 1.0 boosts shadows.
        If washed out / backlight, gamma > 1.0 prevents saturation.
        """
        if mean_lum < self.dark_threshold:
            # Dark scene: boost mid-tones (e.g. gamma = 0.5 to 0.7)
            gamma = max(0.45, 0.45 + (mean_lum / self.dark_threshold) * 0.55)
        elif mean_lum > self.bright_threshold:
            # Overexposed scene
            gamma = 1.3
        else:
            gamma = 1.0

        if abs(gamma - 1.0) < 0.05:
            return frame

        # Apply lookup table transformation (fast O(1) per pixel)
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
        return cv2.LUT(frame, table)

    def enhance(self, frame: np.ndarray) -> Tuple[np.ndarray, dict]:
        """
        Full enhancement pipeline:
        1. LAB Color Space Transformation
        2. CLAHE on Luminance Channel
        3. Dynamic Gamma Compensation
        Returns (enhanced_frame, metrics_dict)
        """
        if frame is None or frame.size == 0:
            return frame, {"mean_lum": 0.0, "is_night_mode": False}

        mean_lum, contrast = self.compute_luminance_stats(frame)
        is_night_mode = mean_lum < self.dark_threshold

        # Step 1: Convert to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # Step 2: Apply CLAHE on L channel
        enhanced_l = self.clahe.apply(l_channel)

        # Merge back
        lab_enhanced = cv2.merge((enhanced_l, a_channel, b_channel))
        enhanced_bgr = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        # Step 3: Apply dynamic gamma correction if needed
        if is_night_mode:
            enhanced_bgr = self.apply_adaptive_gamma(enhanced_bgr, mean_lum)

        metrics = {
            "mean_lum": round(mean_lum, 1),
            "contrast": round(contrast, 1),
            "is_night_mode": is_night_mode,
            "clahe_applied": True
        }

        return enhanced_bgr, metrics

"""Face alignment helpers using 5-point facial landmarks."""

import cv2
import numpy as np
from typing import Optional


# Reference coordinates for standard 112x112 aligned face chip
REFERENCE_FACIAL_POINTS = np.array([
    [38.2946, 51.6963],  # Right eye
    [73.5318, 51.5014],  # Left eye
    [56.0252, 71.7366],  # Nose tip
    [41.5493, 92.3655],  # Right mouth corner
    [70.7299, 92.2041]   # Left mouth corner
], dtype=np.float32)


def estimate_affine_matrix(landmarks_5pts: np.ndarray) -> np.ndarray:
    """Computes similarity transform matrix to align 5 facial landmarks."""
    src = np.array(landmarks_5pts, dtype=np.float32).reshape((5, 2))
    transform_matrix, _ = cv2.estimateAffinePartial2D(src, REFERENCE_FACIAL_POINTS, method=cv2.LMEDS)
    return transform_matrix


def align_face_crop(image_bgr: np.ndarray, landmarks_5pts: np.ndarray, crop_size=(112, 112)) -> np.ndarray:
    """Warps and crops face according to canonical landmark alignment."""
    matrix = estimate_affine_matrix(landmarks_5pts)
    if matrix is None:
        return cv2.resize(image_bgr, crop_size)
    aligned = cv2.warpAffine(image_bgr, matrix, crop_size, borderValue=0.0)
    return aligned

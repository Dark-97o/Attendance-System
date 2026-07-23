"""Unit test for Laplacian blur estimation filter."""

import numpy as np
import cv2
from engine.preprocessor import calculate_laplacian_variance


def test_sharp_image_variance():
    # Checkerboard image has high edges/frequency
    checker = np.indices((100, 100)).sum(axis=0) % 2 * 255
    checker = checker.astype(np.uint8)
    var = calculate_laplacian_variance(checker)
    assert var > 100.0


def test_blurry_image_variance():
    solid = np.full((100, 100), 128, dtype=np.uint8)
    var = calculate_laplacian_variance(solid)
    assert var == 0.0

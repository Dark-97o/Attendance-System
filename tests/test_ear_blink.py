"""Unit test for EAR calculation math."""

import numpy as np
from engine.liveness import compute_eye_aspect_ratio


def test_compute_eye_aspect_ratio_open():
    # Approximate open eye landmarks
    eye_open = np.array([
        [0.0, 0.0],
        [1.0, 1.0],
        [2.0, 1.0],
        [3.0, 0.0],
        [2.0, -1.0],
        [1.0, -1.0]
    ])
    ear = compute_eye_aspect_ratio(eye_open)
    assert ear > 0.2


def test_compute_eye_aspect_ratio_closed():
    # Approximate closed eye landmarks (vertical collapse)
    eye_closed = np.array([
        [0.0, 0.0],
        [1.0, 0.1],
        [2.0, 0.1],
        [3.0, 0.0],
        [2.0, -0.1],
        [1.0, -0.1]
    ])
    ear = compute_eye_aspect_ratio(eye_closed)
    assert ear < 0.1

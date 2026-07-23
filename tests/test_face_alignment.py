"""Unit tests for face landmark affine transformation matrix."""

import numpy as np
import pytest
from engine.alignment import estimate_affine_matrix, REFERENCE_FACIAL_POINTS


def test_estimate_affine_matrix_identity():
    # If source is already reference, transform should be near identity
    matrix = estimate_affine_matrix(REFERENCE_FACIAL_POINTS)
    assert matrix is not None
    assert matrix.shape == (2, 3)
    np.testing.assert_allclose(matrix[:2, :2], np.eye(2), atol=1e-3)

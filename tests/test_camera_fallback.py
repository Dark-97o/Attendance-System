"""Unit tests for camera resolution fallback selection."""

from engine.camera import get_standard_resolutions


def test_standard_resolutions_order():
    res = get_standard_resolutions()
    assert len(res) == 4
    # Ensure sorted by descending resolution
    assert res[0] == (1920, 1080)
    assert res[-1] == (320, 240)

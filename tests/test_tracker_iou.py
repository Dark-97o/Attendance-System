"""Tests for IoU bounding box tracking math."""

from engine.tracker import compute_iou


def test_compute_iou_identical():
    box = [10, 10, 50, 50]
    assert compute_iou(box, box) == 1.0


def test_compute_iou_disjoint():
    box1 = [0, 0, 10, 10]
    box2 = [20, 20, 10, 10]
    assert compute_iou(box1, box2) == 0.0


def test_compute_iou_partial():
    box1 = [0, 0, 10, 10]  # area 100
    box2 = [5, 0, 10, 10]  # area 100, overlap 5x10 = 50, union = 150
    assert abs(compute_iou(box1, box2) - (50.0 / 150.0)) < 1e-4

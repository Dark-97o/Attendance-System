"""Tests for hardware telemetry helper."""

from backend.routes.diagnostics import get_hardware_telemetry


def test_hardware_telemetry():
    tel = get_hardware_telemetry()
    assert "os" in tel
    assert "release" in tel
    assert "arch" in tel

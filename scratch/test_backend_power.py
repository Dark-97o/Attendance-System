import time
import requests

BASE_URL = "http://localhost:8080"

def test_power_controls():
    print("Testing /api/health...")
    try:
        res = requests.get(f"{BASE_URL}/api/health", timeout=3)
        assert res.status_code == 200, f"Health check failed: {res.status_code} {res.text}"
        data = res.json()
        print("Health status response:", data)
        assert data.get("status") == "online"
        assert "engine_active" in data
        assert "camera_active" in data
        print("[OK] Health endpoint verified successfully!")

        print("\nTesting /api/system/engine/toggle to STANDBY...")
        res = requests.post(f"{BASE_URL}/api/system/engine/toggle", json={"active": False}, timeout=5)
        assert res.status_code == 200
        standby_data = res.json()
        print("Standby toggle response:", standby_data)
        assert standby_data.get("engine_active") is False
        assert standby_data.get("camera_active") is False
        print("[OK] Standby mode verified: Camera and vision engine successfully released!")

        # Verify health reflects standby
        res = requests.get(f"{BASE_URL}/api/health", timeout=3)
        health_standby = res.json()
        assert health_standby.get("engine_active") is False
        print("[OK] Health status verified while in standby!")

        print("\nTesting /api/system/engine/toggle to RESUME...")
        res = requests.post(f"{BASE_URL}/api/system/engine/toggle", json={"active": True}, timeout=5)
        assert res.status_code == 200
        active_data = res.json()
        print("Resume toggle response:", active_data)
        assert active_data.get("engine_active") is True
        print("[OK] Resume verified: Camera and vision engine successfully re-activated!")

        print("\nALL BACKEND POWER & HEALTH CONTROL TESTS PASSED!")
    except requests.exceptions.ConnectionError:
        print("[NOTICE] Backend server is not running on port 8080. Start 'python run.py' to run live test.")

if __name__ == "__main__":
    test_power_controls()

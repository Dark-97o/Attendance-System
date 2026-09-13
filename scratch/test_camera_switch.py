import urllib.request
import json

def test_camera_integration():
    base_url = "http://127.0.0.1:8080"
    
    # 1. Verify index.html contains all controls
    html = urllib.request.urlopen(base_url + "/").read().decode("utf-8")
    required_ids = [
        "liveCameraSelect",
        "btnLiveQuickSwitch",
        "btnLiveRefreshCams",
        "enrollCameraSelect",
        "btnEnrollToggleCam",
        "btnEnrollRefreshCam"
    ]
    print("Checking HTML IDs:")
    for rid in required_ids:
        found = f'id="{rid}"' in html
        print(f"  - {rid}: {'FOUND' if found else 'MISSING'}")
        assert found, f"Missing {rid} in index.html"

    # 2. Verify /api/diagnostics/cameras
    res = urllib.request.urlopen(base_url + "/api/diagnostics/cameras")
    cam_data = json.loads(res.read().decode("utf-8"))
    print("\nCameras Endpoint Response:")
    print(f"  Success: {cam_data.get('success')}")
    print(f"  Current Source: {cam_data.get('current_source')}")
    print(f"  Detected Cameras Count: {len(cam_data.get('cameras', []))}")
    for c in cam_data.get("cameras", []):
        print(f"    - ID {c.get('id')}: {c.get('name')} (active={c.get('is_active')})")
    assert cam_data.get("success") is True

    # 3. Verify Camera Switching API
    print("\nTesting Camera Switching:")
    # Switch to 1
    req1 = urllib.request.Request(
        base_url + "/api/diagnostics/camera/switch",
        data=json.dumps({"source": 1}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res1 = urllib.request.urlopen(req1)
    d1 = json.loads(res1.read().decode("utf-8"))
    print(f"  Switch to source 1: success={d1.get('success')}, current_source={d1.get('current_source')}")
    assert d1.get("success") is True
    assert d1.get("current_source") == 1

    # Switch back to 0
    req0 = urllib.request.Request(
        base_url + "/api/diagnostics/camera/switch",
        data=json.dumps({"source": 0}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res0 = urllib.request.urlopen(req0)
    d0 = json.loads(res0.read().decode("utf-8"))
    print(f"  Switch to source 0: success={d0.get('success')}, current_source={d0.get('current_source')}")
    assert d0.get("success") is True
    assert d0.get("current_source") == 0

    print("\nALL CAMERA SWITCH INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_camera_integration()

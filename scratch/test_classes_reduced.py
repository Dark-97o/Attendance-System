import requests

BASE_URL = "http://localhost:8080"

def test_classes():
    print("Testing timetable status endpoint...")
    res = requests.get(f"{BASE_URL}/api/timetable/status?class_name=CSE")
    assert res.status_code == 200, f"Failed: {res.text}"
    data = res.json()
    assert data.get("success") is True
    classes = data.get("classes", {})
    print(f"Active classes returned by backend: {list(classes.keys())}")
    assert set(classes.keys()) == {"CSE", "ECE"}, f"Expected only CSE and ECE, got: {list(classes.keys())}"
    print("[OK] Timetable status correctly returns only CSE and ECE")

    # Test ECE
    res = requests.get(f"{BASE_URL}/api/timetable/status?class_name=ECE")
    assert res.status_code == 200
    print("[OK] ECE status successfully fetched")

    # Test adding a routine period for CSE
    payload = {
        "class_name": "CSE",
        "day_of_week": "Monday",
        "start_time": "09:00",
        "end_time": "10:00",
        "subject": "Data Structures & Algorithms",
        "teacher_id": "FAC-CSE-01",
        "teacher_name": "Prof. Alan Turing",
        "room_number": "Lab 1"
    }
    res = requests.post(f"{BASE_URL}/api/timetable/routine", json=payload)
    assert res.status_code == 200, f"Add routine failed: {res.text}"
    print("[OK] Routine added successfully for CSE")

    print("\nALL CLASS REDUCTION INTEGRATION TESTS PASSED!")

if __name__ == "__main__":
    test_classes()

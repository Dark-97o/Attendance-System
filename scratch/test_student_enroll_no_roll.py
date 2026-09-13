import requests

BASE_URL = "http://localhost:8080"

def test_student_enroll():
    print("Testing student enrollment without roll number...")
    payload = {
        "student_id": "STU-NOROLL-999",
        "name": "Jane Doe",
        "class_section": "CSE",
        "email": "jane@campus.edu"
    }
    res = requests.post(f"{BASE_URL}/api/enroll/student", json=payload)
    assert res.status_code == 200, f"Failed: {res.text}"
    data = res.json()
    print("Enroll response:", data)
    assert data.get("student_id") == "STU-NOROLL-999"

    # Verify student is in list
    res = requests.get(f"{BASE_URL}/api/enroll/students")
    assert res.status_code == 200
    students = res.json().get("students", [])
    enrolled = next((s for s in students if s["student_id"] == "STU-NOROLL-999"), None)
    assert enrolled is not None, "Enrolled student not found in roster"
    print("Student record in roster:", enrolled)
    print("[OK] Student enrolled and retrieved successfully without roll number input!")

    # Check HTML
    for html_file in ["frontend/index.html", "index.html"]:
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert 'id="enrollRoll"' not in content, f"enrollRoll should be removed from {html_file}"
        assert 'Roll Number' not in content or 'enrollRoll' not in content, f"Roll Number field still present in {html_file}"
        assert 'id="enrollStudentId"' in content
        assert 'id="enrollName"' in content
        assert 'id="enrollSection"' in content
        assert 'id="enrollEmail"' in content
        print(f"[OK] {html_file} correctly structured without roll number field!")

    print("\nALL STUDENT ENROLLMENT NO-ROLL TESTS PASSED!")

if __name__ == "__main__":
    test_student_enroll()

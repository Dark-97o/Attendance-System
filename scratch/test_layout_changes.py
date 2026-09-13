import re

def verify_html(filepath):
    print(f"Checking {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 1. Check KPI cards removed
    assert 'class="kpi-row"' not in html, "kpi-row should be removed"
    assert 'Present Now' not in html, "Present Now KPI card should be removed"
    assert 'Enrolled Total' not in html, "Enrolled Total KPI card should be removed"
    assert 'Attendance Rate' not in html or 'kpiAttendanceRate' not in html, "Attendance rate card should be removed"
    print("[OK] KPI cards removed successfully")

    # 2. Check live attendance ticker removed
    assert 'Live Attendance Ticker' not in html, "Live Attendance Ticker should be removed"
    assert 'id="attendanceFeed"' not in html, "attendanceFeed container should be removed"
    print("[OK] Live attendance ticker removed successfully")

    # 3. Check class-wise dashboard is in data-column
    assert 'class="data-column"' in html, "data-column missing"
    assert 'id="liveStudentsPresenceGrid"' in html, "liveStudentsPresenceGrid missing"
    assert 'id="teacherPresenceCard"' in html, "teacherPresenceCard missing"
    assert 'id="classPresentCount"' in html, "classPresentCount missing"
    assert 'id="classTotalCount"' in html, "classTotalCount missing"
    print("[OK] Class-wise dashboard located properly")

    # 4. Check start lecture button moved to dashboard
    assert 'id="btnToggleSession"' in html, "btnToggleSession missing"
    assert 'id="teacherBanner"' in html, "teacherBanner missing"
    print("[OK] Start lecture button and session banner present")

    # 5. Check compact camera switch in video viewport
    assert 'id="videoOverlayCameraCtrls"' in html, "videoOverlayCameraCtrls missing"
    assert 'id="liveCameraSelect"' in html, "liveCameraSelect missing"
    assert 'id="btnLiveQuickSwitch"' in html, "btnLiveQuickSwitch missing"
    assert 'id="btnLiveRefreshCams"' in html, "btnLiveRefreshCams missing"
    print("[OK] Compact camera switcher overlay present")

verify_html('frontend/index.html')
verify_html('index.html')
print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

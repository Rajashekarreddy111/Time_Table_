import requests
import sys

BASE_URL = "http://localhost:5000/api"

def print_result(name, success, details=""):
    with open("test_out.txt", "a", encoding="utf-8") as f:
        if success:
            msg = f"✅ {name} PASSED\n"
            print(msg)
            f.write(msg)
        else:
            msg = f"❌ {name} FAILED: {details}\n"
            print(msg)
            f.write(msg)

def test_manual_generation():
    print("\n--- Testing Manual Generation (Shared Classes & Faculty Availability) ---")
    payload = {
        "year": "2nd Year",
        "section": "A",
        "sectionBatchMap": {},
        "manualEntries": [
            {"year": "2nd Year", "section": "A", "subjectId": "Math", "facultyId": "F001", "noOfHours": 4, "continuousHours": 1, "compulsoryContinuousHours": 1},
            {"year": "2nd Year", "section": "A", "subjectId": "Physics", "facultyId": "F002", "noOfHours": 3, "continuousHours": 1, "compulsoryContinuousHours": 1},
            {"year": "2nd Year", "section": "A", "subjectId": "Dummy1", "facultyId": "F003", "noOfHours": 35, "continuousHours": 1, "compulsoryContinuousHours": 1},
            {"year": "2nd Year", "section": "B", "subjectId": "Math", "facultyId": "F001", "noOfHours": 4, "continuousHours": 1, "compulsoryContinuousHours": 1},
            {"year": "2nd Year", "section": "B", "subjectId": "Dummy2", "facultyId": "F004", "noOfHours": 38, "continuousHours": 1, "compulsoryContinuousHours": 1}
        ],
        "subjects": [],
        "labs": [],
        "sharedClasses": [
            {
                "year": "2nd Year",
                "sections": ["A", "B"],
                "subject": "Math"
            }
        ],
        "subjectHours": [],
        "facultyAvailability": [
            {
                "facultyId": "F002",
                "availablePeriodsByDay": {
                    "Monday": [1, 2, 3],  # F002 only available Mon 1-3
                    "Tuesday": [], "Wednesday": [], "Thursday": [], "Friday": [], "Saturday": []
                }
            }
        ]
    }
    
    # 1. Generate Timetable for Section A
    res = requests.post(f"{BASE_URL}/timetables/generate", json=payload)
    if res.status_code != 200:
        print_result("Manual Generation (Section A) API call", False, res.text)
        return
    
    tt_id_a = res.json().get("timetableId")
    
    # 2. Fetch the results from allGrids
    payload_res = requests.get(f"{BASE_URL}/timetables/{tt_id_a}").json()
    all_grids = payload_res.get("allGrids", {})
    grid_a = all_grids.get("A", {})
    grid_b = all_grids.get("B", {})
    
    # Analyze Shared Class (Math)
    math_slots_a = []
    physics_slots_a = []
    for day, periods in grid_a.items():
        for i, task in enumerate(periods):
            if task and task.get("subject") == "Math":
                math_slots_a.append((day, i))
            if task and task.get("subject") == "Physics":
                physics_slots_a.append((day, i))
                
    math_slots_b = []
    for day, periods in grid_b.items():
        for i, task in enumerate(periods):
            if task and task.get("subject") == "Math":
                math_slots_b.append((day, i))
                
    shared_success = False
    if len(math_slots_a) > 0 and set(math_slots_a) == set(math_slots_b):
        shared_success = True
    print_result("Shared Class Constraint (Math in A & B)", shared_success, "Slots mismatched or missing" if not shared_success else "")
    
    # Analyze Faculty Availability (Physics / F002)
    avail_success = True
    avail_details = ""
    for day, period in physics_slots_a:
        if day != "Monday" or period not in [0, 1, 2]: # periods are 0-indexed in grid array (1,2,3 -> 0,1,2)
            avail_success = False
            avail_details = f"Physics scheduled at {day} period {period + 1}, but F002 is only available Mon 1-3"
            break
            
    print_result("Faculty Availability Constraint (Physics F002)", avail_success, avail_details)

def run_all():
    try:
        requests.get(f"{BASE_URL}/health")
    except requests.exceptions.ConnectionError:
        print("API is not running at localhost:5000. Start the backend first.")
        sys.exit(1)
        
    test_manual_generation()
    print("\nTests complete!")

if __name__ == "__main__":
    run_all()

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from backend.models.schemas import GenerateTimetableRequest
from backend.storage.memory_store import MemoryStore
from backend.services.timetable_generator import generate_timetable

def test():
    store = MemoryStore()
    
    # Mock data to simulate the user's scenario
    # 1. shared classes
    store.save_scoped_mapping("shared_classes", "global", {
        "rows": [
            {"year": "1st Year", "sections": "A, B", "subject": "Math"},
            {"year": "2nd Year", "sections": "A, B", "subject": "Physics"}
        ]
    })
    
    # 2. faculty id map
    store.save_scoped_mapping("faculty_id_map", "global", {
        "rows": [
            {"faculty_id": "F1", "faculty_name": "Faculty One"},
            {"faculty_id": "F2", "faculty_name": "Faculty Two"}
        ]
    })
    
    # 3. 1st year subject faculty map
    store.save_scoped_mapping("subject_faculty_map", "year:1st Year:batch:ALL", {
        "rows": [
            {"year": "1st Year", "section": "A", "subject": "Math", "faculty_id": "F1"},
            {"year": "1st Year", "section": "B", "subject": "Math", "faculty_id": "F1"},
            {"year": "1st Year", "section": "A", "subject": "Science", "faculty_id": "F2"}
        ]
    })
    
    # 4. 2nd year subject faculty map
    store.save_scoped_mapping("subject_faculty_map", "year:2nd Year:batch:ALL", {
        "rows": [
            {"year": "2nd Year", "section": "A", "subject": "Physics", "faculty_id": "F2"},
            {"year": "2nd Year", "section": "B", "subject": "Physics", "faculty_id": "F2"}
        ]
    })
    
    # 5. subject periods map 1st year
    store.save_scoped_mapping("subject_periods_map", "year:1st Year:batch:ALL", {
        "rows": [
            {"subject": "Math", "hours": 4, "continuous_hours": 1},
            {"subject": "Science", "hours": 4, "continuous_hours": 1}
        ]
    })
    
    # 6. subject periods map 2nd year
    store.save_scoped_mapping("subject_periods_map", "year:2nd Year:batch:ALL", {
        "rows": [
            {"subject": "Physics", "hours": 4, "continuous_hours": 1}
        ]
    })

    request_data = GenerateTimetableRequest(
        year="1st Year",
        section="A",
        subjects=[],
        labs=[],
        batchSubjectHours={},
        sectionBatchMap={},
        facultyAvailability=[],
        subjectHours=[],
        sharedClasses=[],
    )
    
    try:
        res = generate_timetable(request_data, store)
        print("1st Year Response:", res)
    except Exception as e:
        print("1st Year Error:", type(e), e)

    request_data_2 = GenerateTimetableRequest(
        year="2nd Year",
        section="A",
        subjects=[],
        labs=[],
        batchSubjectHours={},
        sectionBatchMap={},
        facultyAvailability=[],
        subjectHours=[],
        sharedClasses=[],
    )
    
    try:
        res2 = generate_timetable(request_data_2, store)
        print("2nd Year Response:", res2)
    except Exception as e:
        print("2nd Year Error:", type(e), e)
    
if __name__ == "__main__":
    test()

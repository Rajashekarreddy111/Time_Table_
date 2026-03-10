import requests
import time

payload = {
    "year": "1st Year",
    "section": "A",
    "sectionBatchMap": {},
    "subjects": [
        {"subject": "Math", "faculty": "F001"},
    ],
    "labs": [],
    "sharedClasses": [
        {"year": "1st Year", "sections": ["A", "B"], "subject": "Math"}
    ],
    "subjectHours": [
        {"subject": "Math", "hours": 20, "continuousHours": 1},
    ],
    "facultyAvailability": [
        {
            "facultyId": "F001",
            "availablePeriodsByDay": {
                "Monday": [1, 2, 3, 4, 5, 6, 7],
                "Tuesday": [1, 2, 3, 4, 5, 6, 7],
                "Wednesday": [],
                "Thursday": [],
                "Friday": [],
                "Saturday": []
            }
        }
    ],
    "batchSubjectHours": {}
}

start = time.time()
print("Starting timeout test...")
res = requests.post("http://localhost:5000/api/timetables/generate", json=payload)
print(f"Status: {res.status_code}, Time: {time.time() - start:.2f}s")
print(res.text)

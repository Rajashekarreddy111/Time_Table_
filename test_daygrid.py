from backend.routers.uploads import _normalize_faculty_availability_rows

mock_rows = [
    {
        "Faculty ID": "F001",
        "Monday": "1, 2, 3",
        "Tuesday": "4, 5",
        "Wednesday": "",
        "Thursday": "",
        "Friday": "1, 2",
        "Saturday": ""
    },
    {
        "Faculty ID": "F002",
        "Monday": "",
        "Tuesday": "1, 2, 3, 4",
        "Wednesday": "5, 6, 7",
        "Thursday": "",
        "Friday": "",
        "Saturday": "1"
    }
]

print("Testing mock grid format:")
out = _normalize_faculty_availability_rows(mock_rows)
print(out)

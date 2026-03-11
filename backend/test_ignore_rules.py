import requests
import io
import pandas as pd
import json

base = "http://127.0.0.1:5000/api"

df_workload = pd.DataFrame([
    {"id assigned": "F001", "faculty name": "Faculty 1", "day": "Monday", "period": 1, "year": "2nd Year", "section": "A", "subject": "CS101"},
    {"id assigned": "F002", "faculty name": "Faculty 2", "day": "Monday", "period": 1, "year": "3rd Year", "section": "B", "subject": "CS102"}
])
workload_buf = io.BytesIO()
df_workload.to_excel(workload_buf, index=False)
workload_buf.seek(0)
res = requests.post(f"{base}/uploads/faculty-availability", files={"file": ("workload.xlsx", workload_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
workload_id = res.json()["fileId"]

df_query = pd.DataFrame([
    {"Date": "2024-03-25", "Number of Faculty Required": 2, "Periods": "1"}
])
query_buf = io.BytesIO()
df_query.to_excel(query_buf, index=False)
query_buf.seek(0)
res_query = requests.post(f"{base}/uploads/faculty-availability-query", files={"file": ("query.xlsx", query_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
query_id = res_query.json()["fileId"]

def test_bulk(ignored_years, ignored_sections):
    res = requests.post(f"{base}/faculty/availability/bulk", json={
        "availabilityFileId": workload_id,
        "queryFileId": query_id,
        "ignoredYears": ignored_years,
        "ignoredSections": ignored_sections
    })
    return res.json()["results"][0]["faculty"]

output = {
    "test1_none": test_bulk([], []),
    "test2_ignore_year2": test_bulk(["2nd Year"], []),
    "test3_ignore_sec3b": test_bulk([], ["3rd Year|B"]),
    "test4_ignore_both": test_bulk(["2nd Year"], ["3rd Year|B"])
}

with open("test_results.json", "w") as f:
    json.dump(output, f, indent=2)
print("Wrote to test_results.json")

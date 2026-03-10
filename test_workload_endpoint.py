import sys
import os
import pandas as pd

sys.stdout = open("out_py.txt", "w", encoding="utf-8")
sys.stderr = sys.stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from backend.routers.uploads import _normalize_faculty_availability_rows
from backend.services.file_parser import dataframe_rows

def test_parse():
    data = [
        ["COLLEGES NAME", "", "", "", "", "", "", "", "", ""],
        ["(AUTONOMOUS)", "", "", "", "", "", "", "", "", ""],
        ["DEPT", "", "", "", "", "", "", "", "", ""],
        ["ACADEMIC YEAR : 2024-2025 Even", "", "", "", "", "", "", "", "", ""],
        ["FACULTY WORKLOAD : Dr. Smith", "", "", "", "", "", "", "", "", ""],
        ["Room No :", "", "", "", "", "With effect from : 18-03-2024", "", "", "", ""],
        ["DAY", "1", "2", "", "3", "4", "", "5", "6", "7"],
        ["", "9.10-10.00", "10.00-10.50", "10.50-11.00", "11.00-11.50", "11.50-12.40", "12.40-1.30", "1.30-2.20", "2.20-3.10", "3.10-4.00"],
        ["MON", "1A-MATH", "1B-PHY", "BREAK", "", "", "LUNCH", "", "", ""],
        ["TUE", "", "", "", "2A-CHEM", "", "", "", "", ""],
    ]
    cols = ["COLLEGES NAME"] + [f"Unnamed: {i}" for i in range(1, 10)]
    df = pd.DataFrame(data[1:], columns=cols) 
    rows = dataframe_rows(df)
    print("Row 2:", rows[2])
    print("Row 3:", rows[3])
    try:
        res = _normalize_faculty_availability_rows(rows)
        print("Success! Found available periods:")
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parse()

import pandas as pd

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
    df = pd.DataFrame(data[1:], columns=data[0]) 
    
    # Simulate dataframe_rows
    column_map = {str(col).strip().lower(): str(col).strip() for col in df.columns}
    records = []
    for _, row in df.iterrows():
        record = {}
        for lower_col, orig_col in column_map.items():
            record[lower_col] = row[orig_col]
            record[f"__orig_{lower_col}"] = orig_col
        records.append(record)
        
    print("Columns:", list(df.columns))
    
    
    # Detection
    is_workload = False
    faculty_name = "Unknown"
    
    # Since headers might contain the college name, search ALL items in records
    for row in records[:15]:
        for k, v in row.items():
            k_upper = str(k).upper()
            v_upper = str(v).upper() if pd.notnull(v) else ""
            orig_k = str(row.get(f"__orig_{k}", k)).upper()
            if "FACULTY WORKLOAD :" in orig_k:
                is_workload = True
                faculty_name = row[f"__orig_{k}"].split(":", 1)[1].strip()
                break
            if "FACULTY WORKLOAD :" in v_upper:
                is_workload = True
                faculty_name = str(v).split(":", 1)[1].strip()
                break
        if is_workload:
            break
            
    print("Is Workload?", is_workload)
    print("Faculty:", faculty_name)
    
    # Extract availability
    if is_workload:
        # Find which keys correspond to 'DAY', '1', '2' etc.
        # since it's a matrix structure, "DAY" will be in the first column typically
        # To be robust, let's find the dictionary row that has 'DAY' and '1', '2' etc.
        periods_row = None
        for i, row in enumerate(records):
            vals = [str(x).upper().strip() for k, x in row.items() if not str(k).startswith('__orig_') and pd.notnull(x)]
            if "DAY" in vals and "1" in vals and "2" in vals:
                periods_row = row
                break
                
        if periods_row:
            # map column key to period number
            # The column key is `k`.
            col_to_period = {}
            day_col_key = None
            for k, v in periods_row.items():
                if str(k).startswith('__orig_') or pd.isnull(v):
                    continue
                v_str = str(v).upper().strip()
                if v_str == "DAY":
                    day_col_key = k
                elif v_str in ["1", "2", "3", "4", "5", "6", "7"]:
                    col_to_period[k] = int(v_str)
                    
            print(f"Day col key: {day_col_key}, col_to_period: {col_to_period}")
            
            # Now finding availability
            DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
            available_slots = []
            
            # Start from periods_row index + 2 (skip the timings row)
            # Actually, just search all rows for DAY keys
            for row in records:
                day_val = str(row.get(day_col_key, "")).upper().strip()
                if not pd.isnull(day_val) and day_val in DAYS:
                    # check col_to_period cells
                    for col_key, p_num in col_to_period.items():
                        cell_val = row.get(col_key)
                        # An empty or null cell means AVAILABLE
                        # Actually wait, are there entries with BREAK or LUNCH?
                        # No, BREAK/LUNCH are in unmapped columns (e.g. they don't have header "1", "2")
                        # Because col_to_period only contains keys mapped from "1", "2", "3"...
                        
                        is_empty = pd.isnull(cell_val) or str(cell_val).strip() == ""
                        if is_empty:
                            available_slots.append({
                                "faculty_id": faculty_name, # or ID if available, the file only has name
                                "faculty_name": faculty_name,
                                "day": day_val,
                                "period": p_num,
                                "year": "ALL",
                                "section": "ALL",
                                "subject": ""
                            })
            
            print("Found available slots:", len(available_slots))
            for slot in available_slots:
                print(slot)

if __name__ == "__main__":
    test_parse()

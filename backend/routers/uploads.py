from io import BytesIO
from pathlib import Path

import openpyxl
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from models.schemas import UploadResponse
from services.cloudinary_storage import upload_source_file
from services.file_parser import dataframe_rows, parse_tabular_upload, read_upload_bytes
from services.utils import normalize_year
from storage.memory_store import store

router = APIRouter(tags=["uploads"])


def _validation_error(message: str, details: list | None = None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "ValidationError", "message": message, "details": details or []},
    )


def _to_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_workload_day(value) -> str:
    text = _to_text(value).upper()
    compact = "".join(ch for ch in text if ch.isalpha())
    day_map = {
        "MON": "MON",
        "MONDAY": "MON",
        "TUE": "TUE",
        "TUESDAY": "TUE",
        "WED": "WED",
        "WEDNESDAY": "WED",
        "THU": "THU",
        "THURSDAY": "THU",
        "FRI": "FRI",
        "FRIDAY": "FRI",
        "SAT": "SAT",
        "SATURDAY": "SAT",
    }
    return day_map.get(compact, "")




def _normalize_faculty_id_rows(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        faculty_name = (
            _to_text(row.get("faculty_name"))
            or _to_text(row.get("faculty name"))
            or _to_text(row.get("name"))
        )
        faculty_id = (
            _to_text(row.get("faculty_id"))
            or _to_text(row.get("id assigned"))
            or _to_text(row.get("id"))
        )
        if faculty_name and faculty_id:
            normalized.append({"faculty_id": faculty_id, "faculty_name": faculty_name})
    if not normalized:
        raise _validation_error(
            "Required columns are missing",
            [{
                "expectedAnyOf": [["faculty_id", "faculty_name"], ["faculty name", "id assigned"]],
                "receivedColumns": list(rows[0].keys()) if rows else [],
            }],
        )
    return normalized


def _normalize_main_timetable_config(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        year = normalize_year(_to_text(row.get("year")))
        subject_id = _to_text(row.get("subject_id")) or _to_text(row.get("subject id"))
        if not year or not subject_id:
            continue
        
        sections_found = set()
        for k in row.keys():
            k_str = str(k).lower()
            if k_str.endswith("_hours") and not k_str.startswith("__orig_") and "continuous" not in k_str:
                sec = k_str.replace("_hours", "").upper()
                sections_found.add(sec)
                
        for sec in sections_found:
            hours = _to_text(row.get(f"{sec.lower()}_hours"))
            faculty = _to_text(row.get(f"{sec.lower()}_faculty_id")) or _to_text(row.get(f"{sec.lower()}_faculty-id"))
            continuous = _to_text(row.get(f"{sec.lower()}_continuous_hours")) 
            
            if hours and str(hours).strip() != '0':
                try:
                    h_val = int(float(hours))
                    c_val = int(float(continuous)) if continuous else 1
                    normalized.append({
                        "year": year,
                        "subject_id": subject_id,
                        "section": sec,
                        "hours": h_val,
                        "faculty_id": faculty,
                        "continuous_hours": c_val
                    })
                except ValueError:
                    pass
    if not normalized:
        raise _validation_error("Required columns missing or no data found in main timetable config", [])
    return normalized


def _validate_main_timetable_section_totals(rows: list[dict]) -> None:
    totals: dict[tuple[str, str], int] = {}
    for row in rows:
        year = normalize_year(_to_text(row.get("year")))
        section = _to_text(row.get("section")).upper()
        hours = row.get("hours", 0)
        if not year or not section:
            continue
        totals[(year, section)] = totals.get((year, section), 0) + int(hours or 0)

    violations = []
    for (year, section), total in sorted(totals.items()):
        if total != 42:
            violations.append(
                {
                    "year": year,
                    "section": section,
                    "hours": total,
                    "expected": 42,
                    "detail": f"Year {year} Section {section} -> {total} hours (Expected: 42)",
                }
            )

    if violations:
        raise _validation_error("Validation Error: Main config section totals must equal 42.", violations)


def _normalize_lab_timetable(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        year = normalize_year(_to_text(row.get("year")))
        section = _to_text(row.get("section"))
        subject_id = _to_text(row.get("subject_id")) or _to_text(row.get("subject id"))
        day = _to_text(row.get("day"))
        hours = _to_text(row.get("hours"))
        venue = _to_text(row.get("venue"))
        
        if not year or not section or not subject_id or not day or not hours:
            continue
            
        try:
            day_val = int(float(day))
            hours_list = [int(float(h.strip())) for h in hours.split(",") if h.strip()]
            normalized.append({
                "year": year,
                "section": section,
                "subject_id": subject_id,
                "day": day_val,
                "hours": hours_list,
                "venue": venue
            })
        except ValueError:
            pass
    return normalized


def _normalize_subject_id_mapping(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        sub_id = (
            _to_text(row.get("subject_id"))
            or _to_text(row.get("subject id"))
            or _to_text(row.get("id"))
        )
        name = _to_text(row.get("subject_name")) or _to_text(row.get("subject name")) or _to_text(row.get("subject"))
        if sub_id and name:
            normalized.append({"subject_id": sub_id, "subject_name": name})
    if not normalized:
        raise _validation_error(
            "Required columns are missing",
            [{"expectedAnyOf": [["subject_id", "subject_name"], ["id", "subject name"]]}],
        )
    return normalized


def _normalize_continuous_rules(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        sub_id = _to_text(row.get("subject_id")) or _to_text(row.get("subject id"))
        compulsory = _to_text(row.get("compulsory_continuous_hours")) or _to_text(row.get("continuous"))
        if sub_id and compulsory:
            try:
                c_val = int(float(compulsory))
                normalized.append({"subject_id": sub_id, "compulsory_continuous_hours": c_val})
            except ValueError:
                pass
    return normalized

def _normalize_shared_class_rows(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        year = normalize_year(_to_text(row.get("year")))
        sections_raw = _to_text(row.get("sections"))
        subject = _to_text(row.get("subject")) or _to_text(row.get("subject_id"))
        
        if not year or not sections_raw or not subject:
            continue

        # Accept both "1,2,3" and "1, 2, 3" formats.
        sections = [s.strip() for s in sections_raw.split(",") if s.strip()]
        if not sections:
            continue

        # If a single numeric value is provided (e.g. "3"), interpret it as
        # "total number of sections for this year" instead of explicit names.
        if len(sections) == 1 and sections[0].isdigit():
            normalized.append(
                {
                    "year": year,
                    "sections": [],
                    "sections_count": int(sections[0]),
                    "subject": subject,
                }
            )
            continue

        normalized.append(
            {
                "year": year,
                "sections": sections,
                "subject": subject,
            }
        )
        
    if not normalized:
        raise _validation_error(
            "Required columns are missing in shared classes file",
            [{"expected": ["year", "sections", "subject"]}],
        )
    return normalized


def _normalize_faculty_availability_rows(rows: list[dict]) -> list[dict]:
    # --- Detect Faculty Workload Export Format ---
    is_workload = False
    faculty_name = ""
    
    for row in rows[:15]:
        for k, v in row.items():
            if str(k).startswith("__orig_"):
                continue
            k_upper = str(row.get(f"__orig_{k}", k)).upper()
            v_upper = str(v).upper() if v is not None else ""
            if "FACULTY WORKLOAD :" in k_upper:
                is_workload = True
                faculty_name = row.get(f"__orig_{k}", str(k)).split(":", 1)[1].strip()
                break
            if "FACULTY WORKLOAD :" in v_upper:
                is_workload = True
                faculty_name = str(v).split(":", 1)[1].strip()
                break
        if is_workload:
            break

    if is_workload:
        import math
        
        normalized_workload: list[dict] = []
        # Find which keys correspond to 'DAY', '1', '2' etc.
        periods_row = None
        for row in rows:
            vals = [str(x).upper().strip() for k, x in row.items() if not str(k).startswith('__orig_') and x is not None and not (isinstance(x, float) and math.isnan(x))]
            if "DAY" in vals and "1" in vals and "2" in vals:
                periods_row = row
                break
                
        if periods_row:
            col_to_period = {}
            day_col_key = None
            for k, v in periods_row.items():
                if str(k).startswith('__orig_') or v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                v_str = str(v).upper().strip()
                if v_str == "DAY":
                    day_col_key = k
                elif v_str in ["1", "2", "3", "4", "5", "6", "7"]:
                    col_to_period[k] = int(v_str)
                    
            VALID_DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT"}
            
            for row in rows:
                if day_col_key not in row:
                    continue
                day_val_raw = row[day_col_key]
                if day_val_raw is None or (isinstance(day_val_raw, float) and math.isnan(day_val_raw)):
                    continue
                day_val = _normalize_workload_day(day_val_raw)
                
                if day_val in VALID_DAYS:
                    for col_key, p_num in col_to_period.items():
                        cell_val = row.get(col_key)
                        is_empty = cell_val is None or (isinstance(cell_val, float) and math.isnan(cell_val)) or str(cell_val).strip() == ""
                        if is_empty:
                            normalized_workload.append({
                                "faculty_id": faculty_name,
                                "faculty_name": faculty_name,
                                "day": day_val,
                                "period": p_num,
                                "year": "",
                                "section": "",
                                "subject": "",
                                "is_available": True,
                            })
                            
            if normalized_workload:
                return normalized_workload
            else:
                raise _validation_error(
                    "Faculty workload format detected, but no available periods found (or faculty is fully occupied)",
                    []
                )

    # --- End Detect Faculty Workload Export Format ---

    # --- Detect New Day-Grid Template (Manual Entry format) ---
    is_day_grid = False
    if rows:
        first_row_keys = [str(k).upper() for k in rows[0].keys() if not str(k).startswith("__orig_")]
        if "MONDAY" in first_row_keys and "TUESDAY" in first_row_keys:
            is_day_grid = True

    if is_day_grid:
        normalized_grid: list[dict] = []
        VALID_DAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"}
        for row in rows:
            faculty_id = ""
            for k, v in row.items():
                if str(k).startswith("__orig_"):
                    continue
                k_upper = str(k).upper().strip()
                if k_upper in ["FACULTY ID", "ID ASSIGNED", "FACULTY NAME", "NAME", "FACULTY", "ID"]:
                    faculty_id = _to_text(v)
                    break
            
            if not faculty_id:
                continue

            for k, v in row.items():
                if str(k).startswith("__orig_"):
                    continue
                k_upper = str(k).upper().strip()
                if k_upper in VALID_DAYS:
                    periods_raw = _to_text(v)
                    if not periods_raw:
                        continue
                    
                    parts = [p.strip() for p in periods_raw.split(",")]
                    for p in parts:
                        if not p:
                            continue
                        try:
                            period_num = int(float(p))
                            normalized_grid.append({
                                "faculty_id": faculty_id,
                                "faculty_name": faculty_id,
                                "day": k_upper[:3],
                                "period": period_num,
                                "year": "",
                                "section": "",
                                "subject": "",
                                "is_available": True,
                            })
                        except ValueError:
                            pass
        
        if not normalized_grid:
            raise _validation_error(
                "Day-grid format detected but no valid periods were found",
                []
            )
        return normalized_grid
    # --- End Detect Day-Grid Template ---

    normalized: list[dict] = []
    for row in rows:
        faculty_id = _to_text(row.get("faculty_id")) or _to_text(row.get("id assigned"))
        faculty_name = _to_text(row.get("faculty_name")) or _to_text(row.get("faculty name"))
        day = _to_text(row.get("day"))
        period_raw = _to_text(row.get("period"))
        year = normalize_year(_to_text(row.get("year")))
        section = _to_text(row.get("section"))
        subject = _to_text(row.get("subject"))

        if not day or not period_raw:
            continue
        try:
            period = int(float(period_raw))
        except ValueError:
            raise _validation_error(
                "Invalid period value in faculty availability file",
                [{"day": day, "period": period_raw}],
            )
        normalized.append(
            {
                "faculty_id": faculty_id,
                "faculty_name": faculty_name,
                "day": day,
                "period": period,
                "year": year,
                "section": section,
                "subject": subject,
            }
        )
    if not normalized:
        raise _validation_error(
            "Required columns are missing",
            [{
                "expectedColumns": ["faculty_id/faculty name", "day", "period", "year", "section", "subject"],
                "receivedColumns": list(rows[0].keys()) if rows else [],
            }],
        )
    return normalized


def _parse_workload_sheet_rows(file_bytes: bytes) -> list[dict]:
    workbook = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    normalized_rows: list[dict] = []
    valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT"}

    for worksheet in workbook.worksheets:
        sheet_rows = list(worksheet.iter_rows(values_only=True))
        if not sheet_rows:
            continue

        faculty_name = ""
        for row in sheet_rows[:12]:
            for value in row:
                text = _to_text(value)
                if "FACULTY WORKLOAD" in text.upper():
                    faculty_name = text.split(":", 1)[1].strip() if ":" in text else text
                    break
            if faculty_name:
                break

        periods_row_index = -1
        day_column_index = -1
        column_to_period: dict[int, int] = {}
        for row_index, row in enumerate(sheet_rows):
            values = [_to_text(value).upper() for value in row]
            if "DAY" not in values or "1" not in values or "2" not in values:
                continue
            periods_row_index = row_index
            for column_index, value in enumerate(values):
                if value == "DAY":
                    day_column_index = column_index
                elif value in {"1", "2", "3", "4", "5", "6", "7"}:
                    column_to_period[column_index] = int(value)
            break

        if periods_row_index == -1 or day_column_index == -1 or not column_to_period:
            continue

        for row in sheet_rows[periods_row_index + 1:]:
            if day_column_index >= len(row):
                continue

            day_value = _normalize_workload_day(row[day_column_index])
            if day_value not in valid_days:
                continue

            for column_index, period in column_to_period.items():
                cell_value = row[column_index] if column_index < len(row) else None
                if _to_text(cell_value):
                    continue
                normalized_rows.append(
                    {
                        "faculty_id": faculty_name or worksheet.title.strip(),
                        "faculty_name": faculty_name or worksheet.title.strip(),
                        "day": day_value,
                        "period": period,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    }
                )

    return normalized_rows


def _normalize_faculty_availability_query_rows(rows: list[dict]) -> list[dict]:
    import re
    normalized: list[dict] = []
    for row in rows:
        date_raw = _to_text(row.get("date"))
        required_raw = _to_text(row.get("number of faculty required")) or _to_text(row.get("faculty required"))
        periods_raw = _to_text(row.get("periods")) or _to_text(row.get("select period(s)")) or _to_text(row.get("period"))
        
        if not date_raw:
            continue
            
        try:
            required = int(float(required_raw)) if required_raw else 1
        except ValueError:
            required = 1
            
        periods = []
        if periods_raw:
            for p in re.split(r"[\s,]+", periods_raw.strip()):
                if not p:
                    continue
                match = re.search(r"\d+", p)
                if match:
                    periods.append(int(match.group()))
                    
        normalized.append({
            "date": date_raw,
            "facultyRequired": required,
            "periods": periods
        })
        
    if not normalized:
        raise _validation_error(
            "Required columns are missing or file is empty",
            [{"expectedColumns": ["Date", "Number of Faculty Required", "Periods/Select Period(s)"],
              "receivedColumns": list(rows[0].keys()) if rows else []}],
        )
    return normalized


def _scope_key_global() -> str:
    return "global"


def _scope_key_year(year: str) -> str:
    return f"year:{year.strip()}"


def _normalize_batch_type(value: str | None) -> str:
    text = (value or "").strip().upper()
    if text in {"CREAM", "GENERAL", "ALL"}:
        return text
    return "ALL"


def _scope_key_year_batch(year: str, batch_type: str) -> str:
    return f"{_scope_key_year(year)}:batch:{_normalize_batch_type(batch_type)}"


def _conflict_error(message: str, details: list | None = None) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"error": "ConflictError", "message": message, "details": details or []},
    )


@router.post("/uploads/faculty-id-map", response_model=UploadResponse)
async def upload_faculty_id_map(file: UploadFile = File(...)):
    if not file.filename:
        raise _validation_error("File name is required", [])
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise _validation_error("Only spreadsheet files (.xlsx, .xls, .csv) are allowed for this upload", [])

    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_faculty_id_rows(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/faculty-id-map")
    scope_key = _scope_key_global()
    file_id = store.next_file_id("fmap")
    payload = {
        "id": file_id,
        "fileName": file.filename,
        "rowsParsed": len(rows),
        "rows": rows,
        "sourceFile": cloudinary_file,
    }
    store.save_file_map(file_id, payload)
    store.save_scoped_mapping("faculty_id_map", scope_key, payload, allow_overwrite=True)
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(rows),
        message="Faculty ID map uploaded successfully for all years/sections",
    )


@router.post("/uploads/main-timetable-config", response_model=UploadResponse)
async def upload_main_timetable_config(
    file: UploadFile = File(...)
):
    if not file.filename:
        raise _validation_error("File name is required", [])
    
    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_main_timetable_config(dataframe_rows(dataframe))
    _validate_main_timetable_section_totals(rows)
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/main-timetable")
    
    scope_key = _scope_key_global()
    file_id = store.next_file_id("maincfg")
    payload = {
        "id": file_id,
        "fileName": file.filename,
        "rowsParsed": len(rows),
        "rows": rows,
        "sourceFile": cloudinary_file,
    }
    store.save_file_map(file_id, payload)
    store.save_scoped_mapping("main_timetable_config", scope_key, payload, allow_overwrite=True)
    
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(rows),
        message="Main timetable config uploaded successfully",
    )

@router.post("/uploads/lab-timetable", response_model=UploadResponse)
async def upload_lab_timetable(
    file: UploadFile = File(...)
):
    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_lab_timetable(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/lab-timetable")
    
    scope_key = _scope_key_global()
    file_id = store.next_file_id("labcfg")
    payload = {"id": file_id, "fileName": file.filename, "rowsParsed": len(rows), "rows": rows, "sourceFile": cloudinary_file}
    store.save_file_map(file_id, payload)
    store.save_scoped_mapping("lab_timetable_config", scope_key, payload, allow_overwrite=True)
    return UploadResponse(fileId=file_id, fileName=file.filename, rowsParsed=len(rows), message="Lab timetable uploaded")

@router.post("/uploads/subject-id-mapping", response_model=UploadResponse)
async def upload_subject_id_mapping(file: UploadFile = File(...)):
    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_subject_id_mapping(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/subject-id-mapping")
    
    file_id = store.next_file_id("subid")
    payload = {"id": file_id, "fileName": file.filename, "rowsParsed": len(rows), "rows": rows, "sourceFile": cloudinary_file}
    store.save_file_map(file_id, payload)
    store.save_scoped_mapping("subject_id_mapping", "global", payload, allow_overwrite=True)
    return UploadResponse(fileId=file_id, fileName=file.filename, rowsParsed=len(rows), message="Subject ID Map uploaded")

@router.post("/uploads/subject-continuous-rules", response_model=UploadResponse)
async def upload_subject_continuous_rules(file: UploadFile = File(...)):
    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_continuous_rules(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/continuous-rules")
    
    file_id = store.next_file_id("subcnt")
    payload = {"id": file_id, "fileName": file.filename, "rowsParsed": len(rows), "rows": rows, "sourceFile": cloudinary_file}
    store.save_file_map(file_id, payload)
    store.save_scoped_mapping("subject_continuous_rules", "global", payload, allow_overwrite=True)
    return UploadResponse(fileId=file_id, fileName=file.filename, rowsParsed=len(rows), message="Continuous Rules uploaded")

@router.post("/uploads/faculty-availability", response_model=UploadResponse)
async def upload_faculty_availability(file: UploadFile = File(...)):
    if not file.filename:
        raise _validation_error("File name is required", [])
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise _validation_error("Only spreadsheet files (.xlsx, .xls, .csv) are allowed for this upload", [])

    file_bytes = read_upload_bytes(file)
    rows: list[dict] = []
    if suffix == ".xlsx":
        rows = _parse_workload_sheet_rows(file_bytes)
    if not rows:
        dataframe = parse_tabular_upload(file.filename, file_bytes)
        rows = _normalize_faculty_availability_rows(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/faculty-availability")

    # Merge with existing rows and deduplicate
    existing = store.get_scoped_mapping("faculty_availability", "global")
    if existing:
        existing_rows = existing.get("rows", [])
        
        # Simple deduplication based on (faculty_id, day, period, year, section, subject)
        seen_keys = set()
        for r in existing_rows:
            key = (r.get("faculty_id"), r.get("day"), r.get("period"), r.get("year"), r.get("section"), r.get("subject"))
            seen_keys.add(key)
            
        merged_rows = list(existing_rows)
        for r in rows:
            key = (r.get("faculty_id"), r.get("day"), r.get("period"), r.get("year"), r.get("section"), r.get("subject"))
            if key not in seen_keys:
                merged_rows.append(r)
                seen_keys.add(key)
    else:
        merged_rows = rows

    # Save merged to scoped
    payload = {
        "rows": merged_rows,
        "lastFileName": file.filename,
        "lastSourceFile": cloudinary_file,
    }
    store.save_scoped_mapping("faculty_availability", "global", payload, allow_overwrite=True)

    # Save to file_map for service compatibility
    file_id = store.next_file_id("favail")
    store.save_file_map(
        file_id,
        {
            "id": file_id,
            "fileName": file.filename,
            "rowsParsed": len(merged_rows),
            "rows": merged_rows,
            "sourceFile": cloudinary_file,
        },
    )
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(merged_rows),
        message="Faculty availability file uploaded successfully",
    )


@router.post("/uploads/faculty-availability-query", response_model=UploadResponse)
async def upload_faculty_availability_query(file: UploadFile = File(...)):
    if not file.filename:
        raise _validation_error("File name is required", [])
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise _validation_error("Only spreadsheet files (.xlsx, .xls, .csv) are allowed for this upload", [])

    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_faculty_availability_query_rows(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/faculty-availability-query")

    file_id = store.next_file_id("fquery")
    store.save_file_map(
        file_id,
        {
            "id": file_id,
            "fileName": file.filename,
            "rowsParsed": len(rows),
            "rows": rows,
            "sourceFile": cloudinary_file,
        },
    )
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(rows),
        message="Faculty availability query uploaded successfully",
    )


@router.get("/uploads/mapping-status")
async def get_mapping_status(
    year: str = Query(...),
    section: str = Query(default=""),
):
    normalized_year = normalize_year(year.strip())
    if not normalized_year:
        raise _validation_error("Year is required", [])

    faculty_map = store.get_scoped_mapping("faculty_id_map", _scope_key_global())
    main_cfg = store.get_scoped_mapping("main_timetable_config", _scope_key_global())
    lab_cfg = store.get_scoped_mapping("lab_timetable_config", _scope_key_global())
    sub_id_map = store.get_scoped_mapping("subject_id_mapping", "global")
    sub_cnt = store.get_scoped_mapping("subject_continuous_rules", "global")
    faculty_availability = store.get_scoped_mapping("faculty_availability", "global")
    shared_classes = store.get_scoped_mapping("shared_classes", "global")
    
    return {
        "facultyIdMapUploaded": bool(faculty_map),
        "mainTimetableConfigUploaded": bool(main_cfg),
        "labTimetableConfigUploaded": bool(lab_cfg),
        "subjectIdMappingUploaded": bool(sub_id_map),
        "subjectContinuousRulesUploaded": bool(sub_cnt),
        
        "facultyAvailabilityUploaded": bool(faculty_availability),
        "sharedClassesUploaded": bool(shared_classes),
        
        "facultyIdMapFileName": faculty_map.get("fileName") if faculty_map else None,
        "mainTimetableConfigFileName": main_cfg.get("fileName") if main_cfg else None,
        "labTimetableConfigFileName": lab_cfg.get("fileName") if lab_cfg else None,
        "subjectIdMappingFileName": sub_id_map.get("fileName") if sub_id_map else None,
        "subjectContinuousRulesFileName": sub_cnt.get("fileName") if sub_cnt else None,
        "sharedClassesFileName": shared_classes.get("fileName") if shared_classes else None,
        "facultyAvailabilityFileName": faculty_availability.get("lastFileName") if faculty_availability else None,
    }

@router.post("/uploads/shared-classes", response_model=UploadResponse)
async def upload_shared_classes(file: UploadFile = File(...)):
    if not file.filename:
        raise _validation_error("File name is required", [])
        
    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_shared_class_rows(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/shared-classes")
    
    # Save to scoped
    payload = {
        "rows": rows,
        "fileName": file.filename,
        "sourceFile": cloudinary_file,
    }
    store.save_scoped_mapping("shared_classes", "global", payload, allow_overwrite=True)
    
    file_id = store.next_file_id("shmap")
    store.save_file_map(file_id, {**payload, "id": file_id, "rowsParsed": len(rows)})
    
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(rows),
        message="Shared classes constraint file uploaded successfully",
    )


@router.get("/uploads/faculty-id-status")
async def get_faculty_id_status():
    faculty_map = store.get_scoped_mapping("faculty_id_map", _scope_key_global())
    return {
        "facultyIdMapUploaded": bool(faculty_map),
        "facultyIdMapFileName": faculty_map.get("fileName") if faculty_map else None,
    }

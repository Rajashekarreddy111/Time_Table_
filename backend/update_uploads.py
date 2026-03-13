import re
import os

uploads_path = r"c:\Users\rajas\OneDrive\Desktop\Timetable\backend\routers\uploads.py"
with open(uploads_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace normalization functions
norm_start = content.find("def _normalize_subject_period_rows")
norm_end = content.find("def _normalize_shared_class_rows")

new_norms = """def _normalize_main_timetable_config(rows: list[dict]) -> list[dict]:
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
        sub_id = _to_text(row.get("subject_id")) or _to_text(row.get("subject id"))
        name = _to_text(row.get("subject_name")) or _to_text(row.get("subject name")) or _to_text(row.get("subject"))
        if sub_id and name:
            normalized.append({"subject_id": sub_id, "subject_name": name})
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

"""

content = content[:norm_start] + new_norms + content[norm_end:]

# Replace old endpoints
ep_start = content.find('@router.post("/uploads/subject-faculty-map"')
ep_end = content.find('@router.post("/uploads/faculty-availability"')

new_eps = """@router.post("/uploads/main-timetable-config", response_model=UploadResponse)
async def upload_main_timetable_config(
    year: str = Form(...),
    file: UploadFile = File(...)
):
    if not file.filename:
        raise _validation_error("File name is required", [])
    year = normalize_year(year.strip())
    if not year:
        raise _validation_error("Year is required", [])
    
    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_main_timetable_config(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/main-timetable")
    
    scope_key = _scope_key_year(year)
    file_id = store.next_file_id("maincfg")
    payload = {
        "id": file_id,
        "fileName": file.filename,
        "rowsParsed": len(rows),
        "rows": rows,
        "year": year,
        "sourceFile": cloudinary_file,
    }
    store.save_file_map(file_id, payload)
    store.save_scoped_mapping("main_timetable_config", scope_key, payload, allow_overwrite=True)
    
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(rows),
        message=f"Main timetable config uploaded successfully for {year}",
    )

@router.post("/uploads/lab-timetable", response_model=UploadResponse)
async def upload_lab_timetable(
    year: str = Form(...),
    file: UploadFile = File(...)
):
    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_lab_timetable(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/lab-timetable")
    
    scope_key = _scope_key_year(normalize_year(year))
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

"""

content = content[:ep_start] + new_eps + content[ep_end:]


# Replace get_mapping_status
stat_start = content.find('@router.get("/uploads/mapping-status")')
stat_end = content.find('@router.post("/uploads/shared-classes"')

new_stat = """@router.get("/uploads/mapping-status")
async def get_mapping_status(
    year: str = Query(...),
    section: str = Query(default=""),
):
    normalized_year = normalize_year(year.strip())
    if not normalized_year:
        raise _validation_error("Year is required", [])

    faculty_map = store.get_scoped_mapping("faculty_id_map", _scope_key_global())
    main_cfg = store.get_scoped_mapping("main_timetable_config", _scope_key_year(normalized_year))
    lab_cfg = store.get_scoped_mapping("lab_timetable_config", _scope_key_year(normalized_year))
    sub_id_map = store.get_scoped_mapping("subject_id_mapping", "global")
    sub_cnt = store.get_scoped_mapping("subject_continuous_rules", "global")
    
    return {
        "facultyIdMapUploaded": bool(faculty_map),
        "mainTimetableConfigUploaded": bool(main_cfg),
        "labTimetableConfigUploaded": bool(lab_cfg),
        "subjectIdMappingUploaded": bool(sub_id_map),
        "subjectContinuousRulesUploaded": bool(sub_cnt),
        
        "facultyAvailabilityUploaded": bool(store.get_scoped_mapping("faculty_availability", "global")),
        "sharedClassesUploaded": bool(store.get_scoped_mapping("shared_classes", "global")),
        
        "facultyIdMapFileName": faculty_map.get("fileName") if faculty_map else None,
        "mainTimetableConfigFileName": main_cfg.get("fileName") if main_cfg else None,
        "labTimetableConfigFileName": lab_cfg.get("fileName") if lab_cfg else None,
        "subjectIdMappingFileName": sub_id_map.get("fileName") if sub_id_map else None,
        "subjectContinuousRulesFileName": sub_cnt.get("fileName") if sub_cnt else None,
        "sharedClassesFileName": (store.get_scoped_mapping("shared_classes", "global") or {}).get("fileName"),
    }

"""

content = content[:stat_start] + new_stat + content[stat_end:]


with open(uploads_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")

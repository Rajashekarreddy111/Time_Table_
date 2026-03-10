from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

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


def _normalize_subject_period_rows(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        subject = _to_text(row.get("subject")) or _to_text(row.get("subject/lab"))
        hours = _to_text(row.get("hours")) or _to_text(row.get("number of hours"))
        continuous = _to_text(row.get("continuous_hours")) or _to_text(row.get("continuous hours that can be allocated"))
        if not subject:
            continue
        try:
            hours_value = int(float(hours))
            continuous_value = int(float(continuous))
        except ValueError:
            raise _validation_error(
                "Invalid hours values in subject periods map",
                [{"subject": subject, "hours": hours, "continuous_hours": continuous}],
            )
        normalized.append(
            {
                "subject": subject,
                "hours": hours_value,
                "continuous_hours": continuous_value,
            }
        )
    if not normalized:
        raise _validation_error(
            "Required columns are missing",
            [{
                "expectedAnyOf": [["subject", "hours", "continuous_hours"], ["subject/lab", "number of hours", "continuous hours that can be allocated"]],
                "receivedColumns": list(rows[0].keys()) if rows else [],
            }],
        )
    return normalized


def _normalize_subject_faculty_rows(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        year = normalize_year(_to_text(row.get("year")))
        section = _to_text(row.get("section")) or _to_text(row.get("section/subject"))
        if not year or not section:
            continue

        # Existing row-wise format: year, section, subject, faculty_id
        subject = _to_text(row.get("subject"))
        faculty_id = _to_text(row.get("faculty_id"))
        if subject and faculty_id:
            normalized.append(
                {
                    "year": year,
                    "section": section,
                    "subject": subject,
                    "faculty_id": faculty_id.split(",")[0].strip(),
                }
            )
            continue

        # Matrix-like format: year, section/subject, subject-1, subject-2, lab-1...
        for key, value in row.items():
            key_text = _to_text(key).lower()
            if key_text in {"year", "section", "section/subject"} or key_text.startswith("__orig_"):
                continue
            faculty_value = _to_text(value)
            if not faculty_value:
                continue
            # Use original column name for subject to preserve case
            orig_key = row.get(f"__orig_{key}", key)
            normalized.append(
                {
                    "year": year,
                    "section": section,
                    "subject": _to_text(orig_key),
                    "faculty_id": faculty_value.split(",")[0].strip(),
                }
            )

    if not normalized:
        raise _validation_error(
            "Required columns are missing",
            [{
                "expectedAnyOf": [["year", "section", "subject", "faculty_id"], ["year", "section/subject", "subject-*", "lab-*"]],
                "receivedColumns": list(rows[0].keys()) if rows else [],
            }],
        )
    return normalized


def _normalize_shared_class_rows(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        year = normalize_year(_to_text(row.get("year")))
        sections_raw = _to_text(row.get("sections"))
        subject = _to_text(row.get("subject"))
        
        if not year or not sections_raw or not subject:
            continue
            
        sections = [s.strip() for s in sections_raw.split(",") if s.strip()]
        if not sections:
            continue
            
        normalized.append({
            "year": year,
            "sections": sections,
            "subject": subject
        })
        
    if not normalized:
        raise _validation_error(
            "Required columns are missing in shared classes file",
            [{"expected": ["year", "sections", "subject"]}],
        )
    return normalized


def _normalize_faculty_availability_rows(rows: list[dict]) -> list[dict]:
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
    if store.get_scoped_mapping("faculty_id_map", scope_key):
        raise _conflict_error("Faculty ID mapping has already been uploaded", [{"scope": "global"}])

    file_id = store.next_file_id("fmap")
    payload = {
        "id": file_id,
        "fileName": file.filename,
        "rowsParsed": len(rows),
        "rows": rows,
        "sourceFile": cloudinary_file,
    }
    store.save_file_map(file_id, payload)
    created = store.save_scoped_mapping("faculty_id_map", scope_key, payload, allow_overwrite=True)
    if not created:
        raise _conflict_error("Faculty ID mapping has already been uploaded", [{"scope": "global"}])
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(rows),
        message="Faculty ID map uploaded successfully for all years/sections",
    )


@router.post("/uploads/subject-faculty-map", response_model=UploadResponse)
async def upload_subject_faculty_map(
    year: str = Form(...),
    batchType: str | None = Form(default=None),
    section: str | None = Form(default=None),
    file: UploadFile = File(...),
):
    if not file.filename:
        raise _validation_error("File name is required", [])
    year = normalize_year(year.strip())
    print(f"DEBUG: Uploading subject-faculty map for year='{year}', batchType='{batchType}'")
    if not year:
        raise _validation_error("Year is required for subject-faculty map", [])
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise _validation_error("Only spreadsheet files (.xlsx, .xls, .csv) are allowed for this upload", [])

    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_subject_faculty_rows(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/subject-faculty-map")
    normalized_batch_type = _normalize_batch_type(batchType)
    scope_key = _scope_key_year_batch(year, normalized_batch_type)

    file_id = store.next_file_id("sfmap")
    payload = {
        "id": file_id,
        "fileName": file.filename,
        "rowsParsed": len(rows),
        "rows": rows,
        "year": year,
        "batchType": normalized_batch_type,
        "sourceFile": cloudinary_file,
    }
    store.save_file_map(file_id, payload)
    created = store.save_scoped_mapping("subject_faculty_map", scope_key, payload, allow_overwrite=True)
    if not created:
        raise _conflict_error(
            "Subject-faculty mapping already exists for this year/batch",
            [{"year": year, "batchType": normalized_batch_type}],
        )
    print(f"DEBUG: Successfully saved subject-faculty map (file_id={file_id}) for {year}")
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(rows),
        message=f"Subject faculty map uploaded successfully for {year} ({normalized_batch_type})",
    )


@router.post("/uploads/subject-periods-map", response_model=UploadResponse)
async def upload_subject_periods_map(
    year: str = Form(...),
    batchType: str | None = Form(default=None),
    file: UploadFile = File(...),
):
    if not file.filename:
        raise _validation_error("File name is required", [])
    year = normalize_year(year.strip())
    if not year:
        raise _validation_error("Year is required for subject-periods map", [])
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise _validation_error("Only spreadsheet files (.xlsx, .xls, .csv) are allowed for this upload", [])

    file_bytes = read_upload_bytes(file)
    dataframe = parse_tabular_upload(file.filename, file_bytes)
    rows = _normalize_subject_period_rows(dataframe_rows(dataframe))
    cloudinary_file = upload_source_file(file.filename, file_bytes, folder="timetable/subject-periods-map")
    normalized_batch_type = _normalize_batch_type(batchType)
    scope_key = _scope_key_year_batch(year, normalized_batch_type)

    file_id = store.next_file_id("spmap")
    payload = {
        "id": file_id,
        "fileName": file.filename,
        "rowsParsed": len(rows),
        "rows": rows,
        "year": year,
        "batchType": normalized_batch_type,
        "sourceFile": cloudinary_file,
    }
    store.save_file_map(file_id, payload)
    created = store.save_scoped_mapping("subject_periods_map", scope_key, payload, allow_overwrite=True)
    if not created:
        raise _conflict_error(
            "Subject-periods mapping already exists for this year/batch",
            [{"year": year, "batchType": normalized_batch_type}],
        )
    return UploadResponse(
        fileId=file_id,
        fileName=file.filename,
        rowsParsed=len(rows),
        message=f"Subject periods map uploaded successfully for {year} ({normalized_batch_type})",
    )


@router.post("/uploads/faculty-availability", response_model=UploadResponse)
async def upload_faculty_availability(file: UploadFile = File(...)):
    if not file.filename:
        raise _validation_error("File name is required", [])
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise _validation_error("Only spreadsheet files (.xlsx, .xls, .csv) are allowed for this upload", [])

    file_bytes = read_upload_bytes(file)
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


@router.get("/uploads/mapping-status")
async def get_mapping_status(
    year: str = Query(...),
    section: str = Query(default=""),
):
    normalized_year = normalize_year(year.strip())
    if not normalized_year:
        raise _validation_error("Year is required", [])

    faculty_map = store.get_scoped_mapping("faculty_id_map", _scope_key_global())
    subject_periods_map_all = store.get_scoped_mapping(
        "subject_periods_map",
        _scope_key_year_batch(normalized_year, "ALL"),
    ) or store.get_scoped_mapping("subject_periods_map", _scope_key_year(normalized_year))
    subject_periods_map_cream = store.get_scoped_mapping(
        "subject_periods_map",
        _scope_key_year_batch(normalized_year, "CREAM"),
    )
    subject_periods_map_general = store.get_scoped_mapping(
        "subject_periods_map",
        _scope_key_year_batch(normalized_year, "GENERAL"),
    )
    subject_faculty_map_all = store.get_scoped_mapping(
        "subject_faculty_map",
        _scope_key_year_batch(normalized_year, "ALL"),
    ) or store.get_scoped_mapping("subject_faculty_map", _scope_key_year(normalized_year))
    subject_faculty_map_cream = store.get_scoped_mapping(
        "subject_faculty_map",
        _scope_key_year_batch(normalized_year, "CREAM"),
    )
    subject_faculty_map_general = store.get_scoped_mapping(
        "subject_faculty_map",
        _scope_key_year_batch(normalized_year, "GENERAL"),
    )

    return {
        "facultyIdMapUploaded": bool(faculty_map),
        "subjectPeriodsMapUploaded": bool(subject_periods_map_all or subject_periods_map_cream or subject_periods_map_general),
        "creamSubjectPeriodsMapUploaded": bool(subject_periods_map_cream),
        "generalSubjectPeriodsMapUploaded": bool(subject_periods_map_general),
        "subjectFacultyMapUploaded": bool(subject_faculty_map_all or subject_faculty_map_cream or subject_faculty_map_general),
        "creamSubjectFacultyMapUploaded": bool(subject_faculty_map_cream),
        "generalSubjectFacultyMapUploaded": bool(subject_faculty_map_general),
        "facultyAvailabilityUploaded": bool(store.get_scoped_mapping("faculty_availability", "global")),
        "sharedClassesUploaded": bool(store.get_scoped_mapping("shared_classes", "global")),
        "facultyIdMapFileName": faculty_map.get("fileName") if faculty_map else None,
        "subjectPeriodsMapFileName": subject_periods_map_all.get("fileName") if subject_periods_map_all else None,
        "creamSubjectPeriodsMapFileName": subject_periods_map_cream.get("fileName") if subject_periods_map_cream else None,
        "generalSubjectPeriodsMapFileName": subject_periods_map_general.get("fileName") if subject_periods_map_general else None,
        "subjectFacultyMapFileName": subject_faculty_map_all.get("fileName") if subject_faculty_map_all else None,
        "creamSubjectFacultyMapFileName": subject_faculty_map_cream.get("fileName") if subject_faculty_map_cream else None,
        "generalSubjectFacultyMapFileName": subject_faculty_map_general.get("fileName") if subject_faculty_map_general else None,
        "sharedClassesFileName": (store.get_scoped_mapping("shared_classes", "global") or {}).get("fileName"),
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

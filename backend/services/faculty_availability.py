from datetime import datetime

from fastapi import HTTPException
from storage.memory_store import MemoryStore
from services.utils import normalize_year

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIOD_TIME = {
    1: "9:10 - 10:00",
    2: "10:00 - 10:50",
    3: "11:00 - 11:50",
    4: "11:50 - 12:40",
    5: "1:30 - 2:20",
    6: "2:20 - 3:10",
    7: "3:10 - 4:00",
}


def _validation_error(message: str, details: list | None = None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "ValidationError", "message": message, "details": details or []},
    )


def _is_ignored(class_info: dict, ignored_years: list[str], ignored_sections: list[str]) -> bool:
    raw_year = str(class_info.get("year", "")).strip()
    if not raw_year:
        return False
    full_year = normalize_year(raw_year)
    if full_year in ignored_years:
        return True
    section_key = f"{full_year}|{str(class_info.get('section', '')).strip()}"
    return section_key in ignored_sections


def _to_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _build_faculty_name_map(store: MemoryStore, faculty_id_map_file_id: str | None) -> dict[str, str]:
    if not faculty_id_map_file_id:
        # Fallback to global scoped mapping
        payload = store.get_scoped_mapping("faculty_id_map", "global")
        if not payload:
            return {}
    else:
        payload = store.get_file_map(faculty_id_map_file_id)
        if not payload:
            raise _validation_error("Invalid facultyIdMapFileId", [])
    name_map: dict[str, str] = {}
    for row in payload.get("rows", []):
        fid = _to_text(row.get("faculty_id"))
        fname = _to_text(row.get("faculty_name"))
        if fid and fname:
            name_map[fid] = fname
    return name_map


def _build_schedules_from_upload(
    store: MemoryStore,
    availability_file_id: str,
    faculty_name_map: dict[str, str],
) -> dict[str, dict[str, dict[int, dict]]]:
    payload = store.get_file_map(availability_file_id)
    if not payload:
        raise _validation_error("Invalid availabilityFileId", [])

    schedules: dict[str, dict[str, dict[int, dict]]] = {}
    for row in payload.get("rows", []):
        day = _to_text(row.get("day")).capitalize()
        try:
            period = int(float(_to_text(row.get("period"))))
        except ValueError:
            continue
        if day not in DAYS or period not in PERIOD_TIME:
            continue

        faculty_id = _to_text(row.get("faculty_id"))
        faculty_name = _to_text(row.get("faculty_name"))
        faculty_key = faculty_name or faculty_name_map.get(faculty_id) or faculty_id
        if not faculty_key:
            continue

        class_info = {
            "year": _to_text(row.get("year")),
            "section": _to_text(row.get("section")),
            "subject": _to_text(row.get("subject")),
        }
        schedules.setdefault(faculty_key, {}).setdefault(day, {})[period] = class_info

    if not schedules:
        raise _validation_error("Uploaded faculty availability file has no valid schedule rows", [])
    return schedules


def get_available_faculty_for_all_periods(
    store: MemoryStore,
    date_value: str,
    periods: list[int],
    faculty_required: int,
    ignored_years: list[str],
    ignored_sections: list[str],
    availability_file_id: str | None,
    faculty_id_map_file_id: str | None,
) -> dict:
    if not availability_file_id:
        raise _validation_error("availabilityFileId is required", [])
    if not periods:
        raise _validation_error("At least one period must be selected", [])

    try:
        day_name = datetime.strptime(date_value, "%Y-%m-%d").strftime("%A")
    except ValueError as exc:
        raise _validation_error("Invalid date format; expected YYYY-MM-DD", []) from exc

    if day_name not in DAYS:
        raise _validation_error("Selected date is Sunday; no classes scheduled", [])

    selected_periods = sorted({p for p in periods if p in PERIOD_TIME})
    if not selected_periods:
        raise _validation_error("No valid teaching periods selected", [])

    faculty_name_map = _build_faculty_name_map(store, faculty_id_map_file_id)
    schedules = _build_schedules_from_upload(store, availability_file_id, faculty_name_map)
    faculty_names = list(schedules.keys())
    common_available: set[str] = set(faculty_names)

    for period in selected_periods:
        period_available: set[str] = set()
        for faculty in faculty_names:
            # 1. Check uploaded availability file
            class_info = schedules.get(faculty, {}).get(day_name, {}).get(period)
            if class_info is None or _is_ignored(class_info, ignored_years, ignored_sections):
                period_available.add(faculty)
        common_available &= period_available

    # 2. Check dynamic occupancy from generated timetables
    occupancy_details = store.get_global_faculty_occupancy_details()
    for item in occupancy_details:
        if item.get("day") == day_name and item.get("period") in selected_periods:
            faculty = str(item.get("faculty", "")).strip()
            if faculty in common_available:
                # Still check if this specific occupancy should be ignored
                # (e.g. if the user wants to ignore the section that this faculty is busy with)
                if not _is_ignored(item, ignored_years, ignored_sections):
                    common_available.discard(faculty)

    return {
        "day": day_name,
        "periods": [{"period": p, "time": PERIOD_TIME[p]} for p in selected_periods],
        "faculty": sorted(common_available)[: max(1, faculty_required)],
    }


def get_bulk_available_faculty(
    store: MemoryStore,
    availability_file_id: str,
    query_file_id: str,
    ignored_years: list[str],
    ignored_sections: list[str],
    faculty_id_map_file_id: str | None,
) -> dict:
    if not availability_file_id:
        raise _validation_error("availabilityFileId is required", [])
    if not query_file_id:
        raise _validation_error("queryFileId is required", [])

    query_payload = store.get_file_map(query_file_id)
    if not query_payload:
        raise _validation_error("Invalid queryFileId", [])
        
    query_rows = query_payload.get("rows", [])
    if not query_rows:
        raise _validation_error("Query file is empty", [])

    faculty_name_map = _build_faculty_name_map(store, faculty_id_map_file_id)
    schedules = _build_schedules_from_upload(store, availability_file_id, faculty_name_map)
    faculty_names = list(schedules.keys())
    occupancy_details = store.get_global_faculty_occupancy_details()

    results = []

    for row in query_rows:
        date_value = row.get("date")
        faculty_required = row.get("facultyRequired", 1)
        periods = row.get("periods", [])

        if not periods:
            continue
            
        try:
            day_name = datetime.strptime(date_value, "%Y-%m-%d").strftime("%A")
        except ValueError:
            try:
                from dateutil import parser
                day_name = parser.parse(date_value).strftime("%A")
            except Exception:
                continue

        if day_name not in DAYS:
            continue

        selected_periods = sorted({p for p in periods if p in PERIOD_TIME})
        if not selected_periods:
            continue

        common_available: set[str] = set(faculty_names)

        for period in selected_periods:
            period_available: set[str] = set()
            for faculty in faculty_names:
                class_info = schedules.get(faculty, {}).get(day_name, {}).get(period)
                if class_info is None or _is_ignored(class_info, ignored_years, ignored_sections):
                    period_available.add(faculty)
            common_available &= period_available

        for item in occupancy_details:
            if item.get("day") == day_name and item.get("period") in selected_periods:
                faculty = str(item.get("faculty", "")).strip()
                if faculty in common_available:
                    if not _is_ignored(item, ignored_years, ignored_sections):
                        common_available.discard(faculty)

        results.append({
            "date": date_value,
            "day": day_name,
            "periods": [{"period": p, "time": PERIOD_TIME[p]} for p in selected_periods],
            "faculty": sorted(common_available)[: max(1, faculty_required)],
            "facultyRequired": faculty_required
        })

    return {"results": results}

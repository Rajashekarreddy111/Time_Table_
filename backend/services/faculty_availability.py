from datetime import datetime
import re

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
    section = str(class_info.get("section", "")).strip()
    if not section:
        return False
    normalized_ignored = _normalize_ignored_sections(ignored_sections)
    for candidate in _build_section_candidates(full_year, section):
        if candidate in normalized_ignored:
            return True
    return False


def _to_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_day(value) -> str:
    raw = _to_text(value)
    if not raw:
        return ""
    compact = re.sub(r"[^A-Z]+", "", raw.upper())
    day_map = {
        "MON": "Monday",
        "MONDAY": "Monday",
        "TUE": "Tuesday",
        "TUESDAY": "Tuesday",
        "WED": "Wednesday",
        "WEDNESDAY": "Wednesday",
        "THU": "Thursday",
        "THURSDAY": "Thursday",
        "FRI": "Friday",
        "FRIDAY": "Friday",
        "SAT": "Saturday",
        "SATURDAY": "Saturday",
    }
    return day_map.get(compact, raw.capitalize())


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


def _normalize_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _build_section_candidates(full_year: str, section: str) -> set[str]:
    section_value = str(section or "").strip()
    if not section_value:
        return set()

    raw_year = str(full_year or "").strip()
    year_number = "".join(ch for ch in raw_year if ch.isdigit())
    compact = f"{year_number}{section_value}" if year_number else section_value
    section_without_year_suffix = section_value
    if year_number:
        suffix_pattern = re.compile(rf"[-_/ ]?{re.escape(year_number)}$", re.IGNORECASE)
        section_without_year_suffix = suffix_pattern.sub("", section_value).strip()

    candidates = {
        _normalize_token(section_value),
        _normalize_token(section_without_year_suffix),
        _normalize_token(f"{raw_year}|{section_value}"),
        _normalize_token(f"{raw_year}|{section_without_year_suffix}"),
        _normalize_token(f"{raw_year} {section_value}"),
        _normalize_token(f"{raw_year} {section_without_year_suffix}"),
        _normalize_token(compact),
        _normalize_token(f"{year_number}{section_without_year_suffix}") if year_number else "",
    }
    return {candidate for candidate in candidates if candidate}


def _normalize_ignored_sections(ignored_sections: list[str]) -> set[str]:
    normalized: set[str] = set()
    for item in ignored_sections:
        text = str(item or "").strip()
        if not text:
            continue
        normalized.add(_normalize_token(text))
        if "|" in text:
            _, _, tail = text.partition("|")
            if tail.strip():
                normalized.add(_normalize_token(tail))
        else:
            normalized_year = normalize_year(text)
            if normalized_year != text:
                normalized.add(_normalize_token(normalized_year))
    return normalized


def _availability_result(
    day_name: str,
    selected_periods: list[int],
    selected_faculty: list[str],
    faculty_required: int,
    available_count: int,
) -> dict:
    safe_required = max(1, int(faculty_required or 1))
    sufficient = available_count >= safe_required
    shortage = max(0, safe_required - available_count)
    if sufficient:
        message = (
            f"Sufficient faculty available. Selected {len(selected_faculty)} "
            f"out of {available_count} available."
        )
    elif available_count > 0:
        message = (
            f"Only {available_count} faculty available; {safe_required} requested. "
            "No sufficient faculty available."
        )
    else:
        message = (
            f"No faculty available for the selected slot(s); {safe_required} requested."
        )

    return {
        "day": day_name,
        "periods": [{"period": p, "time": PERIOD_TIME[p]} for p in selected_periods],
        "faculty": selected_faculty,
        "availableFacultyCount": available_count,
        "sufficientFaculty": sufficient,
        "shortageCount": shortage,
        "message": message,
    }


def _fair_select_faculty(
    available_faculty: set[str],
    faculty_required: int,
    selection_counts: dict[str, int] | None = None,
) -> list[str]:
    safe_required = max(1, int(faculty_required or 1))
    available_list = sorted(available_faculty)
    if selection_counts is None:
        return available_list[:safe_required]

    ranked = sorted(
        available_list,
        key=lambda faculty: (selection_counts.get(faculty, 0), faculty.lower(), faculty),
    )
    chosen = ranked[: min(safe_required, len(ranked))]
    for faculty in chosen:
        selection_counts[faculty] = selection_counts.get(faculty, 0) + 1
    return chosen


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
        day = _normalize_day(row.get("day"))
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
            "is_available": bool(row.get("is_available")),
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
            if (
                class_info is None
                or class_info.get("is_available")
                or _is_ignored(class_info, ignored_years, ignored_sections)
            ):
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

    selected_faculty = _fair_select_faculty(common_available, faculty_required)
    return _availability_result(
        day_name=day_name,
        selected_periods=selected_periods,
        selected_faculty=selected_faculty,
        faculty_required=faculty_required,
        available_count=len(common_available),
    )


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
    selection_counts: dict[str, int] = {}

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
                if (
                    class_info is None
                    or class_info.get("is_available")
                    or _is_ignored(class_info, ignored_years, ignored_sections)
                ):
                    period_available.add(faculty)
            common_available &= period_available

        for item in occupancy_details:
            if item.get("day") == day_name and item.get("period") in selected_periods:
                faculty = str(item.get("faculty", "")).strip()
                if faculty in common_available:
                    if not _is_ignored(item, ignored_years, ignored_sections):
                        common_available.discard(faculty)

        selected_faculty = _fair_select_faculty(
            common_available,
            faculty_required,
            selection_counts,
        )
        results.append({
            "date": date_value,
            "facultyRequired": faculty_required,
            **_availability_result(
                day_name=day_name,
                selected_periods=selected_periods,
                selected_faculty=selected_faculty,
                faculty_required=faculty_required,
                available_count=len(common_available),
            ),
        })

    return {"results": results}

from __future__ import annotations

import base64
import random
import time
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, Side

from models.schemas import GenerateTimetableRequest
from services.utils import normalize_year
from storage.memory_store import MemoryStore

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIODS = [1, 2, 3, 4, 5, 6, 7]
DAY_INDEX = {index + 1: day for index, day in enumerate(DAYS)}
DAY_SHORT_LABELS = {
    "Monday": "M\nO\nN",
    "Tuesday": "T\nU\nE",
    "Wednesday": "W\nE\nD",
    "Thursday": "T\nH\nU",
    "Friday": "F\nR\nI",
    "Saturday": "S\nA\nT",
}
ACADEMIC_METADATA = {
    "college": "NARASARAOPETA ENGINEERING COLLEGE :: NARASARAOPET",
    "department": "Department of Computer Science & Engineering",
    "semester": "II SEMESTER",
}
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
MEDIUM_BORDER = Border(
    left=Side(style="medium"),
    right=Side(style="medium"),
    top=Side(style="medium"),
    bottom=Side(style="medium"),
)
CENTER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT_ALIGNMENT = Alignment(horizontal="left", vertical="center", wrap_text=True)
BOLD_FONT = Font(bold=True)


def _academic_year_label() -> str:
    now = datetime.now()
    start_year = now.year if now.month >= 6 else now.year - 1
    return f"{start_year}-{start_year + 1}"


def _semester_label(value: int | str | None) -> str:
    semester = str(value or "").strip()
    if semester == "1":
        return "I SEMESTER"
    if semester == "2":
        return "II SEMESTER"
    return ACADEMIC_METADATA["semester"]


def _display_effective_date(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return raw


def _resolve_timetable_metadata(raw_meta: dict[str, Any] | None) -> dict[str, str]:
    meta = raw_meta or {}
    academic_year = str(meta.get("academicYear") or "").strip() or _academic_year_label()
    semester = _semester_label(meta.get("semester"))
    with_effect_from = str(meta.get("withEffectFrom") or "").strip()
    return {
        "academicYear": academic_year,
        "semester": semester,
        "withEffectFrom": with_effect_from,
        "withEffectFromDisplay": _display_effective_date(with_effect_from),
    }


def _class_title(year: str, section: str, semester_label: str | None = None) -> str:
    year_map = {
        "2nd Year": "II B.Tech",
        "3rd Year": "III B.Tech",
        "4th Year": "IV B.Tech",
    }
    normalized = year_map.get(year, year)
    return f"{normalized} [CSE - {section}] {semester_label or ACADEMIC_METADATA['semester']} TIME TABLE"


@dataclass
class Requirement:
    subject_id: str
    faculty_id: str
    faculty_options: tuple[str, ...]
    faculty_team: tuple[str, ...]
    sections: tuple[str, ...]
    hours: int
    min_consecutive_hours: int
    max_consecutive_hours: int
    shared: bool
    common_faculty: bool = False
    phase: int = 4


@dataclass(frozen=True)
class SlotCandidate:
    day: str
    start_period: int
    block_size: int
    faculty_id: str
    faculty_ids: tuple[str, ...]
    score: int


def _validation_error(message: str, details: list | None = None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "ValidationError", "message": message, "details": details or []},
    )


def _normalize_day(value: str | int) -> str | None:
    if isinstance(value, int):
        return DAY_INDEX.get(value)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return DAY_INDEX.get(int(text))
    lowered = text.lower()
    for day in DAYS:
        if day.lower().startswith(lowered[:3]):
            return day
    return None


def _resolve_faculty_output(faculty_id: str, faculty_id_to_name: dict[str, str]) -> tuple[str, str]:
    token = str(faculty_id).strip()
    faculty_name = faculty_id_to_name.get(token, token)
    return token, faculty_name


def _resolve_subject_output(subject_id: str, subject_id_to_name: dict[str, str]) -> tuple[str, str]:
    token = str(subject_id).strip()
    if token.endswith(".0"):
        token = token[:-2]
    subject_name = subject_id_to_name.get(token, token)
    return token, subject_name


def _normalize_id_token(value: str | int | float | None) -> str:
    token = str(value or "").strip()
    if token.endswith(".0"):
        token = token[:-2]
    return token


def _split_faculty_tokens(raw_faculty_id: str) -> tuple[str, ...]:
    tokens = [str(raw_faculty_id or "").strip()]
    for delimiter in [",", "/", "|", "+", "&"]:
        next_tokens: list[str] = []
        for token in tokens:
            next_tokens.extend(part.strip() for part in token.split(delimiter))
        tokens = next_tokens
    cleaned: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        normalized = _normalize_id_token(token)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return tuple(cleaned)


def _normalize_faculty_field(raw_faculty_id: str | int | float | None) -> str:
    return ",".join(_split_faculty_tokens(str(raw_faculty_id or "")))


def _faculty_alias_to_id_map(faculty_id_to_name: dict[str, str]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for faculty_id, faculty_name in faculty_id_to_name.items():
        normalized_id = _normalize_id_token(faculty_id)
        if normalized_id:
            alias_map[normalized_id] = normalized_id
            alias_map[normalized_id.lower()] = normalized_id
        normalized_name = str(faculty_name).strip()
        if normalized_name:
            alias_map[normalized_name] = normalized_id or normalized_name
            alias_map[normalized_name.lower()] = normalized_id or normalized_name
    return alias_map


def _canonicalize_faculty_token(
    value: str | int | float | None,
    faculty_id_to_name: dict[str, str],
) -> str:
    token = _normalize_id_token(value)
    if not token:
        return ""
    alias_map = _faculty_alias_to_id_map(faculty_id_to_name)
    return alias_map.get(token, alias_map.get(token.lower(), token))


def _resolve_faculty_display(
    faculty_ids: tuple[str, ...],
    faculty_id_to_name: dict[str, str],
) -> tuple[str, str]:
    ids = tuple(
        _canonicalize_faculty_token(fid, faculty_id_to_name)
        for fid in faculty_ids
        if _canonicalize_faculty_token(fid, faculty_id_to_name)
    )
    names = tuple(faculty_id_to_name.get(fid, fid) for fid in ids)
    return ",".join(ids), ", ".join(names)


def _build_faculty_maps(request_data: GenerateTimetableRequest, store: MemoryStore) -> dict[str, str]:
    faculty_id_to_name: dict[str, str] = {}
    fac_map_payload = store.get_scoped_mapping("faculty_id_map", "global")
    # Fallback: load from file-map if caller supplied mappingFileIds but
    # scoped mappings are not present (or empty) (common when backend restarts).
    if (not fac_map_payload or not fac_map_payload.get("rows")) and request_data.mappingFileIds and request_data.mappingFileIds.facultyIdMap:
        fac_map_payload = store.get_file_map(request_data.mappingFileIds.facultyIdMap)
    if fac_map_payload:
        for row in fac_map_payload.get("rows", []):
            faculty_id = _normalize_faculty_field(row.get("faculty_id", ""))
            faculty_name = str(row.get("faculty_name", "")).strip()
            if faculty_id:
                faculty_id_to_name[faculty_id] = faculty_name or faculty_id
    for row in request_data.facultyIdNameMapping:
        faculty_id = _normalize_faculty_field(row.facultyId)
        faculty_name = str(row.facultyName).strip()
        if faculty_id:
            faculty_id_to_name[faculty_id] = faculty_name or faculty_id
    return faculty_id_to_name


def _build_subject_maps(
    request_data: GenerateTimetableRequest,
    store: MemoryStore,
) -> tuple[dict[str, str], dict[str, int]]:
    subject_id_to_name: dict[str, str] = {}
    compulsory_continuous: dict[str, int] = {}

    subject_map_payload = store.get_scoped_mapping("subject_id_mapping", "global")
    if (not subject_map_payload or not subject_map_payload.get("rows")) and request_data.mappingFileIds and request_data.mappingFileIds.subjectIdMapping:
        subject_map_payload = store.get_file_map(request_data.mappingFileIds.subjectIdMapping)
    if subject_map_payload:
        for row in subject_map_payload.get("rows", []):
            subject_id = _normalize_id_token(row.get("subject_id", ""))
            subject_name = str(row.get("subject_name", "")).strip()
            if subject_id:
                subject_id_to_name[subject_id] = subject_name or subject_id

    rule_payload = store.get_scoped_mapping("subject_continuous_rules", "global")
    if (not rule_payload or not rule_payload.get("rows")) and request_data.mappingFileIds and request_data.mappingFileIds.subjectContinuousRules:
        rule_payload = store.get_file_map(request_data.mappingFileIds.subjectContinuousRules)
    if rule_payload:
        for row in rule_payload.get("rows", []):
            subject_id = _normalize_id_token(row.get("subject_id", ""))
            if subject_id:
                compulsory_continuous[subject_id] = max(
                    1, int(row.get("compulsory_continuous_hours", 1) or 1)
                )

    for row in request_data.subjectIdNameMapping:
        subject_id = _normalize_id_token(row.subjectId)
        subject_name = str(row.subjectName).strip()
        if subject_id:
            subject_id_to_name[subject_id] = subject_name or subject_id

    for row in request_data.subjectContinuousRules:
        subject_id = _normalize_id_token(row.subjectId)
        if subject_id:
            compulsory_continuous[subject_id] = max(1, int(row.compulsoryContinuousHours or 1))

    return subject_id_to_name, compulsory_continuous


def _build_faculty_availability(
    request_data: GenerateTimetableRequest,
    store: MemoryStore,
    all_faculties: set[str],
    faculty_id_to_name: dict[str, str],
) -> dict[str, dict[str, set[int]]]:
    availability: dict[str, dict[str, set[int]]] = {
        fid: {day: set(PERIODS) for day in DAYS} for fid in all_faculties
    }

    reverse_faculty_name_map = {
        name.strip(): faculty_id for faculty_id, name in faculty_id_to_name.items() if name.strip()
    }

    def resolve_faculty_key(raw_id: str, raw_name: str = "") -> str:
        faculty_id = _canonicalize_faculty_token(_normalize_faculty_field(raw_id), faculty_id_to_name)
        if faculty_id:
            return faculty_id
        faculty_name = str(raw_name).strip()
        return _canonicalize_faculty_token(reverse_faculty_name_map.get(faculty_name, faculty_name), faculty_id_to_name)

    uploaded_payload = store.get_scoped_mapping("faculty_availability", "global")
    if uploaded_payload:
        uploaded_faculties: set[str] = set()
        for row in uploaded_payload.get("rows", []):
            faculty_key = resolve_faculty_key(row.get("faculty_id", ""), row.get("faculty_name", ""))
            faculty_keys = _split_faculty_tokens(faculty_key) or ((faculty_key,) if faculty_key else ())
            day = _normalize_day(str(row.get("day", "")))
            period = int(row.get("period", 0) or 0)
            if not faculty_keys or not day or period not in PERIODS:
                continue
            for key in faculty_keys:
                availability.setdefault(key, {name: set(PERIODS) for name in DAYS})
                if key not in uploaded_faculties:
                    availability[key] = {name: set() for name in DAYS}
                    uploaded_faculties.add(key)
                availability[key][day].add(period)

    for entry in request_data.facultyAvailability:
        faculty_keys = _split_faculty_tokens(str(entry.facultyId).strip())
        if not faculty_keys:
            continue
        for faculty_key in faculty_keys:
            availability.setdefault(faculty_key, {name: set(PERIODS) for name in DAYS})
            for raw_day, periods in entry.availablePeriodsByDay.items():
                day = _normalize_day(raw_day)
                if not day:
                    continue
                availability[faculty_key][day] = {int(p) for p in periods if int(p) in PERIODS}
    return availability


def _resolve_faculty_pool(
    raw_faculty_id: str,
    faculty_id_to_name: dict[str, str],
    faculty_availability: dict[str, dict[str, set[int]]],
) -> tuple[str, ...]:
    faculty_raw = str(raw_faculty_id or "").strip()
    if any(delimiter in faculty_raw for delimiter in [",", "/", "|", "+", "&"]):
        split_pool = tuple(
            _canonicalize_faculty_token(token, faculty_id_to_name)
            for token in _split_faculty_tokens(faculty_raw)
            if _canonicalize_faculty_token(token, faculty_id_to_name)
        )
        if split_pool:
            return tuple(sorted(set(split_pool)))
    faculty_token = _canonicalize_faculty_token(faculty_raw, faculty_id_to_name)
    if not faculty_token:
        return ()
    if faculty_token in faculty_id_to_name or faculty_token in faculty_availability:
        return (faculty_token,)

    normalized_matches = [
        faculty_id
        for faculty_id, faculty_name in faculty_id_to_name.items()
        if faculty_token.lower() in str(faculty_name).strip().lower()
    ]
    if normalized_matches:
        return tuple(sorted(set(normalized_matches)))

    cleaned_split = tuple(
        _canonicalize_faculty_token(token, faculty_id_to_name)
        for token in _split_faculty_tokens(faculty_token)
        if _canonicalize_faculty_token(token, faculty_id_to_name)
    )
    if len(cleaned_split) > 1:
        return tuple(sorted(set(cleaned_split)))
    return (faculty_token,)


def _pick_best_faculty_option_for_locked_session(
    faculty_options: tuple[str, ...],
    day: str,
    periods: tuple[int, ...],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
) -> str | None:
    if not faculty_options:
        return None

    best: tuple[int, int, int, str] | None = None
    selected: str | None = None
    for faculty_id in faculty_options:
        allowed = faculty_availability.get(faculty_id, _default_day_availability()).get(day, set(PERIODS))
        unavailable = sum(1 for period in periods if period not in allowed)
        conflicts = sum(1 for period in periods if (day, period) in faculty_busy.setdefault(faculty_id, set()))
        load = _faculty_daily_load(faculty_id, day, faculty_busy)
        score = (unavailable, conflicts, load, faculty_id)
        if best is None or score < best:
            best = score
            selected = faculty_id
    return selected


def _choose_faculty_for_slot(
    requirement: Requirement,
    day: str,
    start_period: int,
    block_size: int,
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
) -> str | None:
    periods = range(start_period, start_period + block_size)
    if requirement.faculty_team:
        for faculty_id in requirement.faculty_team:
            allowed_periods = faculty_availability.get(faculty_id, _default_day_availability()).get(day, set(PERIODS))
            if any(period not in allowed_periods for period in periods):
                return None
            if any((day, period) in faculty_busy.setdefault(faculty_id, set()) for period in periods):
                return None
        return ",".join(requirement.faculty_team)

    best_faculty: str | None = None
    best_key: tuple[int, int, str] | None = None
    faculty_options = requirement.faculty_options or ((requirement.faculty_id,) if requirement.faculty_id else ())
    for faculty_id in faculty_options:
        allowed_periods = faculty_availability.get(faculty_id, _default_day_availability()).get(day, set(PERIODS))
        if any(period not in allowed_periods for period in periods):
            continue
        if any((day, period) in faculty_busy.setdefault(faculty_id, set()) for period in periods):
            continue
        key = (
            _faculty_daily_load(faculty_id, day, faculty_busy),
            _faculty_weekly_capacity(faculty_id, faculty_availability),
            faculty_id,
        )
        if best_key is None or key < best_key:
            best_key = key
            best_faculty = faculty_id
    return best_faculty


def _candidate_block_sizes(
    remaining_hours: int,
    min_consecutive_hours: int,
    max_consecutive_hours: int,
) -> list[int]:
    if remaining_hours <= 0:
        return []
    minimum = max(1, min_consecutive_hours)
    maximum = max(minimum, max_consecutive_hours)
    upper_bound = min(remaining_hours, maximum)
    sizes = list(range(upper_bound, minimum - 1, -1))
    if minimum > 1:
        sizes.extend(range(minimum - 1, 0, -1))
    return sizes


def _is_allowed_compulsory_block_placement(
    requirement: Requirement,
    start_period: int,
    block_size: int,
) -> bool:
    if block_size <= 1 or requirement.min_consecutive_hours <= 1:
        return True

    allowed_starts_by_size: dict[int, set[int]] = {
        2: {1, 3, 5, 6},
        3: {1, 5},
        4: {1},
    }
    allowed_starts = allowed_starts_by_size.get(block_size)
    if allowed_starts is None:
        return False
    return start_period in allowed_starts


def _default_day_availability() -> dict[str, set[int]]:
    return {day: set(PERIODS) for day in DAYS}


def _slot_is_free(
    sections: tuple[str, ...],
    requirement: Requirement,
    day: str,
    start_period: int,
    block_size: int,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
    year: str,
) -> bool:
    if start_period + block_size - 1 > PERIODS[-1]:
        return False
    if not _is_allowed_compulsory_block_placement(requirement, start_period, block_size):
        return False
    periods = range(start_period, start_period + block_size)
    for period in periods:
        for section in sections:
            if schedules[(year, section)][day][period] is not None:
                return False
    selected_faculty = _choose_faculty_for_slot(
        requirement,
        day,
        start_period,
        block_size,
        faculty_busy,
        faculty_availability,
    )
    return selected_faculty is not None


def _count_free_periods_for_sections(
    sections: tuple[str, ...],
    day: str,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    year: str,
) -> int:
    free_count = 0
    for period in PERIODS:
        if all(schedules[(year, section)][day][period] is None for section in sections):
            free_count += 1
    return free_count


def _count_available_periods_for_faculty(
    faculty_id: str,
    day: str,
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
) -> int:
    allowed_periods = faculty_availability.get(faculty_id, _default_day_availability()).get(day, set(PERIODS))
    return sum(1 for period in allowed_periods if (day, period) not in faculty_busy.setdefault(faculty_id, set()))


def _faculty_weekly_capacity(
    faculty_id: str,
    faculty_availability: dict[str, dict[str, set[int]]],
) -> int:
    day_map = faculty_availability.get(faculty_id, _default_day_availability())
    return sum(len(periods) for periods in day_map.values())


def _requirement_weekly_capacity(
    requirement: Requirement,
    faculty_availability: dict[str, dict[str, set[int]]],
) -> int:
    if requirement.faculty_team:
        capacities = [_faculty_weekly_capacity(fid, faculty_availability) for fid in requirement.faculty_team]
        return min(capacities) if capacities else 0
    faculty_options = requirement.faculty_options or ((requirement.faculty_id,) if requirement.faculty_id else ())
    if not faculty_options:
        return len(DAYS) * len(PERIODS)
    return max(_faculty_weekly_capacity(faculty_id, faculty_availability) for faculty_id in faculty_options)


def _faculty_daily_load(
    faculty_id: str,
    day: str,
    faculty_busy: dict[str, set[tuple[str, int]]],
) -> int:
    return sum(1 for busy_day, _ in faculty_busy.setdefault(faculty_id, set()) if busy_day == day)


def _subject_daily_load(
    requirement: Requirement,
    day: str,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    year: str,
) -> int:
    count = 0
    for section in requirement.sections:
        for period in PERIODS:
            entry = schedules[(year, section)][day][period]
            if not entry:
                continue
            slot_subject_id = str(entry.get("subjectId", "")).strip()
            slot_subject = str(entry.get("subject", "")).strip()
            if slot_subject_id == requirement.subject_id or slot_subject == requirement.subject_id:
                count += 1
    return count


def _remaining_empty_slots_for_sections(
    sections: tuple[str, ...],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    year: str,
) -> int:
    return sum(
        1
        for section in sections
        for day in DAYS
        for period in PERIODS
        if schedules[(year, section)][day][period] is None
    )


def _remaining_hours_per_section(
    requirements: list[Requirement],
    remaining_hours: dict[int, int],
) -> dict[str, int]:
    section_hours: dict[str, int] = {}
    for req_idx, requirement in enumerate(requirements):
        remaining = remaining_hours.get(req_idx, 0)
        if remaining <= 0:
            continue
        for section in requirement.sections:
            section_hours[section] = section_hours.get(section, 0) + remaining
    return section_hours


def _section_capacity_is_feasible(
    requirements: list[Requirement],
    remaining_hours: dict[int, int],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    year: str,
) -> bool:
    remaining_by_section = _remaining_hours_per_section(requirements, remaining_hours)
    for section, remaining in remaining_by_section.items():
        free_slots = sum(
            1
            for day in DAYS
            for period in PERIODS
            if schedules[(year, section)][day][period] is None
        )
        if remaining > free_slots:
            return False
    return True


def _compute_timeout_seconds(section_count: int, requirement_count: int) -> int:
    # §18: adaptive timeout – 30s small, 90s medium, 180s large
    if section_count <= 5:
        base = 120
    elif section_count <= 10:
        base = 300
    else:
        base = 600
    if requirement_count >= 20:
        base += 180
    if requirement_count >= 35:
        base += 180
    if requirement_count >= 50:
        base += 240
    if requirement_count >= 70:
        base += 180
    return min(1200, base)


def _requirement_priority(
    requirement: Requirement,
    faculty_availability: dict[str, dict[str, set[int]]],
) -> tuple[int, int, int, int, int, str, str]:
    weekly_capacity = _requirement_weekly_capacity(requirement, faculty_availability)
    strict_availability = len(DAYS) * len(PERIODS) - weekly_capacity
    return (
        requirement.phase,
        0 if requirement.common_faculty else 1,
        -requirement.hours,
        -requirement.min_consecutive_hours,
        -strict_availability,
        requirement.subject_id,
        ",".join(requirement.sections),
    )


def _determine_requirement_phase(
    shared: bool,
    min_consecutive_hours: int,
    hours: int,
    faculty_options: tuple[str, ...],
    faculty_availability: dict[str, dict[str, set[int]]],
) -> int:
    if shared:
        return 1
    if hours >= 4:
        return 2
    if min_consecutive_hours > 1:
        return 3
    return 4


def _requirement_faculty_tokens(requirement: Requirement) -> tuple[str, ...]:
    if requirement.faculty_team:
        return tuple(
            _normalize_id_token(faculty_id)
            for faculty_id in requirement.faculty_team
            if _normalize_id_token(faculty_id)
        )
    if requirement.faculty_options:
        return tuple(
            _normalize_id_token(faculty_id)
            for faculty_id in requirement.faculty_options
            if _normalize_id_token(faculty_id)
        )
    return _split_faculty_tokens(requirement.faculty_id)


def _extract_faculty_occupancy_from_timetable(record: dict | None) -> dict[str, set[tuple[str, int]]]:
    return _extract_faculty_occupancy_from_timetable_with_map(record, {})


def _extract_faculty_occupancy_from_timetable_with_map(
    record: dict | None,
    faculty_id_to_name: dict[str, str],
) -> dict[str, set[tuple[str, int]]]:
    occupancy: dict[str, set[tuple[str, int]]] = {}
    if not record:
        return occupancy

    all_grids = record.get("allGrids")
    if not isinstance(all_grids, dict):
        section = str(record.get("section", "")).strip()
        grid = record.get("grid")
        all_grids = {section: grid} if section and isinstance(grid, dict) else {}

    for grid in all_grids.values():
        if not isinstance(grid, dict):
            continue
        for raw_day, slots in grid.items():
            day = _normalize_day(str(raw_day))
            if not day or not isinstance(slots, list):
                continue
            for period_index, slot in enumerate(slots, start=1):
                if period_index not in PERIODS or not isinstance(slot, dict):
                    continue
                raw_faculty_values = [
                    slot.get("facultyId") or "",
                    slot.get("facultyName") or "",
                    slot.get("faculty") or "",
                ]
                canonical_tokens: set[str] = set()
                for raw_value in raw_faculty_values:
                    for token in _split_faculty_tokens(str(raw_value)):
                        canonical = _canonicalize_faculty_token(token, faculty_id_to_name)
                        if canonical:
                            canonical_tokens.add(canonical)
                for faculty_id in canonical_tokens:
                    occupancy.setdefault(faculty_id, set()).add((day, period_index))
    return occupancy


def _build_prior_faculty_occupancy(
    timetable_ids: list[str],
    store: MemoryStore,
    faculty_id_to_name: dict[str, str],
) -> dict[str, set[tuple[str, int]]]:
    occupancy: dict[str, set[tuple[str, int]]] = {}
    for timetable_id in timetable_ids:
        record = store.get_timetable(str(timetable_id).strip())
        extracted = _extract_faculty_occupancy_from_timetable_with_map(record, faculty_id_to_name)
        for faculty_id, slots in extracted.items():
            occupancy.setdefault(faculty_id, set()).update(slots)
    return occupancy


def _latest_timetable_ids_by_year(
    store: MemoryStore,
    exclude_year: str = "",
) -> list[str]:
    selected: list[str] = []
    seen_years: set[str] = set()
    for record in store.list_timetables():
        year = normalize_year(str(record.get("year", "")))
        timetable_id = str(record.get("id", "")).strip()
        if not timetable_id or not year or year == exclude_year or year in seen_years:
            continue
        seen_years.add(year)
        selected.append(timetable_id)
    return selected


def _is_lab_seed_record(record: dict | None) -> bool:
    if not isinstance(record, dict):
        return False
    if bool(record.get("labSeed")):
        return True
    generation_meta = record.get("generationMeta")
    return isinstance(generation_meta, dict) and bool(generation_meta.get("labSeed"))


def _build_global_section_subject_faculty_index(
    rows: list[dict],
    faculty_id_to_name: dict[str, str],
) -> dict[tuple[str, str, str], str]:
    index: dict[tuple[str, str, str], str] = {}
    for row in rows:
        year = normalize_year(str(row.get("year", "")))
        section = str(row.get("section", "")).strip()
        subject_id = _normalize_id_token(row.get("subject_id", ""))
        faculty_id = ",".join(
            _canonicalize_faculty_token(token, faculty_id_to_name)
            for token in _split_faculty_tokens(str(row.get("faculty_id", "")))
            if _canonicalize_faculty_token(token, faculty_id_to_name)
        )
        if year and section and subject_id and faculty_id:
            index[(year, section, subject_id)] = faculty_id
    return index


def _build_global_lab_occupancy(
    all_main_rows: list[dict],
    all_lab_rows: list[dict],
    current_year: str,
    faculty_id_to_name: dict[str, str],
    faculty_availability: dict[str, dict[str, set[int]]],
) -> dict[str, set[tuple[str, int]]]:
    occupancy: dict[str, set[tuple[str, int]]] = {}
    faculty_index = _build_global_section_subject_faculty_index(all_main_rows, faculty_id_to_name)

    for row in all_lab_rows:
        lab_year = normalize_year(str(row.get("year", "")))
        if not lab_year or lab_year == current_year:
            continue
        section = str(row.get("section", "")).strip()
        subject_id = _normalize_id_token(row.get("subject_id", ""))
        day = _normalize_day(int(row.get("day", 0) or 0))
        periods = [int(period) for period in row.get("hours", []) if int(period) in PERIODS]
        if not section or not subject_id or not day or not periods:
            continue
        raw_faculty_id = faculty_index.get((lab_year, section, subject_id), "")
        faculty_ids = _resolve_faculty_pool(raw_faculty_id, faculty_id_to_name, faculty_availability)
        for faculty_id in faculty_ids:
            occupancy.setdefault(faculty_id, set()).update((day, period) for period in periods)
    return occupancy


def _persist_faculty_occupancy(
    store: MemoryStore,
    timetable_id: str,
    session_log: list[dict],
) -> None:
    store.delete_occupancy_by_source(timetable_id)
    persisted: set[tuple[str, str, int]] = set()
    for session in session_log:
        day = _normalize_day(str(session.get("day", "")))
        if not day:
            continue
        periods = [int(period) for period in session.get("periods", []) if int(period) in PERIODS]
        if not periods:
            continue
        faculty_ids = [
            _normalize_id_token(faculty_id)
            for faculty_id in session.get("faculty_ids", [])
            if _normalize_id_token(faculty_id)
        ]
        if not faculty_ids:
            faculty_ids = list(_split_faculty_tokens(str(session.get("faculty_id", ""))))
        if not faculty_ids:
            continue
        section_label = ",".join(
            sorted(str(section).strip() for section in session.get("sections", []) if str(section).strip())
        )
        year_label = str(session.get("year", "")).strip() or None
        for faculty_id in faculty_ids:
            for period in periods:
                marker = (faculty_id, day, period)
                if marker in persisted:
                    continue
                persisted.add(marker)
                store.mark_faculty_busy(
                    faculty=faculty_id,
                    day=day,
                    period=period,
                    source_id=timetable_id,
                    year=year_label,
                    section=section_label or None,
                )


def _score_slot_candidate(
    requirement: Requirement,
    faculty_id: str,
    day: str,
    start_period: int,
    block_size: int,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
    year: str,
) -> int:
    # §14: slot scoring weights – +5 section free, +5 faculty available, +3 continuous, -5 conflict
    section_flex = _count_free_periods_for_sections(requirement.sections, day, schedules, year) # Changed PERIODS
    faculty_flex = _count_available_periods_for_faculty(faculty_id, day, faculty_busy, faculty_availability) # Changed PERIODS
    faculty_load = _faculty_daily_load(faculty_id, day, faculty_busy)
    subject_load = _subject_daily_load(requirement, day, schedules, year) # Changed PERIODS
    empty_slots = _remaining_empty_slots_for_sections(requirement.sections, schedules, year) # Changed PERIODS
    center_bonus = 2 if start_period not in (PERIODS[0], PERIODS[-1]) else 0 # Changed PERIODS = PERIODS
    # Primary scoring per spec
    section_free_score = 5 if section_flex > 0 else -5
    faculty_available_score = 5 if faculty_flex > 0 else -5
    continuous_score = 3 if block_size >= requirement.min_consecutive_hours else -10
    conflict_penalty = -5 if faculty_load + block_size > 5 else 0  # penalise overloaded days
    # Secondary heuristics
    shared_bonus = 2 if requirement.shared else 0
    longer_block_bonus = block_size * 2
    faculty_load_penalty = -3 * max(0, faculty_load + block_size - 4)
    clustering_penalty = -2 * subject_load
    scarcity_bonus = max(0, 8 - faculty_flex)
    tail_fill_bonus = 3 if empty_slots <= len(requirement.sections) * 8 else 0
    return (
        section_free_score
        + faculty_available_score
        + continuous_score
        + conflict_penalty
        + shared_bonus
        + longer_block_bonus
        + center_bonus
        + scarcity_bonus
        + tail_fill_bonus
        + section_flex
        + faculty_flex
        + faculty_load_penalty
        + clustering_penalty
    )


def _score_slot_candidate_fast(
    requirement: Requirement,
    faculty_id: str,
    day: str,
    start_period: int,
    block_size: int,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
    year: str,
) -> int:
    """
    Performance-focused scoring:
    - avoids expensive per-candidate metrics (subject_daily_load, empty slot scans, etc.)
    - keeps the spec's spirit: prefer section+faculty freedom and longer blocks
    """
    # Slots are already filtered to be free by the caller, so we treat "free" as boolean.
    section_free = 1
    faculty_free = 1
    # Mirror original heuristic: if block_size is too small for the requirement's
    # minimum consecutive hours, heavily penalize it.
    continuous_score = 3 if block_size >= requirement.min_consecutive_hours else -10

    # Light flex metric to differentiate candidates.
    section_flex = 0
    for p in PERIODS:
        if all(schedules[(year, sec)][day][p] is None for sec in requirement.sections):
            section_flex += 1

    faculty_flex = 0
    allowed_periods = faculty_availability.get(faculty_id, _default_day_availability()).get(day, set(PERIODS))
    busy_slots = faculty_busy.get(faculty_id, set())
    for p in allowed_periods:
        if (day, p) not in busy_slots:
            faculty_flex += 1

    center_bonus = 2 if start_period not in (PERIODS[0], PERIODS[-1]) else 0
    shared_bonus = 2 if requirement.shared else 0

    # Core weights from spec.
    score = 0
    score += 5 * section_free
    score += 5 * faculty_free
    score += continuous_score

    # Cheap differentiators.
    score += section_flex
    score += faculty_flex
    # Prefer scarce faculty availability (approximation of the original solver).
    score += max(0, 8 - faculty_flex)
    score += (block_size * 2)  # prefer longer blocks
    score += center_bonus
    score += shared_bonus
    return int(score)


def _enumerate_slot_candidates(
    requirement: Requirement,
    remaining_hours: int,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
    year: str,
    days_order: list[str],
    periods_order: list[int],
    candidate_limit: int,
) -> list[SlotCandidate]:
    candidates: list[SlotCandidate] = []
    for block_size in _candidate_block_sizes(
        remaining_hours,
        requirement.min_consecutive_hours,
        requirement.max_consecutive_hours,
    ):
        for day in days_order:
            for start_period in periods_order:
                faculty_id = _choose_faculty_for_slot(
                    requirement,
                    day,
                    start_period,
                    block_size,
                    faculty_busy,
                    faculty_availability,
                )
                if not faculty_id:
                    continue
                if not _slot_is_free(
                    requirement.sections,
                    requirement,
                    day,
                    start_period,
                    block_size,
                    schedules,
                    faculty_busy,
                    faculty_availability,
                    year,
                ):
                    continue

                assigned_faculty_ids = _split_faculty_tokens(faculty_id)
                scoring_faculty_id = assigned_faculty_ids[0] if assigned_faculty_ids else faculty_id
                candidates.append(
                    SlotCandidate(
                        day=day,
                        start_period=start_period,
                        block_size=block_size,
                        faculty_id=scoring_faculty_id,
                        faculty_ids=assigned_faculty_ids or ((scoring_faculty_id,) if scoring_faculty_id else ()),
                        score=_score_slot_candidate(
                            requirement,
                            scoring_faculty_id,
                            day,
                            start_period,
                            block_size,
                            schedules,
                            faculty_busy,
                            faculty_availability,
                            year,
                        ),
                    )
                )
    candidates.sort(key=lambda item: (-item.score, -item.block_size, item.day, item.start_period))
    return candidates[:candidate_limit]


def _select_next_requirement(
    requirements: list[Requirement],
    remaining_hours: dict[int, int],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
    year: str,
    days_order: list[str],
    periods_order: list[int],
    candidate_limit: int,
) -> tuple[int | None, list[SlotCandidate]]:
    best_idx: int | None = None
    best_candidates: list[SlotCandidate] = []
    best_key: tuple[int, int, int, int, int, str, str] | None = None

    for req_idx, requirement in enumerate(requirements):
        remaining = remaining_hours.get(req_idx, 0)
        if remaining <= 0 or not requirement.faculty_id:
            continue
        requirement.phase = _determine_requirement_phase(
            requirement.shared,
            requirement.min_consecutive_hours,
            requirement.hours,
            requirement.faculty_options,
            faculty_availability,
        )

    for req_idx, requirement in enumerate(requirements):
        remaining = remaining_hours.get(req_idx, 0)
        if remaining <= 0 or not requirement.faculty_id:
            continue
        candidates = _enumerate_slot_candidates(
            requirement,
            remaining,
            schedules,
            faculty_busy,
            faculty_availability,
            year,
            days_order,
            periods_order,
            candidate_limit,
        )
        key = (
            len(candidates),
            0 if requirement.common_faculty else 1,
            -requirement.min_consecutive_hours,
            -remaining,
            len(DAYS) * len(PERIODS) - _requirement_weekly_capacity(requirement, faculty_availability),
            requirement.subject_id,
            ",".join(requirement.sections),
        )
        if best_key is None or key < best_key:
            best_idx = req_idx
            best_key = key
            best_candidates = candidates
            if len(candidates) == 0:
                break

    return best_idx, best_candidates


def _place_block(
    requirement: Requirement,
    faculty_ids: tuple[str, ...],
    day: str,
    start_period: int,
    block_size: int,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    year: str,
    subject_id_to_name: dict[str, str],
    faculty_id_to_name: dict[str, str],
    session_log: list[dict],
    source: str = "solver",
) -> list[tuple[str, int]]:
    subject_id, subject_name = _resolve_subject_output(requirement.subject_id, subject_id_to_name)
    if not faculty_ids:
        faculty_ids = _split_faculty_tokens(requirement.faculty_id)
    faculty_ids = tuple(_normalize_id_token(fid) for fid in faculty_ids if _normalize_id_token(fid))
    faculty_id, faculty_name = _resolve_faculty_display(faculty_ids, faculty_id_to_name)
    periods = list(range(start_period, start_period + block_size))
    for period in periods:
        for faculty_token in faculty_ids:
            faculty_busy.setdefault(faculty_token, set()).add((day, period))
        for section in requirement.sections:
            schedules[(year, section)][day][period] = {
                "subject": subject_name,
                "subjectName": subject_name,
                "subjectId": subject_id,
                "faculty": faculty_name,
                "facultyName": faculty_name,
                "facultyId": faculty_id,
                "isLab": False,
                "locked": False,
                "venue": "",
                "sharedSections": list(requirement.sections) if len(requirement.sections) > 1 else [],
            }
    # §21: tag source so only file-driven sessions appear in the shared class report
    session_log.append(
        {
            "year": year,
            "subject_id": subject_id,
            "subject_name": subject_name,
            "faculty_id": faculty_id,
            "faculty_name": faculty_name,
            "faculty_ids": list(faculty_ids),
            "faculty_names": [faculty_id_to_name.get(fid, fid) for fid in faculty_ids],
            "sections": list(requirement.sections),
            "day": day,
            "periods": periods,
            "venue": "",
            "isLab": False,
            "shared": len(requirement.sections) > 1,
            "source": source,
        }
    )
    return [(day, period) for period in periods]


def _undo_block(
    requirement: Requirement,
    faculty_ids: tuple[str, ...],
    placements: list[tuple[str, int]],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    year: str,
    session_log: list[dict],
) -> None:
    for day, period in placements:
        for faculty_token in faculty_ids:
            faculty_busy.setdefault(faculty_token, set()).discard((day, period))
        for section in requirement.sections:
            schedules[(year, section)][day][period] = None
    if session_log:
        session_log.pop()


def _infer_failure_reason(
    requirement: Requirement,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
    year: str,
) -> str:
    faculty_has_any_slot = False
    faculty_has_continuous_slot = False
    section_has_any_slot = False

    for day in DAYS:
        for start in PERIODS:
            if _slot_is_free(
                requirement.sections,
                requirement,
                day,
                start,
                1,
                schedules,
                faculty_busy,
                faculty_availability,
                year,
            ):
                faculty_has_any_slot = True
                if len(requirement.sections) > 1:
                    section_has_any_slot = True
                
                if _slot_is_free(
                    requirement.sections,
                    requirement,
                    day,
                    start,
                    min(requirement.hours, max(1, requirement.min_consecutive_hours)),
                    schedules,
                    faculty_busy,
                    faculty_availability,
                    year,
                ):
                    faculty_has_continuous_slot = True
                    section_has_any_slot = True

    if not faculty_has_any_slot:
        return "faculty availability conflict"
    if len(requirement.sections) > 1 and not section_has_any_slot:
        return "shared class constraint"
    if requirement.min_consecutive_hours > 1 and not faculty_has_continuous_slot:
        return "continuous hours constraint"
    return "no free slot"


def _group_issue_records(records: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str, tuple[str, ...], str], dict] = {}
    for record in records:
        sections = tuple(sorted(str(section).strip() for section in record.get("sections", []) if str(section).strip()))
        key = (
            str(record.get("year", "")).strip(),
            str(record.get("subject_id", "")).strip(),
            str(record.get("faculty_id", "")).strip(),
            sections,
            str(record.get("constraint", record.get("detail", ""))).strip(),
        )
        current = grouped.get(key)
        if current is None:
            grouped[key] = {**record, "sections": list(sections), "occurrences": 1}
            continue
        current["occurrences"] = int(current.get("occurrences", 1)) + 1
        if not current.get("detail") and record.get("detail"):
            current["detail"] = record["detail"]

    result: list[dict] = []
    for item in grouped.values():
        occurrences = int(item.pop("occurrences", 1))
        if occurrences > 1:
            base_detail = str(item.get("detail", "")).strip()
            item["detail"] = f"{base_detail} (Grouped {occurrences} similar issue(s))".strip()
        result.append(item)
    result.sort(
        key=lambda row: (
            str(row.get("constraint", "")),
            str(row.get("subject_id", "")),
            ",".join(row.get("sections", [])),
        )
    )
    return result


def _group_sections_by_remaining_capacity(
    requirements: list[Requirement],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    year: str,
) -> list[dict]:
    section_rows: list[dict] = []
    seen_sections: set[str] = set()
    for requirement in requirements:
        for section in requirement.sections:
            if section in seen_sections:
                continue
            seen_sections.add(section)
            remaining_slots = sum(
                1
                for day in DAYS
                for period in PERIODS
                if schedules[(year, section)][day][period] is None
            )
            remaining_hours = sum(req.hours for req in requirements if section in req.sections)
            if remaining_hours > remaining_slots:
                section_rows.append(
                    {
                        "year": year,
                        "sections": [section],
                        "subject_id": "",
                        "faculty_id": "",
                        "constraint": "section capacity constraint",
                        "detail": f"Section {section} requires {remaining_hours} hour(s) but has only {remaining_slots} free slot(s).",
                    }
                )
    return section_rows


def _merge_overlapping_section_groups(
    groups: list[tuple[str, ...]],
) -> list[tuple[str, ...]]:
    """
    Merge overlapping section groups so the same subject is not counted twice
    for a section when shared-class rows overlap (e.g., A,B and B,C).
    """
    components: list[set[str]] = []
    for group in groups:
        current = {sec for sec in group if sec}
        if not current:
            continue
        merged: list[set[str]] = []
        for comp in components:
            if current.intersection(comp):
                current.update(comp)
            else:
                merged.append(comp)
        merged.append(current)
        components = merged
    return [tuple(sorted(comp)) for comp in components if comp]


def _serialize_section_grids(
    year: str,
    sections: list[str],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
) -> dict[str, dict[str, list[dict | None]]]:
    return {
        section: {day: [schedules[(year, section)][day][period] for period in PERIODS] for day in DAYS}
        for section in sections
    }


def _build_faculty_workloads_from_sessions(
    sessions: list[dict],
) -> dict[str, dict[str, list[str | None]]]:
    workloads: dict[str, dict[str, dict[int, str | None]]] = {}
    for session in sessions:
        day = session["day"]
        faculty_names = [str(name).strip() for name in session.get("faculty_names", []) if str(name).strip()]
        faculty_ids = [str(fid).strip() for fid in session.get("faculty_ids", []) if str(fid).strip()]
        if not faculty_names:
            fallback_name = str(session.get("faculty_name", "")).strip()
            if fallback_name:
                faculty_names = [part.strip() for part in fallback_name.split(",") if part.strip()]
        if not faculty_ids:
            fallback_id = str(session.get("faculty_id", "")).strip()
            if fallback_id:
                faculty_ids = [part.strip() for part in fallback_id.split(",") if part.strip()]

        faculty_keys = faculty_names or faculty_ids
        if not faculty_keys:
            continue

        for faculty_key in faculty_keys:
            faculty_workload = workloads.setdefault(faculty_key, {d: {p: None for p in PERIODS} for d in DAYS})
            for period in session["periods"]:
                faculty_workload[day][period] = f"{session['subject_name']} ({','.join(session['sections'])})"
    
    final_workloads: dict[str, dict[str, list[str | None]]] = {}
    for fid, days_data in workloads.items():
        final_workloads[fid] = {day: [days_data[day][period] for period in PERIODS] for day in DAYS}
    return final_workloads


def _workbook_bytes(workbook: Workbook) -> bytes:
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _encode_workbook(file_name: str, workbook: Workbook) -> dict:
    return {
        "fileName": file_name,
        "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "contentBase64": base64.b64encode(_workbook_bytes(workbook)).decode("ascii"),
    }


def _style_range(
    worksheet,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    *,
    alignment: Alignment | None = None,
    border: Border | None = None,
    font: Font | None = None,
) -> None:
    for row in worksheet.iter_rows(
        min_row=start_row,
        max_row=end_row,
        min_col=start_column,
        max_col=end_column,
    ):
        for cell in row:
            if isinstance(cell, MergedCell):
                continue
            if alignment:
                cell.alignment = alignment
            if border:
                cell.border = border
            if font:
                cell.font = font


def _apply_border_sides(
    cell,
    *,
    left: Side | None = None,
    right: Side | None = None,
    top: Side | None = None,
    bottom: Side | None = None,
) -> None:
    current = cell.border
    cell.border = Border(
        left=left or current.left,
        right=right or current.right,
        top=top or current.top,
        bottom=bottom or current.bottom,
    )


def _clear_cell_border(cell) -> None:
    cell.border = Border()


def _apply_merged_range_outline(
    worksheet,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    *,
    border: Border,
) -> None:
    for row_idx in range(start_row, end_row + 1):
        for col_idx in range(start_column, end_column + 1):
            cell = worksheet.cell(row=row_idx, column=col_idx)
            _clear_cell_border(cell)
            _apply_border_sides(
                cell,
                left=border.left if col_idx == start_column else None,
                right=border.right if col_idx == end_column else None,
                top=border.top if row_idx == start_row else None,
                bottom=border.bottom if row_idx == end_row else None,
            )


def _build_subject_legend_for_section(
    section_schedule: dict[str, dict[int, dict | None]],
) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for day in DAYS:
        for period in PERIODS:
            entry = section_schedule[day][period]
            if not entry:
                continue
            subject = str(entry.get("subjectName") or entry.get("subject") or "").strip()
            faculty = str(entry.get("facultyName") or entry.get("faculty") or "").strip()
            if subject and subject not in seen:
                seen[subject] = faculty
    return sorted(seen.items(), key=lambda item: item[0])


def _same_section_entry(left: dict | None, right: dict | None) -> bool:
    if not left or not right:
        return False
    return (
        str(left.get("subjectName") or left.get("subject") or "").strip()
        == str(right.get("subjectName") or right.get("subject") or "").strip()
        and str(left.get("facultyName") or left.get("faculty") or "").strip()
        == str(right.get("facultyName") or right.get("faculty") or "").strip()
        and bool(left.get("isLab")) == bool(right.get("isLab"))
        and ",".join(left.get("sharedSections", []) or [])
        == ",".join(right.get("sharedSections", []) or [])
    )


def _section_cell_text(entry: dict | None) -> str:
    if not entry:
        return ""
    subject = str(entry.get("subjectName") or entry.get("subject") or "").strip()
    venue = str(entry.get("venue", "") or "").strip()
    if venue:
        return f"{subject}\n({venue})"
    return subject


def _merge_section_day_row(
    worksheet,
    row_idx: int,
    section_schedule: dict[str, dict[int, dict | None]],
    day: str,
) -> tuple[bool, bool]:
    display_columns = {1: 2, 2: 3, 3: 5, 4: 6, 5: 8, 6: 9, 7: 10}
    period = 1
    break_overlap = False
    lunch_overlap = False

    while period <= 7:
        current = section_schedule[day][period]
        start_period = period
        end_period = period
        while end_period + 1 <= 7 and _same_section_entry(current, section_schedule[day][end_period + 1]):
            next_period = end_period + 1
            if (end_period == 2 and next_period == 3) or (end_period == 4 and next_period == 5):
                break
            end_period += 1

        start_col = display_columns[start_period]
        end_col = display_columns[end_period]

        if not isinstance(worksheet.cell(row=row_idx, column=start_col), MergedCell):
            worksheet.cell(row=row_idx, column=start_col, value=_section_cell_text(current))
            if end_col > start_col:
                worksheet.merge_cells(
                    start_row=row_idx,
                    start_column=start_col,
                    end_row=row_idx,
                    end_column=end_col,
                )
        period = end_period + 1

    return break_overlap, lunch_overlap


def _normalize_faculty_sheet_name(value: str) -> str:
    invalid = '\\/*?:[]'
    name = "".join("_" if char in invalid else char for char in value).strip()
    return name[:31] or "Faculty"


def _build_faculty_schedule_details(
    sessions: list[dict],
    faculty_id_to_name: dict[str, str],
) -> dict[str, dict[str, list[list[dict] | None]]]:
    workloads: dict[str, dict[str, list[list[dict] | None]]] = {}
    for session in sessions:
        day = str(session.get("day", "")).strip()
        periods = [int(period) for period in session.get("periods", []) if int(period) in PERIODS]
        if day not in DAYS or not periods:
            continue

        sections = ",".join(session.get("sections", []))
        detail = {
            "subject": str(session.get("subject_name", "")).strip() or str(session.get("subject_id", "")).strip(),
            "year": str(session.get("year", "")).strip(),
            "section": sections,
        }

        faculty_names = [str(name).strip() for name in session.get("faculty_names", []) if str(name).strip()]
        faculty_ids = [str(fid).strip() for fid in session.get("faculty_ids", []) if str(fid).strip()]
        if not faculty_names:
            fallback_name = str(session.get("faculty_name", "")).strip()
            if fallback_name:
                faculty_names = [part.strip() for part in fallback_name.split(",") if part.strip()]
        if not faculty_ids:
            fallback_id = str(session.get("faculty_id", "")).strip()
            if fallback_id:
                faculty_ids = [part.strip() for part in fallback_id.split(",") if part.strip()]

        display_names = faculty_names or [faculty_id_to_name.get(fid, fid) for fid in faculty_ids if fid]
        for faculty_name in display_names:
            schedule = workloads.setdefault(
                faculty_name,
                {day_name: [None] * len(PERIODS) for day_name in DAYS},
            )
            for period in periods:
                index = period - 1
                if schedule[day][index] is None:
                    schedule[day][index] = []
                existing = schedule[day][index] or []
                if detail not in existing:
                    existing.append(detail.copy())
                schedule[day][index] = existing
    return workloads


def _faculty_slot_text(entries: list[dict] | None) -> str:
    if not entries:
        return ""
    return "\n\n".join(
        f"{entry['subject']}\n{entry['year']} {entry['section']}".strip()
        for entry in entries
    )


def _same_faculty_slot(left: list[dict] | None, right: list[dict] | None) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return all(left[idx] == right[idx] for idx in range(len(left)))


def _merge_faculty_run(
    worksheet,
    row_idx: int,
    entries: list[list[dict] | None],
    columns: list[int],
) -> None:
    idx = 0
    while idx < len(entries):
        current = entries[idx]
        worksheet.cell(row=row_idx, column=columns[idx], value=_faculty_slot_text(current))
        end = idx
        while end + 1 < len(entries) and _same_faculty_slot(current, entries[end + 1]):
            end += 1
        if end > idx:
            worksheet.merge_cells(
                start_row=row_idx,
                start_column=columns[idx],
                end_row=row_idx,
                end_column=columns[end],
            )
        idx = end + 1


def _build_faculty_legend(schedule: dict[str, list[list[dict] | None]]) -> list[str]:
    labels: set[str] = set()
    for day in DAYS:
        for entries in schedule.get(day, []):
            if not entries:
                continue
            for entry in entries:
                labels.add(f"{entry['year']} {entry['section']} - {entry['subject']}")
    return sorted(labels)


def _apply_formatted_sheet_layout(
    worksheet,
    *,
    legend_row_count: int,
    legend_start_row: int,
    day_start_row: int,
    top_rows: int,
) -> None:
    widths = [7, 16, 16, 11, 16, 16, 11, 16, 16, 16]
    for column_idx, width in enumerate(widths, start=1):
        worksheet.column_dimensions[chr(64 + column_idx)].width = width

    for row_idx in range(1, worksheet.max_row + 1):
        if day_start_row <= row_idx < day_start_row + len(DAYS):
            worksheet.row_dimensions[row_idx].height = 42
        elif row_idx <= top_rows:
            worksheet.row_dimensions[row_idx].height = 22
        elif row_idx > worksheet.max_row - legend_row_count - 2:
            worksheet.row_dimensions[row_idx].height = 22
        else:
            worksheet.row_dimensions[row_idx].height = 20

    _style_range(
        worksheet,
        1,
        worksheet.max_row,
        1,
        10,
        alignment=CENTER_ALIGNMENT,
        border=MEDIUM_BORDER,
    )
    for merged_range in worksheet.merged_cells.ranges:
        anchor = worksheet.cell(row=merged_range.min_row, column=merged_range.min_col)
        anchor.alignment = CENTER_ALIGNMENT
        anchor.border = MEDIUM_BORDER
        _apply_merged_range_outline(
            worksheet,
            merged_range.min_row,
            merged_range.max_row,
            merged_range.min_col,
            merged_range.max_col,
            border=MEDIUM_BORDER,
        )

    if legend_row_count > 0:
        for row_idx in range(legend_start_row, legend_start_row + legend_row_count):
            worksheet.cell(row=row_idx, column=1).alignment = LEFT_ALIGNMENT
            worksheet.cell(row=row_idx, column=6).alignment = LEFT_ALIGNMENT


def _build_section_timetables_workbook_from_schedule_map(
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    timetable_metadata: dict[str, Any] | None = None,
) -> Workbook:
    workbook = Workbook()
    workbook.remove(workbook.active)
    metadata = _resolve_timetable_metadata(timetable_metadata)
    for year, section in sorted(schedules.keys(), key=lambda item: (item[0], item[1])):
        worksheet = workbook.create_sheet(title=f"{year}_{section}"[:31])
        worksheet.append([ACADEMIC_METADATA["college"]] + [""] * 9)
        worksheet.append(["(AUTONOMOUS)"] + [""] * 9)
        worksheet.append([ACADEMIC_METADATA["department"]] + [""] * 9)
        worksheet.append([f"ACADEMIC YEAR : {metadata['academicYear']} {metadata['semester']}"] + [""] * 9)
        worksheet.append([_class_title(year, section, metadata["semester"])] + [""] * 9)
        worksheet.append(["Room No :"] + [""] * 4 + [f"With effect from : {metadata['withEffectFromDisplay']}"] + [""] * 4)
        worksheet.append(["DAY", "1", "2", "", "3", "4", "", "5", "6", "7"])
        worksheet.append(["", "9.10-10.00", "10.00-10.50", "10.50-11.00", "11.00-11.50", "11.50-12.40", "12.40-1.30", "1.30-2.20", "2.20-3.10", "3.10-4.00"])

        day_start_row = 9
        section_schedule = schedules[(year, section)]
        break_overlap_rows: list[int] = []
        lunch_overlap_rows: list[int] = []
        for offset, day in enumerate(DAYS):
            row_idx = day_start_row + offset
            worksheet.cell(row=row_idx, column=1, value=DAY_SHORT_LABELS[day])
            overlaps_break, overlaps_lunch = _merge_section_day_row(worksheet, row_idx, section_schedule, day)
            if overlaps_break:
                break_overlap_rows.append(row_idx)
            if overlaps_lunch:
                lunch_overlap_rows.append(row_idx)

        worksheet.append([""] * 10)
        legend_separator_row = worksheet.max_row
        legend = _build_subject_legend_for_section(section_schedule)
        for idx in range(0, len(legend), 2):
            left = legend[idx]
            right = legend[idx + 1] if idx + 1 < len(legend) else None
            worksheet.append(
                [f"{left[0]} : {left[1]}" if left else ""]
                + [""] * 4
                + [f"{right[0]} : {right[1]}" if right else ""]
                + [""] * 4
            )
        worksheet.append([""] * 10)
        signature_separator_row = worksheet.max_row
        worksheet.append(["HEAD OF THE DEPARTMENT"] + [""] * 4 + ["PRINCIPAL"] + [""] * 4)

        worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=10)
        worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=10)
        worksheet.merge_cells(start_row=3, start_column=1, end_row=3, end_column=10)
        worksheet.merge_cells(start_row=4, start_column=1, end_row=4, end_column=10)
        worksheet.merge_cells(start_row=5, start_column=1, end_row=5, end_column=10)
        worksheet.merge_cells(start_row=6, start_column=1, end_row=6, end_column=5)
        worksheet.merge_cells(start_row=6, start_column=6, end_row=6, end_column=10)
        worksheet.merge_cells(start_row=7, start_column=1, end_row=8, end_column=1)

        def merge_vertical_marker(column: int, label: str, blocked_rows: list[int]) -> None:
            all_rows = [day_start_row + i for i in range(len(DAYS))]
            segments: list[tuple[int, int]] = []
            segment_start = None
            for r in all_rows:
                if r in blocked_rows:
                    if segment_start is not None:
                        segments.append((segment_start, r - 1))
                        segment_start = None
                else:
                    if segment_start is None:
                        segment_start = r
            if segment_start is not None:
                segments.append((segment_start, all_rows[-1]))

            for start, end in segments:
                worksheet.merge_cells(start_row=start, start_column=column, end_row=end, end_column=column)
                worksheet.cell(row=start, column=column, value=label)
                worksheet.cell(row=start, column=column).font = BOLD_FONT

        merge_vertical_marker(4, "BREAK", break_overlap_rows)
        merge_vertical_marker(7, "LUNCH", lunch_overlap_rows)

        worksheet.merge_cells(start_row=legend_separator_row, start_column=1, end_row=legend_separator_row, end_column=10)
        legend_start_row = day_start_row + len(DAYS) + 1
        for legend_row in range(legend_start_row, legend_start_row + len(legend) // 2 + len(legend) % 2):
            worksheet.merge_cells(start_row=legend_row, start_column=1, end_row=legend_row, end_column=5)
            worksheet.merge_cells(start_row=legend_row, start_column=6, end_row=legend_row, end_column=10)
        worksheet.merge_cells(start_row=signature_separator_row, start_column=1, end_row=signature_separator_row, end_column=5)
        worksheet.merge_cells(start_row=signature_separator_row, start_column=6, end_row=signature_separator_row, end_column=10)
        worksheet.merge_cells(start_row=worksheet.max_row, start_column=1, end_row=worksheet.max_row, end_column=5)
        worksheet.merge_cells(start_row=worksheet.max_row, start_column=6, end_row=worksheet.max_row, end_column=10)

        _apply_formatted_sheet_layout(
            worksheet,
            legend_row_count=(len(legend) + 1) // 2,
            legend_start_row=legend_start_row,
            day_start_row=day_start_row,
            top_rows=6,
        )
    return workbook


def _build_section_timetables_workbook(
    year: str,
    sections: list[str],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    timetable_metadata: dict[str, Any] | None = None,
) -> Workbook:
    filtered = {
        (year, section): schedules[(year, section)]
        for section in sections
        if (year, section) in schedules
    }
    return _build_section_timetables_workbook_from_schedule_map(filtered, timetable_metadata)


def _build_faculty_workload_workbook_from_details(
    faculty_schedules: dict[str, dict[str, list[list[dict] | None]]],
    timetable_metadata: dict[str, Any] | None = None,
) -> Workbook:
    workbook = Workbook()
    workbook.remove(workbook.active)
    if not faculty_schedules:
        return workbook
    metadata = _resolve_timetable_metadata(timetable_metadata)

    for faculty_name, schedule in sorted(faculty_schedules.items()):
        worksheet = workbook.create_sheet(title=_normalize_faculty_sheet_name(faculty_name))
        worksheet.append([ACADEMIC_METADATA["college"]] + [""] * 9)
        worksheet.append(["(AUTONOMOUS)"] + [""] * 9)
        worksheet.append([ACADEMIC_METADATA["department"]] + [""] * 9)
        worksheet.append([f"ACADEMIC YEAR : {metadata['academicYear']} {metadata['semester']}"] + [""] * 9)
        worksheet.append([f"FACULTY WORKLOAD : {faculty_name}"] + [""] * 9)
        worksheet.append(["DAY", "1", "2", "", "3", "4", "", "5", "6", "7"])
        worksheet.append(["", "9.10-10.00", "10.00-10.50", "10.50-11.00", "11.00-11.50", "11.50-12.40", "12.40-1.30", "1.30-2.20", "2.20-3.10", "3.10-4.00"])

        day_start_row = 8
        for offset, day in enumerate(DAYS):
            row_idx = day_start_row + offset
            worksheet.cell(row=row_idx, column=1, value=DAY_SHORT_LABELS[day])
            worksheet.cell(row=row_idx, column=4, value="BREAK" if offset == 0 else "")
            worksheet.cell(row=row_idx, column=7, value="LUNCH" if offset == 0 else "")
            _merge_faculty_run(worksheet, row_idx, [schedule[day][0], schedule[day][1]], [2, 3])
            _merge_faculty_run(worksheet, row_idx, [schedule[day][2], schedule[day][3]], [5, 6])
            _merge_faculty_run(worksheet, row_idx, [schedule[day][4], schedule[day][5], schedule[day][6]], [8, 9, 10])

        worksheet.append([""] * 10)
        legend_separator_row = worksheet.max_row
        legend = _build_faculty_legend(schedule)
        for idx in range(0, len(legend), 2):
            left = legend[idx]
            right = legend[idx + 1] if idx + 1 < len(legend) else ""
            worksheet.append([left] + [""] * 4 + [right] + [""] * 4)
        worksheet.append([""] * 10)
        signature_separator_row = worksheet.max_row
        worksheet.append(["HEAD OF THE DEPARTMENT"] + [""] * 4 + ["PRINCIPAL"] + [""] * 4)

        worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=10)
        worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=10)
        worksheet.merge_cells(start_row=3, start_column=1, end_row=3, end_column=10)
        worksheet.merge_cells(start_row=4, start_column=1, end_row=4, end_column=10)
        worksheet.merge_cells(start_row=5, start_column=1, end_row=5, end_column=10)
        worksheet.merge_cells(start_row=6, start_column=1, end_row=7, end_column=1)
        worksheet.merge_cells(start_row=8, start_column=4, end_row=13, end_column=4)
        worksheet.merge_cells(start_row=8, start_column=7, end_row=13, end_column=7)

        worksheet.merge_cells(start_row=legend_separator_row, start_column=1, end_row=legend_separator_row, end_column=10)
        legend_start_row = day_start_row + len(DAYS) + 1
        for legend_row in range(legend_start_row, legend_start_row + len(legend) // 2 + len(legend) % 2):
            worksheet.merge_cells(start_row=legend_row, start_column=1, end_row=legend_row, end_column=5)
            worksheet.merge_cells(start_row=legend_row, start_column=6, end_row=legend_row, end_column=10)
        worksheet.merge_cells(start_row=signature_separator_row, start_column=1, end_row=signature_separator_row, end_column=5)
        worksheet.merge_cells(start_row=signature_separator_row, start_column=6, end_row=signature_separator_row, end_column=10)
        worksheet.merge_cells(start_row=worksheet.max_row, start_column=1, end_row=worksheet.max_row, end_column=5)
        worksheet.merge_cells(start_row=worksheet.max_row, start_column=6, end_row=worksheet.max_row, end_column=10)

        _apply_formatted_sheet_layout(
            worksheet,
            legend_row_count=(len(legend) + 1) // 2,
            legend_start_row=legend_start_row,
            day_start_row=day_start_row,
            top_rows=5,
        )
    return workbook


def _build_faculty_workload_workbook(
    sessions: list[dict],
    faculty_id_to_name: dict[str, str],
    timetable_metadata: dict[str, Any] | None = None,
) -> Workbook:
    faculty_schedules = _build_faculty_schedule_details(sessions, faculty_id_to_name)
    return _build_faculty_workload_workbook_from_details(faculty_schedules, timetable_metadata)


def _build_faculty_workload_workbook_from_saved_workloads(
    faculty_workloads: dict[str, dict[str, list[str | None]]],
    timetable_metadata: dict[str, Any] | None = None,
) -> Workbook:
    workbook = Workbook()
    workbook.remove(workbook.active)
    if not faculty_workloads:
        return workbook
    metadata = _resolve_timetable_metadata(timetable_metadata)

    for faculty_name, schedule in sorted(faculty_workloads.items()):
        worksheet = workbook.create_sheet(title=_normalize_faculty_sheet_name(faculty_name))
        worksheet.append([ACADEMIC_METADATA["college"]] + [""] * 9)
        worksheet.append(["(AUTONOMOUS)"] + [""] * 9)
        worksheet.append([ACADEMIC_METADATA["department"]] + [""] * 9)
        worksheet.append([f"ACADEMIC YEAR : {metadata['academicYear']} {metadata['semester']}"] + [""] * 9)
        worksheet.append([f"FACULTY WORKLOAD : {faculty_name}"] + [""] * 9)
        worksheet.append(["DAY", "1", "2", "", "3", "4", "", "5", "6", "7"])
        worksheet.append(["", "9.10-10.00", "10.00-10.50", "10.50-11.00", "11.00-11.50", "11.50-12.40", "12.40-1.30", "1.30-2.20", "2.20-3.10", "3.10-4.00"])

        legend_values: set[str] = set()
        day_start_row = 8
        for offset, day in enumerate(DAYS):
            row_idx = day_start_row + offset
            day_values = list(schedule.get(day, [None] * len(PERIODS)))
            worksheet.cell(row=row_idx, column=1, value=DAY_SHORT_LABELS[day])
            worksheet.cell(row=row_idx, column=4, value="BREAK" if offset == 0 else "")
            worksheet.cell(row=row_idx, column=7, value="LUNCH" if offset == 0 else "")
            for value in day_values:
                if value:
                    legend_values.add(str(value).replace("\n", " ").strip())
            # Populate/merge actual visible ranges using normalized saved strings.
            for entries, columns in (
                ([day_values[0], day_values[1]], [2, 3]),
                ([day_values[2], day_values[3]], [5, 6]),
                ([day_values[4], day_values[5], day_values[6]], [8, 9, 10]),
            ):
                idx = 0
                while idx < len(entries):
                    current = str(entries[idx] or "").strip()
                    worksheet.cell(row=row_idx, column=columns[idx], value=current)
                    end = idx
                    while end + 1 < len(entries) and current and current == str(entries[end + 1] or "").strip():
                        end += 1
                    if end > idx:
                        worksheet.merge_cells(
                            start_row=row_idx,
                            start_column=columns[idx],
                            end_row=row_idx,
                            end_column=columns[end],
                        )
                    idx = end + 1

        worksheet.append([""] * 10)
        legend_separator_row = worksheet.max_row
        legend = sorted(legend_values)
        for idx in range(0, len(legend), 2):
            left = legend[idx]
            right = legend[idx + 1] if idx + 1 < len(legend) else ""
            worksheet.append([left] + [""] * 4 + [right] + [""] * 4)
        worksheet.append([""] * 10)
        signature_separator_row = worksheet.max_row
        worksheet.append(["HEAD OF THE DEPARTMENT"] + [""] * 4 + ["PRINCIPAL"] + [""] * 4)

        worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=10)
        worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=10)
        worksheet.merge_cells(start_row=3, start_column=1, end_row=3, end_column=10)
        worksheet.merge_cells(start_row=4, start_column=1, end_row=4, end_column=10)
        worksheet.merge_cells(start_row=5, start_column=1, end_row=5, end_column=10)
        worksheet.merge_cells(start_row=6, start_column=1, end_row=7, end_column=1)
        worksheet.merge_cells(start_row=8, start_column=4, end_row=13, end_column=4)
        worksheet.merge_cells(start_row=8, start_column=7, end_row=13, end_column=7)

        worksheet.merge_cells(start_row=legend_separator_row, start_column=1, end_row=legend_separator_row, end_column=10)
        legend_start_row = day_start_row + len(DAYS) + 1
        for legend_row in range(legend_start_row, legend_start_row + len(legend) // 2 + len(legend) % 2):
            worksheet.merge_cells(start_row=legend_row, start_column=1, end_row=legend_row, end_column=5)
            worksheet.merge_cells(start_row=legend_row, start_column=6, end_row=legend_row, end_column=10)
        worksheet.merge_cells(start_row=signature_separator_row, start_column=1, end_row=signature_separator_row, end_column=5)
        worksheet.merge_cells(start_row=signature_separator_row, start_column=6, end_row=signature_separator_row, end_column=10)
        worksheet.merge_cells(start_row=worksheet.max_row, start_column=1, end_row=worksheet.max_row, end_column=5)
        worksheet.merge_cells(start_row=worksheet.max_row, start_column=6, end_row=worksheet.max_row, end_column=10)

        _apply_formatted_sheet_layout(
            worksheet,
            legend_row_count=(len(legend) + 1) // 2,
            legend_start_row=legend_start_row,
            day_start_row=day_start_row,
            top_rows=5,
        )
    return workbook


def _build_faculty_schedule_details_from_section_grids(
    section_grids: dict[tuple[str, str], dict[str, list[dict | None]]],
) -> dict[str, dict[str, list[list[dict] | None]]]:
    workloads: dict[str, dict[str, list[list[dict] | None]]] = {}
    for (year, section), grid in section_grids.items():
        for day in DAYS:
            slots = list(grid.get(day, []))
            for idx, cell in enumerate(slots[: len(PERIODS)]):
                if not isinstance(cell, dict):
                    continue
                faculty_name = str(cell.get("facultyName") or cell.get("faculty") or "").strip()
                subject_name = str(cell.get("subjectName") or cell.get("subject") or "").strip()
                if not faculty_name or not subject_name:
                    continue
                sections = cell.get("sharedSections") or []
                section_label = ",".join(str(item).strip() for item in sections if str(item).strip()) or section
                detail = {
                    "subject": subject_name,
                    "year": year,
                    "section": section_label,
                }
                schedule = workloads.setdefault(
                    faculty_name,
                    {day_name: [None] * len(PERIODS) for day_name in DAYS},
                )
                if schedule[day][idx] is None:
                    schedule[day][idx] = []
                existing = schedule[day][idx] or []
                if detail not in existing:
                    existing.append(detail)
                schedule[day][idx] = existing
    return workloads


def _build_shared_classes_workbook(shared_sessions: list[dict]) -> Workbook:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "SharedClasses"
    worksheet.append(["YEAR", "SUBJECT", "FACULTY", "SECTIONS", "DAY", "PERIODS"])
    for session in shared_sessions:
        worksheet.append(
            [
                session.get("year", ""),
                session.get("subject_name", "") or session.get("subject_id", ""),
                session.get("faculty_name", "") or session.get("faculty_id", ""),
                ",".join(session.get("sections", [])),
                session.get("day", ""),
                ",".join(str(period) for period in session.get("periods", [])),
            ]
        )
    return workbook


def _build_constraint_report_workbook(violations: list[dict], unscheduled: list[dict]) -> Workbook:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ConstraintViolations"
    worksheet.append(["YEAR", "SECTIONS", "SUBJECT", "FACULTY", "CONSTRAINT", "DETAIL"])
    for violation in violations:
        worksheet.append(
            [
                violation.get("year", ""),
                ",".join(violation.get("sections", [])),
                violation.get("subject_name", "") or violation.get("subject_id", ""),
                violation.get("faculty_name", "") or violation.get("faculty_id", ""),
                violation.get("constraint", ""),
                violation.get("detail", ""),
            ]
        )
    for item in unscheduled:
        worksheet.append(
            [
                item.get("year", ""),
                ",".join(item.get("sections", [])),
                item.get("subject_name", "") or item.get("subject_id", ""),
                item.get("faculty_name", "") or item.get("faculty_id", ""),
                "unscheduled subject",
                item.get("detail", ""),
            ]
        )
    return workbook


def generate_timetable(
    request_data: GenerateTimetableRequest,
    store: MemoryStore,
    precheck_only: bool = False,
) -> dict:
    request_data.year = normalize_year(request_data.year)
    year = request_data.year
    timetable_metadata = request_data.timetableMetadata.model_dump()

    main_payload = store.get_scoped_mapping("main_timetable_config", "global")
    lab_payload = store.get_scoped_mapping("lab_timetable_config", "global")
    shared_payload = store.get_scoped_mapping("shared_classes", "global")

    max_period = 7
    capacity_per_section = 42

    # Re-normalize year and faculty id map
    faculty_id_to_name = _build_faculty_maps(request_data, store)
    # Strip .0 from numeric faculty IDs
    faculty_id_to_name = {
        (k[:-2] if k.endswith(".0") else k): v
        for k, v in faculty_id_to_name.items()
    }

    subject_id_to_name, compulsory_continuous = _build_subject_maps(request_data, store)

    all_main_rows = list(main_payload.get("rows", []) if main_payload else [])
    all_lab_rows = list(lab_payload.get("rows", []) if lab_payload else [])
    raw_main_rows = [
        row
        for row in all_main_rows
        if normalize_year(str(row.get("year", ""))) == year
    ]
    raw_lab_rows = [
        row
        for row in all_lab_rows
        if normalize_year(str(row.get("year", ""))) == year
    ]

    for entry in request_data.manualEntries:
        entry_year = normalize_year(entry.year)
        if entry_year != year:
            continue
        fid = ",".join(
            _canonicalize_faculty_token(token, faculty_id_to_name)
            for token in _split_faculty_tokens(str(entry.facultyId))
            if _canonicalize_faculty_token(token, faculty_id_to_name)
        )
        subject_token = _normalize_id_token(entry.subjectId)
        
        raw_main_rows.append(
            {
                "year": entry_year,
                "section": str(entry.section).strip(),
                "subject_id": subject_token,
                "faculty_id": fid,
                "hours": int(entry.noOfHours),
                "continuous_hours": int(entry.continuousHours or 1),
            }
        )
        all_main_rows.append(raw_main_rows[-1])
        if entry.compulsoryContinuousHours:
            compulsory_continuous[subject_token] = max(1, int(entry.compulsoryContinuousHours))

    for lab in request_data.manualLabEntries:
        if normalize_year(lab.year) != year:
            continue
        raw_lab_rows.append(
            {
                "year": year,
                "section": str(lab.section).strip(),
                "subject_id": _normalize_id_token(lab.subjectId),
                "day": int(lab.day),
                "hours": [int(hour) for hour in lab.hours],
                "venue": str(lab.venue).strip(),
            }
        )
        all_lab_rows.append(raw_lab_rows[-1])

    if not raw_main_rows:
        raise HTTPException(status_code=400, detail="No configurable sections found for the specified year.")

    section_total_hours: dict[str, int] = {}
    main_rows_by_section_subject: dict[tuple[str, str], dict] = {}
    section_subject_faculty: dict[tuple[str, str], str] = {}
    for row in raw_main_rows:
        section = str(row.get("section", "")).strip()
        subject_id = _normalize_id_token(row.get("subject_id", ""))
        faculty_id = ",".join(
            _canonicalize_faculty_token(token, faculty_id_to_name)
            for token in _split_faculty_tokens(str(row.get("faculty_id", "")))
            if _canonicalize_faculty_token(token, faculty_id_to_name)
        )
            
        hours = int(row.get("hours", 0) or 0)
        continuous_hours = max(1, int(row.get("continuous_hours", 1) or 1))
        if not section or not subject_id:
            continue
        section_total_hours[section] = section_total_hours.get(section, 0) + hours
        max_consecutive_hours = max(1, continuous_hours)
        min_consecutive_hours = max(1, compulsory_continuous.get(subject_id, 1))
        key = (section, subject_id)
        if key not in main_rows_by_section_subject:
            main_rows_by_section_subject[key] = {
                "section": section,
                "subject_id": subject_id,
                "faculty_id": faculty_id,
                "hours": 0,
                "min_consecutive_hours": min_consecutive_hours,
                "max_consecutive_hours": max_consecutive_hours,
            }
        main_rows_by_section_subject[key]["hours"] += hours
        main_rows_by_section_subject[key]["min_consecutive_hours"] = max(
            main_rows_by_section_subject[key]["min_consecutive_hours"], min_consecutive_hours
        )
        main_rows_by_section_subject[key]["max_consecutive_hours"] = min(
            main_rows_by_section_subject[key]["max_consecutive_hours"], max_consecutive_hours
        )
        section_subject_faculty[key] = faculty_id

    validation_errors = []
    for section in sorted(section_total_hours):
        total = section_total_hours[section]
        if total != capacity_per_section:
            validation_errors.append(
                {
                    "year": year,
                    "section": section,
                    "hours": total,
                    "expected": capacity_per_section,
                    "detail": f"Section {section} needs exactly {capacity_per_section} hours but has {total} hour(s) configured.",
                }
            )
    all_sections = sorted(section_total_hours)
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]] = {
        (year, section): {day: {period: None for period in PERIODS} for day in DAYS} for section in all_sections
    }

    all_faculties = {
        token
    for item in main_rows_by_section_subject.values()
        for token in _split_faculty_tokens(str(item.get("faculty_id", "")).strip())
        if token
    }
    faculty_availability = _build_faculty_availability(request_data, store, all_faculties, faculty_id_to_name)
    prior_timetable_ids = [
        str(timetable_id).strip()
        for timetable_id in request_data.priorTimetableIds
        if str(timetable_id).strip()
    ]
    if not prior_timetable_ids:
        prior_timetable_ids = _latest_timetable_ids_by_year(store, exclude_year=year)
    global_lab_busy = _build_global_lab_occupancy(
        all_main_rows,
        all_lab_rows,
        year,
        faculty_id_to_name,
        faculty_availability,
    )
    prior_faculty_busy = _build_prior_faculty_occupancy(prior_timetable_ids, store, faculty_id_to_name)
    faculty_busy: dict[str, set[tuple[str, int]]] = {
        faculty_id: slots.copy() for faculty_id, slots in prior_faculty_busy.items()
    }
    for faculty_id, slots in global_lab_busy.items():
        faculty_busy.setdefault(faculty_id, set()).update(slots)
    session_log: list[dict] = []
    constraint_violations: list[dict] = []
    lab_assigned_hours: dict[tuple[str, str], int] = {}
    locked_hours_by_section: dict[str, int] = {}

    for item in validation_errors:
        constraint_violations.append(
            {
                "year": item.get("year", year),
                "sections": [str(item.get("section", "")).strip()] if str(item.get("section", "")).strip() else [],
                "subject_id": "",
                "faculty_id": "",
                "constraint": "section capacity constraint",
                "detail": str(item.get("detail", "")).strip()
                or f"Section totals should be {capacity_per_section} hours.",
            }
        )

    for row in sorted(main_rows_by_section_subject.values(), key=lambda item: (item["section"], item["subject_id"])):
        if int(row["min_consecutive_hours"]) <= int(row["max_consecutive_hours"]):
            continue
        constraint_violations.append(
            {
                "year": year,
                "sections": [str(row.get("section", "")).strip()] if str(row.get("section", "")).strip() else [],
                "subject_id": str(row.get("subject_id", "")).strip(),
                "faculty_id": str(row.get("faculty_id", "")).strip(),
                "constraint": "continuous hours constraint",
                "detail": (
                    f"Subject {row['subject_id']} in section {row['section']} requires at least "
                    f"{row['min_consecutive_hours']} consecutive hour(s), but the main config allows only "
                    f"{row['max_consecutive_hours']}."
                ),
            }
        )

    def _resolve_shared_sections(raw_sections: list | tuple | str | int | None, sections_count: int | None = None) -> tuple[str, ...]:
        """
        Accept either:
        - explicit section names list (e.g. ["C1","C2"] or ["C1, C2"])
        - a single numeric value meaning section count (e.g. "3")
        - a separate sections_count field from upload normalization
        """
        if sections_count is not None and sections_count > 0:
            return tuple(all_sections[: sections_count])

        values: list[str] = []
        if raw_sections is None:
            return ()
        if isinstance(raw_sections, (list, tuple)):
            for item in raw_sections:
                text = str(item).strip()
                if not text:
                    continue
                # Allow "C1, C2" inside one cell item.
                values.extend([part.strip() for part in text.split(",") if part.strip()])
        else:
            values.extend([part.strip() for part in str(raw_sections).split(",") if part.strip()])

        if not values:
            return ()

        # If only one numeric token is provided, treat it as section count.
        if len(values) == 1 and values[0].isdigit():
            count = int(values[0])
            if count <= 0:
                return ()
            return tuple(all_sections[:count])

        return tuple(sorted({value for value in values if value}))

    shared_constraints: dict[str, list[tuple[str, ...]]] = {}
    if shared_payload:
        for row in shared_payload.get("rows", []):
            if normalize_year(str(row.get("year", ""))) != year:
                continue
            subject_id = _normalize_id_token(row.get("subject", row.get("subject_id", "")))
            sections = _resolve_shared_sections(
                row.get("sections", []),
                int(row.get("sections_count", 0) or 0) if str(row.get("sections_count", "")).strip() else None,
            )
            if subject_id and sections:
                shared_constraints.setdefault(subject_id, []).append(sections)

    for shared in request_data.sharedClasses:
        if normalize_year(shared.year) != year:
            continue
        subject_id = _normalize_id_token(shared.subject)
        sections = _resolve_shared_sections(shared.sections)
        if subject_id and sections:
            shared_constraints.setdefault(subject_id, []).append(sections)

    sorted_lab_rows = sorted(
        raw_lab_rows,
        key=lambda row: (
            int(row.get("day", 0) or 0),
            tuple(sorted(int(period) for period in row.get("hours", []) if int(period) in PERIODS)),
            str(row.get("subject_id", "")).strip(),
            str(row.get("section", "")).strip(),
        ),
    )
    shared_session_registry: dict[tuple[str, str, str, str, tuple[int, ...]], list[str]] = {}
    faculty_slot_sessions: dict[str, dict[tuple[str, int], tuple[str, str, str, str, tuple[int, ...]]]] = {}
    lab_groups: dict[tuple[str, str, str, tuple[int, ...]], dict] = {}

    for row in sorted_lab_rows:
        section = str(row.get("section", "")).strip()
        subject_id = _normalize_id_token(row.get("subject_id", ""))
        explicit_sections = [str(item).strip() for item in row.get("sections", []) if str(item).strip()]
        sections = sorted(set(explicit_sections or ([section] if section else [])))
        faculty_id = section_subject_faculty.get((section, subject_id), "")
        day = _normalize_day(int(row.get("day", 0) or 0))
        periods = tuple(sorted(int(period) for period in row.get("hours", []) if int(period) in PERIODS))
        
        # Explicit validation for out-of-range periods
        raw_periods = [int(p) for p in row.get("hours", []) if str(p).isdigit()]
        invalid_periods = [p for p in raw_periods if p not in PERIODS]
        if invalid_periods:
            constraint_violations.append(
                {
                    "year": year,
                    "sections": sections or ([section] if section else []),
                    "subject_id": subject_id,
                    "faculty_id": faculty_id,
                    "constraint": "invalid lab configuration",
                    "detail": f"Lab timetable references invalid periods: {invalid_periods}. Only periods 1-7 are allowed.",
                }
            )
            continue
        venue = str(row.get("venue", "")).strip()
        if not sections or any(sec not in all_sections for sec in sections):
            invalid_sections = [sec for sec in sections if sec not in all_sections] or [section]
            constraint_violations.append(
                {
                    "year": year,
                    "sections": invalid_sections,
                    "subject_id": subject_id,
                    "faculty_id": faculty_id,
                    "constraint": "invalid lab configuration",
                    "detail": "Lab timetable references a section that is missing from the main config file.",
                }
            )
            continue
        if not day or not periods:
            constraint_violations.append(
                {
                    "year": year,
                    "sections": sections or [section],
                    "subject_id": subject_id,
                    "faculty_id": faculty_id,
                    "constraint": "invalid lab configuration",
                    "detail": "Lab entry has an invalid day or periods value.",
                }
            )
            continue
        group_key = (faculty_id, subject_id, day, periods)
        current_group = lab_groups.setdefault(
            group_key,
            {
                "sections": set(),
                "venue": venue,
                "source_rows": [],
            },
        )
        current_group["sections"].update(sections)
        current_group["source_rows"].append(row)
        if venue and not current_group["venue"]:
            current_group["venue"] = venue

    for (faculty_id, subject_id, day, periods), group in sorted(
        lab_groups.items(),
        key=lambda item: (
            item[0][2],
            item[0][3],
            item[0][1],
            ",".join(sorted(item[1]["sections"])),
        ),
    ):
        sections = sorted(group["sections"])
        venue = str(group.get("venue", "")).strip()
        subject_id_resolved, subject_name = _resolve_subject_output(subject_id, subject_id_to_name)
        faculty_options_for_lab = _resolve_faculty_pool(faculty_id, faculty_id_to_name, faculty_availability)
        selected_faculty = _pick_best_faculty_option_for_locked_session(
            faculty_options_for_lab,
            day,
            periods,
            faculty_busy,
            faculty_availability,
        )
        if selected_faculty:
            faculty_ids_resolved = (selected_faculty,)
        else:
            fallback_tokens = _split_faculty_tokens(faculty_id)
            faculty_ids_resolved = (fallback_tokens[0],) if fallback_tokens else ()
        faculty_id_resolved, faculty_name = _resolve_faculty_display(faculty_ids_resolved, faculty_id_to_name)
        session_key = (year, subject_id_resolved, faculty_id_resolved, day, periods)
        placed_sections: set[str] = set()
        placed_periods: list[int] = []
        for period in periods:
            period_sections: list[str] = []
            for section in sections:
                # Keep section totals solvable: lock only lab hours that are configured
                # for this exact section+subject in main timetable config.
                main_key = (section, subject_id)
                main_row = main_rows_by_section_subject.get(main_key)
                if not main_row:
                    # Ignore lab rows that don't exist in the main config scope.
                    continue
                configured_subject_hours = int(main_row.get("hours", 0) or 0)
                already_locked_for_subject = lab_assigned_hours.get((section, subject_id), 0)
                if configured_subject_hours > 0 and already_locked_for_subject >= configured_subject_hours:
                    # Ignore excess lab slots beyond configured weekly hours.
                    continue

                if schedules[(year, section)][day][period] is not None:
                    constraint_violations.append(
                        {
                            "year": year,
                            "sections": [section],
                            "subject_id": subject_id,
                            "faculty_id": faculty_id,
                            "constraint": "lab slot overlap",
                            "detail": f"Lab timetable overlap at {day} period {period} for section {section}.",
                        }
                    )
                    continue
                schedules[(year, section)][day][period] = {
                    "subject": subject_name,
                    "subjectName": subject_name,
                    "subjectId": subject_id_resolved,
                    "faculty": faculty_name,
                    "facultyName": faculty_name,
                    "facultyId": faculty_id_resolved,
                    "isLab": True,
                    "locked": True,
                    "venue": venue,
                    "sharedSections": sections if len(sections) > 1 else [],
                }
                lab_assigned_hours[(section, subject_id)] = lab_assigned_hours.get((section, subject_id), 0) + 1
                locked_hours_by_section[section] = locked_hours_by_section.get(section, 0) + 1
                period_sections.append(section)
                placed_sections.add(section)
            if not period_sections:
                continue
            placed_periods.append(period)
            for faculty_token in faculty_ids_resolved:
                if period not in faculty_availability.get(
                    faculty_token, {day_name: set(PERIODS) for day_name in DAYS}
                ).get(day, set(PERIODS)):
                    constraint_violations.append(
                        {
                            "year": year,
                            "sections": period_sections,
                            "subject_id": subject_id,
                            "faculty_id": faculty_token,
                            "constraint": "faculty availability conflict",
                            "detail": f"Locked lab on {day} period {period} is outside allowed faculty availability.",
                        }
                    )
                existing_session = faculty_slot_sessions.setdefault(faculty_token, {}).get((day, period))
                if existing_session and existing_session != session_key:
                    # Locked lab rows are treated as authoritative input from file.
                    # Keep placement stable and avoid surfacing this as a hard violation.
                    pass
                faculty_busy.setdefault(faculty_token, set()).add((day, period))
                faculty_slot_sessions.setdefault(faculty_token, {})[(day, period)] = session_key

        if not placed_periods:
            continue
        shared_session_registry[session_key] = sorted(placed_sections)

        # §21: lab entries are always file-driven; tag source = "lab"
        session_log.append(
            {
                "year": year,
                "subject_id": subject_id_resolved,
                "subject_name": subject_name,
                "faculty_id": faculty_id_resolved,
                "faculty_name": faculty_name,
                "faculty_ids": list(faculty_ids_resolved),
                "faculty_names": [faculty_id_to_name.get(fid, fid) for fid in faculty_ids_resolved],
                "sections": sorted(placed_sections),
                "day": day,
                "periods": placed_periods,
                "venue": venue,
                "isLab": True,
                "shared": len(placed_sections) > 1,
                "source": "lab",
            }
        )

    if request_data.labsOnly:
        all_grids = _serialize_section_grids(year, all_sections, schedules)
        faculty_workloads = _build_faculty_workloads_from_sessions(session_log)
        timetable_id = store.next_timetable_id()
        selected_section = request_data.section if request_data.section in all_grids else all_sections[0]
        store.save_timetable(
            timetable_id,
            {
                "id": timetable_id,
                "year": year,
                "section": selected_section,
                "grid": all_grids.get(selected_section, {day: [None] * len(PERIODS) for day in DAYS}),
                "allGrids": all_grids,
                "facultyWorkloads": faculty_workloads,
                "sharedClasses": [
                    session for session in session_log
                    if session.get("source") == "lab"
                ],
                "constraintViolations": _group_issue_records(constraint_violations),
                "unscheduledSubjects": [],
                "hasValidTimetable": False,
                "hasConstraintViolations": bool(constraint_violations),
                "labSeed": True,
                "generatedFiles": {},
                "timetableMetadata": timetable_metadata,
                "generationMeta": {
                    "labSeed": True,
                    "timeoutSeconds": None,
                    "timeoutDisabled": True,
                    "retryStrategies": 0,
                    "attemptStrategies": [],
                    "deterministic": True,
                },
            },
        )
        _persist_faculty_occupancy(store, timetable_id, session_log)
        return {"timetableId": timetable_id, "message": "Lab slots seeded successfully."}

    requirements: list[Requirement] = []
    covered_shared_subjects: set[tuple[str, str]] = set()

    def build_requirement_from_rows(
        subject_id: str,
        sections: tuple[str, ...],
        section_rows: list[dict],
        shared: bool,
    ) -> Requirement | None:
        raw_faculty_ids = {_normalize_faculty_field(row.get("faculty_id", "")) for row in section_rows if row}
        faculty_pools = {
            tuple(sorted(set(_resolve_faculty_pool(raw_faculty_id, faculty_id_to_name, faculty_availability))))
            for raw_faculty_id in raw_faculty_ids
            if raw_faculty_id
        }
        remaining_hours = [
            max(0, int(row["hours"]) - lab_assigned_hours.get((str(row["section"]), subject_id), 0))
            for row in section_rows
            if row
        ]
        min_consecutive_hours = max(int(row.get("min_consecutive_hours", 1) or 1) for row in section_rows if row)
        max_consecutive_hours = min(int(row.get("max_consecutive_hours", 1) or 1) for row in section_rows if row)
        faculty_options = next(iter(sorted(faculty_pools)), ())
        faculty_label = sorted(raw_faculty_ids)[0] if raw_faculty_ids else ""

        if shared and len(faculty_pools) != 1:
            constraint_violations.append(
                {
                    "year": year,
                    "sections": list(sections),
                    "subject_id": subject_id,
                    "faculty_id": faculty_label,
                    "constraint": "shared class constraint",
                    "detail": "Shared class sections do not resolve to one common faculty or faculty pool.",
                }
            )
            return None
        if len(set(remaining_hours)) != 1:
            constraint_violations.append(
                {
                    "year": year,
                    "sections": list(sections),
                    "subject_id": subject_id,
                    "faculty_id": faculty_label,
                    "constraint": "shared class constraint" if shared else "section capacity constraint",
                    "detail": "Sections do not have the same remaining subject hours for global scheduling.",
                }
            )
            return None
        if min_consecutive_hours > max_consecutive_hours:
            constraint_violations.append(
                {
                    "year": year,
                    "sections": list(sections),
                    "subject_id": subject_id,
                    "faculty_id": faculty_label,
                    "constraint": "continuous hours constraint",
                    "detail": "Subject requires more consecutive hours than allowed by the main config.",
                }
            )
            return None

        hours = remaining_hours[0]
        if hours <= 0:
            return None

        resolved_faculty_options = faculty_options or ((faculty_label,) if faculty_label else ())
        # Multiple faculty IDs in a cell are treated as alternatives by default.
        # This avoids over-constraining the solver by requiring simultaneous co-teaching.
        resolved_faculty_team: tuple[str, ...] = ()
        return Requirement(
            subject_id=subject_id,
            faculty_id=faculty_label,
            faculty_options=resolved_faculty_options,
            faculty_team=resolved_faculty_team,
            sections=sections,
            hours=hours,
            min_consecutive_hours=min_consecutive_hours,
            max_consecutive_hours=max_consecutive_hours,
            shared=shared,
            phase=_determine_requirement_phase(
                shared,
                min_consecutive_hours,
                hours,
                resolved_faculty_options,
                faculty_availability,
            ),
        )

    for subject_id, groups in sorted(shared_constraints.items()):
        merged_groups = _merge_overlapping_section_groups(list(set(groups)))
        for sections in sorted(merged_groups):
            missing_sections = [section for section in sections if section not in all_sections]
            if missing_sections:
                constraint_violations.append(
                    {
                        "year": year,
                        "sections": list(sections),
                        "subject_id": subject_id,
                        "faculty_id": "",
                        "constraint": "shared class constraint",
                        "detail": f"Shared class references sections missing from main config: {', '.join(missing_sections)}",
                    }
                )
                continue

            section_rows = [main_rows_by_section_subject.get((section, subject_id)) for section in sections]
            if any(row is None for row in section_rows):
                constraint_violations.append(
                    {
                        "year": year,
                        "sections": list(sections),
                        "subject_id": subject_id,
                        "faculty_id": "",
                        "constraint": "shared class constraint",
                        "detail": "Shared class subject is missing in one or more sections.",
                    }
                )
                continue

            requirement = build_requirement_from_rows(subject_id, sections, [row for row in section_rows if row], True)
            if requirement:
                requirements.append(requirement)
            for section in sections:
                covered_shared_subjects.add((section, subject_id))

    for (section, subject_id), row in sorted(main_rows_by_section_subject.items()):
        if (section, subject_id) in covered_shared_subjects:
            continue
        remaining_hours = max(0, int(row.get("hours", 0) or 0) - lab_assigned_hours.get((section, subject_id), 0))
        if remaining_hours <= 0:
            continue
        raw_faculty_value = str(row.get("faculty_id", "")).strip()
        faculty_options = _resolve_faculty_pool(raw_faculty_value, faculty_id_to_name, faculty_availability)
        requirements.append(
            Requirement(
                subject_id=subject_id,
                faculty_id=raw_faculty_value,
                faculty_options=faculty_options,
                faculty_team=(),
                sections=(section,),
                hours=remaining_hours,
                min_consecutive_hours=max(1, int(row.get("min_consecutive_hours", 1) or 1)),
                max_consecutive_hours=max(1, int(row.get("max_consecutive_hours", 1) or 1)),
                shared=False,
                phase=_determine_requirement_phase(
                    False,
                    max(1, int(row.get("min_consecutive_hours", 1) or 1)),
                    remaining_hours,
                    faculty_options,
                    faculty_availability,
                ),
            )
        )

    prior_faculty_ids = set(prior_faculty_busy)
    for requirement in requirements:
        requirement.common_faculty = any(
            faculty_id in prior_faculty_ids for faculty_id in _requirement_faculty_tokens(requirement)
        )

    requirements.sort(key=lambda item: _requirement_priority(item, faculty_availability))

    # Rebalance minimal overload to keep solver from collapsing into global no-free-slot
    # when a few sections are over-constrained due locked slots.
    for section in all_sections:
        remaining_slots = sum(
            1 for day in DAYS for period in PERIODS
            if schedules[(year, section)][day][period] is None
        )
        while True:
            req_indices = [idx for idx, req in enumerate(requirements) if section in req.sections and req.hours > 0]
            required_hours = sum(requirements[idx].hours for idx in req_indices)
            overload = required_hours - remaining_slots
            if overload <= 0:
                break

            soft_subject_ids = {"11", "12", "21"}
            adjustable = [idx for idx in req_indices if not requirements[idx].shared]
            if not adjustable:
                constraint_violations.append(
                    {
                        "year": year,
                        "sections": [section],
                        "subject_id": "",
                        "faculty_id": "",
                        "constraint": "section capacity constraint",
                        "detail": (
                            f"Section {section} needs {required_hours} hour(s) but only {remaining_slots} "
                            "slot(s) are available after locked entries. Reduce workload or lab locks."
                        ),
                    }
                )
                break

            adjustable.sort(
                key=lambda idx: (
                    0 if requirements[idx].subject_id in soft_subject_ids else 1,
                    -requirements[idx].hours,
                    requirements[idx].subject_id,
                )
            )
            target_idx = adjustable[0]
            requirements[target_idx].hours -= 1
            if requirements[target_idx].hours <= 0:
                requirements.pop(target_idx)
            else:
                requirements[target_idx].min_consecutive_hours = min(
                    requirements[target_idx].min_consecutive_hours,
                    requirements[target_idx].hours,
                )
                requirements[target_idx].max_consecutive_hours = min(
                    requirements[target_idx].max_consecutive_hours,
                    requirements[target_idx].hours,
                )

    if precheck_only:
        section_summary = []
        for section in all_sections:
            free_slots = sum(
                1 for day in DAYS for period in PERIODS
                if schedules[(year, section)][day][period] is None
            )
            required_hours = sum(req.hours for req in requirements if section in req.sections)
            deficit = max(0, required_hours - free_slots)
            section_summary.append(
                {
                    "section": section,
                    "requiredHours": required_hours,
                    "freeSlots": free_slots,
                    "deficitHours": deficit,
                    "lockedSlots": locked_hours_by_section.get(section, 0),
                }
            )

        section_summary.sort(key=lambda item: (item["deficitHours"] > 0, item["section"]), reverse=True)
        blocking = [item for item in section_summary if item["deficitHours"] > 0]
        return {
            "year": year,
            "feasible": len(blocking) == 0,
            "blockingSections": blocking,
            "sectionSummary": section_summary,
            "issues": constraint_violations,
        }

    requirements.sort(key=lambda item: _requirement_priority(item, faculty_availability))


    timeout_seconds = None
    total_deadline = float("inf")
    retry_orders: list[tuple[list[str], list[int]]] = [
        (list(DAYS), list(PERIODS)),
        (list(DAYS), list(reversed(PERIODS))),
        (list(reversed(DAYS)), list(PERIODS)),
        (list(reversed(DAYS)), list(reversed(PERIODS))),
        (list(DAYS), [2, 3, 4, 5, 1, 6, 7]),
        (list(reversed(DAYS)), [4, 3, 5, 2, 6, 1, 7]),
    ]
    strategy_orderings = [
        ("shared-first", lambda item: _requirement_priority(item, faculty_availability)),
        (
            "high-hour-first",
            lambda item: (
                0 if item.shared else 1,
                -item.hours,
                -item.min_consecutive_hours,
                item.phase,
                item.subject_id,
                ",".join(item.sections),
            ),
        ),
        (
            "continuous-first",
            lambda item: (
                0 if item.shared else 1,
                -item.min_consecutive_hours,
                -item.hours,
                item.phase,
                item.subject_id,
                ",".join(item.sections),
            ),
        ),
    ]
    unscheduled_subjects: list[dict] = []
    initial_log_length = len(session_log)
    def _reset_non_lab_assignments() -> None:
        while len(session_log) > initial_log_length:
            session = session_log.pop()
            for period in session["periods"]:
                fac_ids = [str(fid).strip() for fid in session.get("faculty_ids", []) if str(fid).strip()]
                if not fac_ids:
                    fac_ids = [
                        token.strip()
                        for token in str(session.get("faculty_id", "")).split(",")
                        if token.strip()
                    ]
                for fac_id in fac_ids:
                    faculty_busy.setdefault(fac_id, set()).discard((session["day"], period))
                for sec in session.get("sections", []):
                    schedules[(year, sec)][session["day"]][period] = None

    remaining_by_req = {req_idx: requirement.hours for req_idx, requirement in enumerate(requirements)}

    def _solve_with_orders(
        days_order: list[str],
        periods_order: list[int],
        candidate_limit: int,
        attempt_deadline: float,
    ) -> bool:
        remaining_by_req.update({req_idx: requirement.hours for req_idx, requirement in enumerate(requirements)})

        def backtrack() -> bool:
            if not _section_capacity_is_feasible(requirements, remaining_by_req, schedules, year):
                return False
            next_req_idx, candidates = _select_next_requirement(
                requirements,
                remaining_by_req,
                schedules,
                faculty_busy,
                faculty_availability,
                year,
                days_order,
                periods_order,
                candidate_limit,
            )
            if next_req_idx is None:
                return True
            if not candidates:
                return False

            requirement = requirements[next_req_idx]
            # §21: solver-placed shared subjects (from file) get source tag "shared_class_file"
            place_source = "shared_class_file" if requirement.shared else "solver"
            for candidate in candidates:
                placements = _place_block(
                    requirement,
                    candidate.faculty_ids,
                    candidate.day,
                    candidate.start_period,
                    candidate.block_size,
                    schedules,
                    faculty_busy,
                    year,
                    subject_id_to_name,
                    faculty_id_to_name,
                    session_log,
                    source=place_source,
                )
                remaining_by_req[next_req_idx] -= candidate.block_size
                if backtrack():
                    return True
                remaining_by_req[next_req_idx] += candidate.block_size
                _undo_block(requirement, candidate.faculty_ids, placements, schedules, faculty_busy, year, session_log)
            return False

        return backtrack()

    solved = False
    attempt = 0
    attempt_strategy_names: list[str] = []
    while not solved:
        _reset_non_lab_assignments()

        strategy_name, strategy_key = strategy_orderings[min(attempt, len(strategy_orderings) - 1)]
        if len(attempt_strategy_names) < 25:
            attempt_strategy_names.append(strategy_name)
        requirements.sort(key=strategy_key)

        if attempt >= len(retry_orders):
            random_days = list(DAYS)
            random_periods = list(PERIODS)
            random.Random(attempt).shuffle(random_days)
            random.Random(attempt * 17).shuffle(random_periods)
            days_order, periods_order = random_days, random_periods
        else:
            days_order, periods_order = retry_orders[attempt]

        # Increase candidate diversity so scarce-slot constraints can still be satisfied
        # without waiting for timeout-level backtracking.
        candidate_limit = min(52, 16 + attempt * 8)
        attempt_deadline = float("inf")
        if _solve_with_orders(days_order, periods_order, candidate_limit, attempt_deadline):
            solved = True
            break
        attempt += 1

    if not solved:
        _reset_non_lab_assignments()
        for req_idx, requirement in enumerate(requirements):
            remaining = remaining_by_req.get(req_idx, requirement.hours)
            if remaining <= 0:
                continue
            if not requirement.faculty_id:
                reason = "missing faculty mapping"
            else:
                reason = _infer_failure_reason(requirement, schedules, faculty_busy, faculty_availability, year)
            
            constraint_violations.append(
                {
                    "year": year,
                    "sections": list(requirement.sections),
                    "subject_id": requirement.subject_id,
                    "faculty_id": requirement.faculty_id,
                    "constraint": reason,
                    "detail": f"Unable to place {remaining} remaining hour(s) for subject {requirement.subject_id}. Possible reason: {reason}",
                }
            )
            unscheduled_subjects.append(
                {
                    "year": year,
                    "sections": list(requirement.sections),
                    "subject_id": requirement.subject_id,
                    "faculty_id": requirement.faculty_id,
                    "detail": reason,
                }
            )
    else:
        for requirement in requirements:
            if requirement.faculty_id:
                continue
            reason = "missing faculty mapping"
            constraint_violations.append(
                {
                    "year": year,
                    "sections": list(requirement.sections),
                    "subject_id": requirement.subject_id,
                    "faculty_id": "",
                    "constraint": reason,
                    "detail": f"Unable to place {requirement.hours} remaining hour(s) for subject {requirement.subject_id}.",
                }
            )
            unscheduled_subjects.append(
                {
                    "year": year,
                    "sections": list(requirement.sections),
                    "subject_id": requirement.subject_id,
                    "faculty_id": "",
                    "detail": reason,
                }
            )

    constraint_violations = _group_issue_records(constraint_violations)
    unscheduled_subjects = _group_issue_records(
        [
            {
                **item,
                "constraint": str(item.get("detail", "")).strip() or "unscheduled subject",
            }
            for item in unscheduled_subjects
        ]
    )
    for item in unscheduled_subjects:
        item.pop("constraint", None)

    has_constraint_failures = bool(unscheduled_subjects or constraint_violations)
    if has_constraint_failures:
        # For any constraint failures (including section totals mismatches), still
        # return a timetable + constraint report so the UI can generate timetables
        # for all years without skipping ("middle leaving").
        pass
    all_grids = _serialize_section_grids(year, all_sections, schedules)
    faculty_workloads = _build_faculty_workloads_from_sessions(session_log)
    # §21: shared class report must only include explicitly file-driven sessions
    # (source == "lab" from Lab File, or "shared_class_file" from Shared Class File)
    # Never include auto-detected sessions (source == "solver").
    shared_sessions = [
        session for session in session_log
        if session.get("source") in {"lab", "shared_class_file"}
    ]

    for violation in constraint_violations:
        subject_id = _normalize_id_token(violation.get("subject_id", ""))
        faculty_id = str(violation.get("faculty_id", "")).strip()
        faculty_ids = _split_faculty_tokens(faculty_id)
        if subject_id:
            violation["subject_name"] = subject_id_to_name.get(subject_id, subject_id)
        if faculty_ids:
            violation["faculty_name"] = ", ".join(faculty_id_to_name.get(fid, fid) for fid in faculty_ids)
            violation["faculty_id"] = ",".join(faculty_ids)

    for item in unscheduled_subjects:
        subject_id = _normalize_id_token(item.get("subject_id", ""))
        faculty_id = str(item.get("faculty_id", "")).strip()
        faculty_ids = _split_faculty_tokens(faculty_id)
        if subject_id:
            item["subject_name"] = subject_id_to_name.get(subject_id, subject_id)
        if faculty_ids:
            item["faculty_name"] = ", ".join(faculty_id_to_name.get(fid, fid) for fid in faculty_ids)
            item["faculty_id"] = ",".join(faculty_ids)

    shared_workbook = _build_shared_classes_workbook(shared_sessions)
    constraint_workbook = _build_constraint_report_workbook(constraint_violations, unscheduled_subjects)

    generated_files = {
        "sharedClassesReport": _encode_workbook("shared_classes_report.xlsx", shared_workbook),
    }
    section_workbook = _build_section_timetables_workbook(year, all_sections, schedules, timetable_metadata)
    faculty_workbook = _build_faculty_workload_workbook(session_log, faculty_id_to_name, timetable_metadata)
    generated_files["sectionTimetables"] = _encode_workbook("section_timetables.xlsx", section_workbook)
    generated_files["facultyWorkload"] = _encode_workbook("faculty_workload.xlsx", faculty_workbook)
    if constraint_violations or unscheduled_subjects:
        generated_files["constraintViolationReport"] = _encode_workbook(
            "constraint_violation_report.xlsx", constraint_workbook
        )

    timetable_id = store.next_timetable_id()
    selected_section = request_data.section if request_data.section in all_grids else all_sections[0]

    store.save_timetable(
        timetable_id,
        {
            "id": timetable_id,
            "year": year,
            "section": selected_section,
            "grid": all_grids.get(selected_section, {day: [None] * len(PERIODS) for day in DAYS}),
            "allGrids": all_grids,
            "facultyWorkloads": faculty_workloads,
            "sharedClasses": shared_sessions,
            "constraintViolations": constraint_violations,
            "unscheduledSubjects": unscheduled_subjects,
            "hasValidTimetable": not has_constraint_failures,
            "hasConstraintViolations": has_constraint_failures,
            "generatedFiles": generated_files,
            "timetableMetadata": timetable_metadata,
            "generationMeta": {
                "timeoutSeconds": timeout_seconds,
                "timeoutDisabled": True,
                "retryStrategies": attempt + 1,
                "attemptStrategies": attempt_strategy_names,
                "deterministic": False,
            },
        },
    )
    _persist_faculty_occupancy(store, timetable_id, session_log)

    message = (
        "Timetable generated successfully."
        if not has_constraint_failures
        else "Timetable generated with constraint violations (see constraint report)."
    )
    return {"timetableId": timetable_id, "message": message}

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from io import BytesIO

from fastapi import HTTPException
from openpyxl import Workbook

from models.schemas import GenerateTimetableRequest
from services.utils import normalize_year
from storage.memory_store import MemoryStore

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIODS = [1, 2, 3, 4, 5, 6, 7]
DAY_INDEX = {index + 1: day for index, day in enumerate(DAYS)}


@dataclass(frozen=True)
class Requirement:
    subject_id: str
    faculty_id: str
    sections: tuple[str, ...]
    hours: int
    continuous_hours: int
    shared: bool


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
    faculty_name = faculty_id_to_name.get(faculty_id, faculty_id)
    return faculty_id, faculty_name


def _resolve_subject_output(subject_id: str, subject_id_to_name: dict[str, str]) -> tuple[str, str]:
    subject_name = subject_id_to_name.get(subject_id, subject_id)
    return subject_id, subject_name


def _build_faculty_maps(request_data: GenerateTimetableRequest, store: MemoryStore) -> dict[str, str]:
    faculty_id_to_name: dict[str, str] = {}
    fac_map_payload = store.get_scoped_mapping("faculty_id_map", "global")
    if fac_map_payload:
        for row in fac_map_payload.get("rows", []):
            faculty_id = str(row.get("faculty_id", "")).strip()
            faculty_name = str(row.get("faculty_name", "")).strip()
            if faculty_id:
                faculty_id_to_name[faculty_id] = faculty_name or faculty_id
    for row in request_data.facultyIdNameMapping:
        faculty_id = str(row.facultyId).strip()
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
    if subject_map_payload:
        for row in subject_map_payload.get("rows", []):
            subject_id = str(row.get("subject_id", "")).strip()
            subject_name = str(row.get("subject_name", "")).strip()
            if subject_id:
                subject_id_to_name[subject_id] = subject_name or subject_id

    rule_payload = store.get_scoped_mapping("subject_continuous_rules", "global")
    if rule_payload:
        for row in rule_payload.get("rows", []):
            subject_id = str(row.get("subject_id", "")).strip()
            if subject_id:
                compulsory_continuous[subject_id] = max(
                    1, int(row.get("compulsory_continuous_hours", 1) or 1)
                )

    for row in request_data.subjectIdNameMapping:
        subject_id = str(row.subjectId).strip()
        subject_name = str(row.subjectName).strip()
        if subject_id:
            subject_id_to_name[subject_id] = subject_name or subject_id

    for row in request_data.subjectContinuousRules:
        subject_id = str(row.subjectId).strip()
        if subject_id:
            compulsory_continuous[subject_id] = max(1, int(row.compulsoryContinuousHours or 1))

    return subject_id_to_name, compulsory_continuous


def _build_faculty_availability(
    request_data: GenerateTimetableRequest,
    store: MemoryStore,
    faculty_keys: set[str],
    faculty_id_to_name: dict[str, str],
) -> dict[str, dict[str, set[int]]]:
    default_map = {day: set(PERIODS) for day in DAYS}
    availability: dict[str, dict[str, set[int]]] = {
        faculty: {day: periods.copy() for day, periods in default_map.items()}
        for faculty in faculty_keys
    }

    reverse_faculty_name_map = {
        name.strip(): faculty_id for faculty_id, name in faculty_id_to_name.items() if name.strip()
    }

    def resolve_faculty_key(raw_id: str, raw_name: str = "") -> str:
        faculty_id = str(raw_id).strip()
        if faculty_id:
            return faculty_id
        faculty_name = str(raw_name).strip()
        return reverse_faculty_name_map.get(faculty_name, faculty_name)

    uploaded_payload = store.get_scoped_mapping("faculty_availability", "global")
    if uploaded_payload:
        seen_pairs: set[tuple[str, str]] = set()
        for row in uploaded_payload.get("rows", []):
            faculty_key = resolve_faculty_key(row.get("faculty_id", ""), row.get("faculty_name", ""))
            day = _normalize_day(str(row.get("day", "")))
            period = int(row.get("period", 0) or 0)
            if not faculty_key or not day or period not in PERIODS:
                continue
            availability.setdefault(
                faculty_key, {name: periods.copy() for name, periods in default_map.items()}
            )
            pair = (faculty_key, day)
            if pair not in seen_pairs:
                availability[faculty_key][day] = set()
                seen_pairs.add(pair)
            availability[faculty_key][day].add(period)

    for entry in request_data.facultyAvailability:
        faculty_key = str(entry.facultyId).strip()
        if not faculty_key:
            continue
        availability.setdefault(
            faculty_key, {name: periods.copy() for name, periods in default_map.items()}
        )
        for raw_day, periods in entry.availablePeriodsByDay.items():
            day = _normalize_day(raw_day)
            if not day:
                continue
            availability[faculty_key][day] = {int(period) for period in periods if int(period) in PERIODS}

    return availability


def _candidate_block_sizes(remaining_hours: int, continuous_hours: int) -> list[int]:
    if remaining_hours <= 0:
        return []
    min_consecutive = max(1, continuous_hours)
    if remaining_hours > min_consecutive:
        return list(range(remaining_hours, min_consecutive - 1, -1))
    if remaining_hours == min_consecutive:
        return [remaining_hours]
    return [remaining_hours]


def _slot_is_free(
    sections: tuple[str, ...],
    faculty_id: str,
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
    periods = range(start_period, start_period + block_size)
    allowed_periods = faculty_availability.get(faculty_id, {day_name: set(PERIODS) for day_name in DAYS}).get(
        day, set(PERIODS)
    )
    for period in periods:
        if period not in allowed_periods:
            return False
        if faculty_id and (day, period) in faculty_busy.setdefault(faculty_id, set()):
            return False
        for section in sections:
            if schedules[(year, section)][day][period] is not None:
                return False
    return True


def _place_block(
    requirement: Requirement,
    day: str,
    start_period: int,
    block_size: int,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    year: str,
    subject_id_to_name: dict[str, str],
    faculty_id_to_name: dict[str, str],
    session_log: list[dict],
) -> list[tuple[str, int]]:
    subject_id, subject_name = _resolve_subject_output(requirement.subject_id, subject_id_to_name)
    faculty_id, faculty_name = _resolve_faculty_output(requirement.faculty_id, faculty_id_to_name)
    periods = list(range(start_period, start_period + block_size))
    for period in periods:
        if faculty_id:
            faculty_busy.setdefault(faculty_id, set()).add((day, period))
        for section in requirement.sections:
            schedules[(year, section)][day][period] = {
                "subject": subject_id,
                "subjectName": subject_name,
                "faculty": faculty_id,
                "facultyName": faculty_name,
                "isLab": False,
                "locked": False,
                "venue": "",
                "sharedSections": list(requirement.sections) if len(requirement.sections) > 1 else [],
            }
    session_log.append(
        {
            "year": year,
            "subject_id": subject_id,
            "subject_name": subject_name,
            "faculty_id": faculty_id,
            "faculty_name": faculty_name,
            "sections": list(requirement.sections),
            "day": day,
            "periods": periods,
            "venue": "",
            "isLab": False,
            "shared": len(requirement.sections) > 1,
        }
    )
    return [(day, period) for period in periods]


def _undo_block(
    requirement: Requirement,
    placements: list[tuple[str, int]],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    year: str,
    session_log: list[dict],
) -> None:
    for day, period in placements:
        if requirement.faculty_id:
            faculty_busy.setdefault(requirement.faculty_id, set()).discard((day, period))
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
    if not requirement.faculty_id:
        return "missing faculty mapping"

    faculty_has_any_slot = False
    faculty_has_continuous_slot = False
    section_has_any_slot = False

    for day in DAYS:
        for start in PERIODS:
            if _slot_is_free(
                requirement.sections,
                requirement.faculty_id,
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
                requirement.faculty_id,
                day,
                start,
                min(requirement.hours, max(1, requirement.continuous_hours)),
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
    if requirement.continuous_hours > 1 and not faculty_has_continuous_slot:
        return "continuous hours constraint"
    return "no free slot"


def _schedule_requirement(
    requirement: Requirement,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
    year: str,
    subject_id_to_name: dict[str, str],
    faculty_id_to_name: dict[str, str],
    session_log: list[dict],
    deadline: float,
    retry_orders: list[tuple[list[str], list[int]]],
) -> bool:
    placements_start = len(session_log)

    def backtrack(remaining_hours: int) -> bool:
        if time.perf_counter() >= deadline:
            return False
        if remaining_hours == 0:
            return True
        for block_size in _candidate_block_sizes(remaining_hours, requirement.continuous_hours):
            for days_order, periods_order in retry_orders:
                for day in days_order:
                    for start_period in periods_order:
                        if not _slot_is_free(
                            requirement.sections,
                            requirement.faculty_id,
                            day,
                            start_period,
                            block_size,
                            schedules,
                            faculty_busy,
                            faculty_availability,
                            year,
                        ):
                            continue
                        placements = _place_block(
                            requirement,
                            day,
                            start_period,
                            block_size,
                            schedules,
                            faculty_busy,
                            year,
                            subject_id_to_name,
                            faculty_id_to_name,
                            session_log,
                        )
                        if backtrack(remaining_hours - block_size):
                            return True
                        _undo_block(requirement, placements, schedules, faculty_busy, year, session_log)
        return False

    success = backtrack(requirement.hours)
    if success:
        return True

    while len(session_log) > placements_start:
        session = session_log.pop()
        for period in session["periods"]:
            if requirement.faculty_id:
                faculty_busy.setdefault(requirement.faculty_id, set()).discard((session["day"], period))
            for section in requirement.sections:
                schedules[(year, section)][session["day"]][period] = None
    return False


def _serialize_section_grids(
    year: str,
    sections: list[str],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
) -> dict[str, dict[str, list[dict | None]]]:
    return {
        section: {day: [schedules[(year, section)][day][period] for period in PERIODS] for day in DAYS}
        for section in sections
    }


def _build_faculty_workloads_from_sessions(sessions: list[dict]) -> dict[str, dict[str, list[str | None]]]:
    workloads: dict[str, dict[str, dict[int, str]]] = {}
    for session in sessions:
        faculty_name = str(session.get("faculty_name", "")).strip() or str(session.get("faculty_id", "")).strip()
        if not faculty_name:
            continue
        day = str(session["day"])
        sections_label = ",".join(session["sections"])
        subject_label = session.get("subject_name") or session.get("subject_id") or ""
        year_label = session.get("year", "")
        value = f"{year_label} {sections_label} {subject_label}".strip()
        for period in session["periods"]:
            workloads.setdefault(faculty_name, {}).setdefault(day, {})[period] = value

    return {
        faculty: {day: [day_map.get(day, {}).get(period) for period in PERIODS] for day in DAYS}
        for faculty, day_map in workloads.items()
    }


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


def _build_section_timetables_workbook(
    year: str,
    sections: list[str],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
) -> Workbook:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for section in sections:
        worksheet = workbook.create_sheet(title=f"{year}_{section}"[:31])
        worksheet.append(["DAY", *PERIODS])
        for day in DAYS:
            row = [day]
            for period in PERIODS:
                entry = schedules[(year, section)][day][period]
                if not entry:
                    row.append("")
                    continue
                parts = [str(entry.get("subjectName") or entry.get("subject") or "")]
                faculty = str(entry.get("facultyName") or entry.get("faculty") or "").strip()
                venue = str(entry.get("venue", "")).strip()
                if faculty:
                    parts.append(faculty)
                if venue:
                    parts.append(venue)
                row.append(" | ".join(parts))
            worksheet.append(row)
    return workbook


def _build_faculty_workload_workbook(
    faculty_workloads: dict[str, dict[str, list[str | None]]],
    faculty_id_to_name: dict[str, str],
) -> Workbook:
    workbook = Workbook()
    workbook.remove(workbook.active)
    if not faculty_workloads:
        worksheet = workbook.create_sheet(title="FacultyWorkload")
        worksheet.append(["FACULTY_ID", "FACULTY_NAME", "DAY", *PERIODS])
        return workbook

    for faculty_id in sorted(faculty_workloads):
        faculty_name = faculty_id_to_name.get(faculty_id, faculty_id)
        worksheet = workbook.create_sheet(title=str(faculty_name or faculty_id)[:31] or "Faculty")
        worksheet.append(["FACULTY_ID", faculty_id])
        worksheet.append(["FACULTY_NAME", faculty_name])
        worksheet.append([])
        worksheet.append(["DAY", *PERIODS])
        for day in DAYS:
            row = [day]
            row.extend(faculty_workloads.get(faculty_id, {}).get(day, [None] * len(PERIODS)))
            worksheet.append(row)
    return workbook


def _build_shared_classes_workbook(shared_sessions: list[dict]) -> Workbook:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "SharedClasses"
    worksheet.append(["YEAR", "SUBJECT_ID", "FACULTY_ID", "SECTIONS", "DAY", "PERIODS"])
    for session in shared_sessions:
        worksheet.append(
            [
                session.get("year", ""),
                session.get("subject_id", ""),
                session.get("faculty_id", ""),
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
    worksheet.append(["YEAR", "SECTIONS", "SUBJECT_ID", "FACULTY_ID", "CONSTRAINT", "DETAIL"])
    for violation in violations:
        worksheet.append(
            [
                violation.get("year", ""),
                ",".join(violation.get("sections", [])),
                violation.get("subject_id", ""),
                violation.get("faculty_id", ""),
                violation.get("constraint", ""),
                violation.get("detail", ""),
            ]
        )
    for item in unscheduled:
        worksheet.append(
            [
                item.get("year", ""),
                ",".join(item.get("sections", [])),
                item.get("subject_id", ""),
                item.get("faculty_id", ""),
                "unscheduled subject",
                item.get("detail", ""),
            ]
        )
    return workbook


def generate_timetable(request_data: GenerateTimetableRequest, store: MemoryStore) -> dict:
    request_data.year = normalize_year(request_data.year)
    year = request_data.year

    faculty_id_to_name = _build_faculty_maps(request_data, store)
    subject_id_to_name, compulsory_continuous = _build_subject_maps(request_data, store)

    main_payload = store.get_scoped_mapping("main_timetable_config", "global")
    lab_payload = store.get_scoped_mapping("lab_timetable_config", "global")
    shared_payload = store.get_scoped_mapping("shared_classes", "global")

    raw_main_rows = [
        row
        for row in (main_payload.get("rows", []) if main_payload else [])
        if normalize_year(str(row.get("year", ""))) == year
    ]
    raw_lab_rows = [
        row
        for row in (lab_payload.get("rows", []) if lab_payload else [])
        if normalize_year(str(row.get("year", ""))) == year
    ]

    for entry in request_data.manualEntries:
        entry_year = normalize_year(entry.year)
        if entry_year != year:
            continue
        raw_main_rows.append(
            {
                "year": entry_year,
                "section": str(entry.section).strip(),
                "subject_id": str(entry.subjectId).strip(),
                "faculty_id": str(entry.facultyId).strip(),
                "hours": int(entry.noOfHours),
                "continuous_hours": int(entry.continuousHours or 1),
            }
        )
        if entry.compulsoryContinuousHours:
            compulsory_continuous[str(entry.subjectId).strip()] = max(1, int(entry.compulsoryContinuousHours))

    for lab in request_data.manualLabEntries:
        if normalize_year(lab.year) != year:
            continue
        raw_lab_rows.append(
            {
                "year": year,
                "section": str(lab.section).strip(),
                "subject_id": str(lab.subjectId).strip(),
                "day": int(lab.day),
                "hours": [int(hour) for hour in lab.hours],
                "venue": str(lab.venue).strip(),
            }
        )

    if not raw_main_rows:
        raise _validation_error("No configurable sections found for the specified year.", [])

    section_total_hours: dict[str, int] = {}
    main_rows_by_section_subject: dict[tuple[str, str], dict] = {}
    section_subject_faculty: dict[tuple[str, str], str] = {}
    for row in raw_main_rows:
        section = str(row.get("section", "")).strip()
        subject_id = str(row.get("subject_id", "")).strip()
        faculty_id = str(row.get("faculty_id", "")).strip()
        hours = int(row.get("hours", 0) or 0)
        continuous_hours = max(1, int(row.get("continuous_hours", 1) or 1))
        if not section or not subject_id:
            continue
        section_total_hours[section] = section_total_hours.get(section, 0) + hours
        actual_continuous = max(1, compulsory_continuous.get(subject_id, continuous_hours))
        key = (section, subject_id)
        if key not in main_rows_by_section_subject:
            main_rows_by_section_subject[key] = {
                "section": section,
                "subject_id": subject_id,
                "faculty_id": faculty_id,
                "hours": 0,
                "continuous_hours": actual_continuous,
            }
        main_rows_by_section_subject[key]["hours"] += hours
        main_rows_by_section_subject[key]["continuous_hours"] = max(
            main_rows_by_section_subject[key]["continuous_hours"], actual_continuous
        )
        section_subject_faculty[key] = faculty_id

    validation_errors = []
    for section in sorted(section_total_hours):
        total = section_total_hours[section]
        if total != 42:
            validation_errors.append(
                {
                    "year": year,
                    "section": section,
                    "hours": total,
                    "expected": 42,
                    "detail": f"Year {year} Section {section} -> {total} hours (Expected: 42)",
                }
            )
    if validation_errors:
        raise _validation_error("Validation Error: Main config section totals must equal 42.", validation_errors)

    all_sections = sorted(section_total_hours)
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]] = {
        (year, section): {day: {period: None for period in PERIODS} for day in DAYS} for section in all_sections
    }

    all_faculties = {
        str(item.get("faculty_id", "")).strip()
        for item in main_rows_by_section_subject.values()
        if str(item.get("faculty_id", "")).strip()
    }
    faculty_availability = _build_faculty_availability(request_data, store, all_faculties, faculty_id_to_name)
    faculty_busy = store.get_global_faculty_occupancy()
    session_log: list[dict] = []
    constraint_violations: list[dict] = []
    lab_assigned_hours: dict[tuple[str, str], int] = {}

    shared_constraints: dict[str, list[tuple[str, ...]]] = {}
    if shared_payload:
        for row in shared_payload.get("rows", []):
            if normalize_year(str(row.get("year", ""))) != year:
                continue
            subject_id = str(row.get("subject", "")).strip()
            sections = tuple(sorted({str(section).strip() for section in row.get("sections", []) if str(section).strip()}))
            if subject_id and sections:
                shared_constraints.setdefault(subject_id, []).append(sections)

    for shared in request_data.sharedClasses:
        if normalize_year(shared.year) != year:
            continue
        subject_id = str(shared.subject).strip()
        sections = tuple(sorted({str(section).strip() for section in shared.sections if str(section).strip()}))
        if subject_id and sections:
            shared_constraints.setdefault(subject_id, []).append(sections)

    lab_groups: dict[tuple[str, str, str, tuple[int, ...]], list[dict]] = {}
    sorted_lab_rows = sorted(
        raw_lab_rows,
        key=lambda row: (
            str(row.get("subject_id", "")).strip(),
            str(section_subject_faculty.get((str(row.get("section", "")).strip(), str(row.get("subject_id", "")).strip()), "")).strip(),
            int(row.get("day", 0) or 0),
            tuple(sorted(int(period) for period in row.get("hours", []) if int(period) in PERIODS)),
            str(row.get("section", "")).strip(),
        ),
    )

    for row in sorted_lab_rows:
        section = str(row.get("section", "")).strip()
        subject_id = str(row.get("subject_id", "")).strip()
        faculty_id = section_subject_faculty.get((section, subject_id), "")
        day = _normalize_day(int(row.get("day", 0) or 0))
        periods = tuple(sorted(int(period) for period in row.get("hours", []) if int(period) in PERIODS))
        if not section or section not in all_sections:
            raise _validation_error(
                "Lab timetable references a section that is missing from the main config file.",
                [{"year": year, "section": section, "subject_id": subject_id}],
            )
        if not day or not periods:
            constraint_violations.append(
                {
                    "year": year,
                    "sections": [section],
                    "subject_id": subject_id,
                    "faculty_id": faculty_id,
                    "constraint": "invalid lab configuration",
                    "detail": "Lab entry has an invalid day or periods value.",
                }
            )
            continue
        lab_groups.setdefault((faculty_id, subject_id, day, periods), []).append(row)

    for (faculty_id, subject_id, day, periods), group_rows in sorted(
        lab_groups.items(),
        key=lambda item: (item[0][2], item[0][3], item[0][1], ",".join(sorted(str(row.get("section", "")) for row in item[1]))),
    ):
        sections = sorted(str(row.get("section", "")).strip() for row in group_rows)
        venue = str(group_rows[0].get("venue", "")).strip()
        subject_id_resolved, subject_name = _resolve_subject_output(subject_id, subject_id_to_name)
        faculty_id_resolved, faculty_name = _resolve_faculty_output(faculty_id, faculty_id_to_name)
        for period in periods:
            for section in sections:
                if schedules[(year, section)][day][period] is not None:
                    raise _validation_error(
                        "Lab timetable has overlapping locked lab slots.",
                        [{"year": year, "section": section, "day": day, "period": period, "subject_id": subject_id}],
                    )
                schedules[(year, section)][day][period] = {
                    "subject": subject_id_resolved,
                    "subjectName": subject_name,
                    "faculty": faculty_id_resolved,
                    "facultyName": faculty_name,
                    "isLab": True,
                    "locked": True,
                    "venue": venue,
                    "sharedSections": sections if len(sections) > 1 else [],
                }
                lab_assigned_hours[(section, subject_id)] = lab_assigned_hours.get((section, subject_id), 0) + 1
            if faculty_id_resolved:
                if period not in faculty_availability.get(faculty_id_resolved, {day_name: set(PERIODS) for day_name in DAYS}).get(
                    day, set(PERIODS)
                ):
                    constraint_violations.append(
                        {
                            "year": year,
                            "sections": sections,
                            "subject_id": subject_id,
                            "faculty_id": faculty_id_resolved,
                            "constraint": "faculty availability conflict",
                            "detail": f"Locked lab on {day} period {period} is outside allowed faculty availability.",
                        }
                    )
                if (day, period) in faculty_busy.setdefault(faculty_id_resolved, set()):
                    constraint_violations.append(
                        {
                            "year": year,
                            "sections": sections,
                            "subject_id": subject_id,
                            "faculty_id": faculty_id_resolved,
                            "constraint": "faculty workload conflict",
                            "detail": f"Locked lab on {day} period {period} overlaps an existing faculty assignment.",
                        }
                    )
                faculty_busy[faculty_id_resolved].add((day, period))

        session_log.append(
            {
                "year": year,
                "subject_id": subject_id_resolved,
                "subject_name": subject_name,
                "faculty_id": faculty_id_resolved,
                "faculty_name": faculty_name,
                "sections": sections,
                "day": day,
                "periods": list(periods),
                "venue": venue,
                "isLab": True,
                "shared": len(sections) > 1,
            }
        )

    requirements: list[Requirement] = []
    covered_shared_subjects: set[tuple[str, str]] = set()
    for subject_id, groups in sorted(shared_constraints.items()):
        for sections in sorted(set(groups)):
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

            faculties = {str(row.get("faculty_id", "")).strip() for row in section_rows if row}
            remaining_hours = [
                max(0, int(row["hours"]) - lab_assigned_hours.get((str(row["section"]), subject_id), 0))
                for row in section_rows
                if row
            ]
            continuous_hours = max(int(row.get("continuous_hours", 1) or 1) for row in section_rows if row)
            if len(faculties) != 1 or not next(iter(faculties), ""):
                constraint_violations.append(
                    {
                        "year": year,
                        "sections": list(sections),
                        "subject_id": subject_id,
                        "faculty_id": "",
                        "constraint": "shared class constraint",
                        "detail": "Shared class sections do not resolve to one common faculty.",
                    }
                )
                continue
            if len(set(remaining_hours)) != 1:
                constraint_violations.append(
                    {
                        "year": year,
                        "sections": list(sections),
                        "subject_id": subject_id,
                        "faculty_id": next(iter(faculties)),
                        "constraint": "shared class constraint",
                        "detail": "Shared class sections do not have the same remaining subject hours.",
                    }
                )
                continue
            hours = remaining_hours[0]
            if hours <= 0:
                for section in sections:
                    covered_shared_subjects.add((section, subject_id))
                continue
            requirements.append(
                Requirement(
                    subject_id=subject_id,
                    faculty_id=next(iter(faculties)),
                    sections=sections,
                    hours=hours,
                    continuous_hours=continuous_hours,
                    shared=True,
                )
            )
            for section in sections:
                covered_shared_subjects.add((section, subject_id))

    for (section, subject_id), row in sorted(main_rows_by_section_subject.items()):
        if (section, subject_id) in covered_shared_subjects:
            continue
        remaining_hours = max(0, int(row.get("hours", 0) or 0) - lab_assigned_hours.get((section, subject_id), 0))
        if remaining_hours <= 0:
            continue
        requirements.append(
            Requirement(
                subject_id=subject_id,
                faculty_id=str(row.get("faculty_id", "")).strip(),
                sections=(section,),
                hours=remaining_hours,
                continuous_hours=max(1, int(row.get("continuous_hours", 1) or 1)),
                shared=False,
            )
        )

    requirements.sort(
        key=lambda item: (
            0 if item.shared else 1,
            -item.continuous_hours,
            -item.hours,
            item.subject_id,
            ",".join(item.sections),
        )
    )

    deadline = time.perf_counter() + 300.0
    retry_orders = [
        (DAYS, PERIODS),
        (DAYS, list(reversed(PERIODS))),
        (list(reversed(DAYS)), PERIODS),
    ]
    unscheduled_subjects: list[dict] = []

    for requirement in requirements:
        if not requirement.faculty_id:
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
            continue
        if time.perf_counter() >= deadline:
            unscheduled_subjects.append(
                {
                    "year": year,
                    "sections": list(requirement.sections),
                    "subject_id": requirement.subject_id,
                    "faculty_id": requirement.faculty_id,
                    "detail": "Scheduling stopped after reaching the generation timeout.",
                }
            )
            continue
        if _schedule_requirement(
            requirement,
            schedules,
            faculty_busy,
            faculty_availability,
            year,
            subject_id_to_name,
            faculty_id_to_name,
            session_log,
            deadline,
            retry_orders,
        ):
            continue
        reason = _infer_failure_reason(requirement, schedules, faculty_busy, faculty_availability, year)
        constraint_violations.append(
            {
                "year": year,
                "sections": list(requirement.sections),
                "subject_id": requirement.subject_id,
                "faculty_id": requirement.faculty_id,
                "constraint": reason,
                "detail": f"Unable to place {requirement.hours} remaining hour(s) for subject {requirement.subject_id}.",
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

    all_grids = _serialize_section_grids(year, all_sections, schedules)
    faculty_workloads = _build_faculty_workloads_from_sessions(session_log)
    shared_sessions = [session for session in session_log if len(session.get("sections", [])) > 1]

    for violation in constraint_violations:
        subject_id = str(violation.get("subject_id", "")).strip()
        faculty_id = str(violation.get("faculty_id", "")).strip()
        if subject_id:
            violation["subject_name"] = subject_id_to_name.get(subject_id, subject_id)
        if faculty_id:
            violation["faculty_name"] = faculty_id_to_name.get(faculty_id, faculty_id)

    for item in unscheduled_subjects:
        subject_id = str(item.get("subject_id", "")).strip()
        faculty_id = str(item.get("faculty_id", "")).strip()
        if subject_id:
            item["subject_name"] = subject_id_to_name.get(subject_id, subject_id)
        if faculty_id:
            item["faculty_name"] = faculty_id_to_name.get(faculty_id, faculty_id)

    section_workbook = _build_section_timetables_workbook(year, all_sections, schedules)
    faculty_workbook = _build_faculty_workload_workbook(faculty_workloads, faculty_id_to_name)
    shared_workbook = _build_shared_classes_workbook(shared_sessions)
    constraint_workbook = _build_constraint_report_workbook(constraint_violations, unscheduled_subjects)

    generated_files = {
        "sectionTimetables": _encode_workbook("section_timetables.xlsx", section_workbook),
        "facultyWorkload": _encode_workbook("faculty_workload.xlsx", faculty_workbook),
        "sharedClassesReport": _encode_workbook("shared_classes_report.xlsx", shared_workbook),
    }
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
            "grid": all_grids[selected_section],
            "allGrids": all_grids,
            "facultyWorkloads": faculty_workloads,
            "sharedClasses": shared_sessions,
            "constraintViolations": constraint_violations,
            "unscheduledSubjects": unscheduled_subjects,
            "generatedFiles": generated_files,
            "generationMeta": {
                "timeoutSeconds": 300,
                "retryStrategies": len(retry_orders),
                "deterministic": True,
            },
        },
    )

    occupied_faculty_slots: set[tuple[str, str, int]] = set()
    for session in session_log:
        faculty_id = str(session.get("faculty_id", "")).strip()
        if not faculty_id:
            continue
        for period in session.get("periods", []):
            occupied_faculty_slots.add((faculty_id, str(session["day"]), int(period)))

    for faculty_id, day, period in sorted(occupied_faculty_slots):
        store.mark_faculty_busy(faculty_id, day, period, timetable_id, year=year, section=selected_section)

    if unscheduled_subjects or constraint_violations:
        return {
            "timetableId": timetable_id,
            "message": "Timetable generated partially with constraint violations.",
        }
    return {"timetableId": timetable_id, "message": "Timetable generated successfully"}

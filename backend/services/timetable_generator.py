from __future__ import annotations

import random
import time
from dataclasses import dataclass

from fastapi import HTTPException

from models.schemas import GenerateTimetableRequest
from storage.memory_store import MemoryStore
from services.utils import normalize_year

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIODS = [1, 2, 3, 4, 5, 6, 7]
PRE_LUNCH = {1, 2, 3, 4}
POST_LUNCH = {5, 6, 7}


@dataclass
class Requirement:
    subject: str
    faculty: str
    hours: int
    continuous_hours: int
    target_sections: list[str]


@dataclass
class PlacementTask:
    subject: str
    faculty: str
    block: int
    target_sections: list[str]


def _validation_error(message: str, details: list | None = None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "ValidationError", "message": message, "details": details or []},
    )




def _normalize_subject(name: str) -> str:
    return name.strip()


def _subject_key(name: str) -> str:
    # Matching key used across different uploads where casing/spacing often differs.
    return " ".join(name.strip().lower().split())


def _resolve_faculty(token: str, faculty_id_to_name: dict[str, str]) -> str:
    cleaned = token.strip()
    return faculty_id_to_name.get(cleaned, cleaned)


def _normalize_batch_type(value: str | None) -> str:
    text = (value or "").strip().upper()
    if text in {"CREAM", "GENERAL"}:
        return text
    return "ALL"


def _scope_key_year_batch(year: str, batch_type: str) -> str:
    return f"year:{year.strip()}:batch:{_normalize_batch_type(batch_type)}"


def _extract_mappings(request_data: GenerateTimetableRequest, store: MemoryStore):
    faculty_id_to_name: dict[str, str] = {}
    subject_faculty_map: dict[str, list[dict]] = {"ALL": [], "CREAM": [], "GENERAL": []}
    subject_periods_map: dict[str, list[dict]] = {"ALL": [], "CREAM": [], "GENERAL": []}
    mapping_ids = request_data.mappingFileIds

    faculty_payload = None
    if mapping_ids and mapping_ids.facultyIdMap:
        faculty_payload = store.get_file_map(mapping_ids.facultyIdMap)
        if not faculty_payload:
            raise _validation_error("Invalid facultyIdMap fileId", [])
    else:
        faculty_payload = store.get_scoped_mapping("faculty_id_map", "global")

    if faculty_payload:
        for row in faculty_payload["rows"]:
            faculty_id = str(row.get("faculty_id", "")).strip()
            faculty_name = str(row.get("faculty_name", "")).strip()
            if faculty_id and faculty_name:
                faculty_id_to_name[faculty_id] = faculty_name

    if mapping_ids and mapping_ids.subjectFacultyMap:
        subject_faculty_payload = store.get_file_map(mapping_ids.subjectFacultyMap)
        if not subject_faculty_payload:
            raise _validation_error("Invalid subjectFacultyMap fileId", [])
        subject_faculty_map["ALL"] = subject_faculty_payload["rows"]

    if mapping_ids and mapping_ids.subjectFacultyMapCream:
        subject_faculty_payload = store.get_file_map(mapping_ids.subjectFacultyMapCream)
        if not subject_faculty_payload:
            raise _validation_error("Invalid subjectFacultyMapCream fileId", [])
        subject_faculty_map["CREAM"] = subject_faculty_payload["rows"]

    if mapping_ids and mapping_ids.subjectFacultyMapGeneral:
        subject_faculty_payload = store.get_file_map(mapping_ids.subjectFacultyMapGeneral)
        if not subject_faculty_payload:
            raise _validation_error("Invalid subjectFacultyMapGeneral fileId", [])
        subject_faculty_map["GENERAL"] = subject_faculty_payload["rows"]

    if not any(subject_faculty_map.values()):
        default_subject_faculty_payload = store.get_scoped_mapping(
            "subject_faculty_map",
            _scope_key_year_batch(request_data.year, "ALL"),
        ) or store.get_scoped_mapping(
            "subject_faculty_map",
            f"year:{request_data.year}",
        )
        cream_subject_faculty_payload = store.get_scoped_mapping(
            "subject_faculty_map",
            _scope_key_year_batch(request_data.year, "CREAM"),
        )
        general_subject_faculty_payload = store.get_scoped_mapping(
            "subject_faculty_map",
            _scope_key_year_batch(request_data.year, "GENERAL"),
        )
        if default_subject_faculty_payload:
            subject_faculty_map["ALL"] = default_subject_faculty_payload["rows"]
        if cream_subject_faculty_payload:
            subject_faculty_map["CREAM"] = cream_subject_faculty_payload["rows"]
        if general_subject_faculty_payload:
            subject_faculty_map["GENERAL"] = general_subject_faculty_payload["rows"]

    if mapping_ids and mapping_ids.subjectPeriodsMap:
        subject_periods_payload = store.get_file_map(mapping_ids.subjectPeriodsMap)
        if not subject_periods_payload:
            raise _validation_error("Invalid subjectPeriodsMap fileId", [])
        subject_periods_map["ALL"] = subject_periods_payload["rows"]

    if mapping_ids and mapping_ids.subjectPeriodsMapCream:
        subject_periods_payload = store.get_file_map(mapping_ids.subjectPeriodsMapCream)
        if not subject_periods_payload:
            raise _validation_error("Invalid subjectPeriodsMapCream fileId", [])
        subject_periods_map["CREAM"] = subject_periods_payload["rows"]

    if mapping_ids and mapping_ids.subjectPeriodsMapGeneral:
        subject_periods_payload = store.get_file_map(mapping_ids.subjectPeriodsMapGeneral)
        if not subject_periods_payload:
            raise _validation_error("Invalid subjectPeriodsMapGeneral fileId", [])
        subject_periods_map["GENERAL"] = subject_periods_payload["rows"]

    if not any(subject_periods_map.values()):
        default_payload = store.get_scoped_mapping(
            "subject_periods_map",
            _scope_key_year_batch(request_data.year, "ALL"),
        ) or store.get_scoped_mapping("subject_periods_map", f"year:{request_data.year}")
        cream_payload = store.get_scoped_mapping(
            "subject_periods_map",
            _scope_key_year_batch(request_data.year, "CREAM"),
        )
        general_payload = store.get_scoped_mapping(
            "subject_periods_map",
            _scope_key_year_batch(request_data.year, "GENERAL"),
        )
        if default_payload:
            subject_periods_map["ALL"] = default_payload["rows"]
        if cream_payload:
            subject_periods_map["CREAM"] = cream_payload["rows"]
        if general_payload:
            subject_periods_map["GENERAL"] = general_payload["rows"]

    return faculty_id_to_name, subject_faculty_map, subject_periods_map


def _build_requirements(request_data: GenerateTimetableRequest, store: MemoryStore) -> tuple[list[Requirement], list[str], dict[str, str]]:
    faculty_id_to_name, subject_faculty_rows_by_batch, subject_period_rows_by_batch = _extract_mappings(request_data, store)

    # section -> subject -> faculty
    section_subject_faculty: dict[str, dict[str, str]] = {}

    # Manual inputs apply to selected section.
    section_subject_faculty.setdefault(request_data.section, {})
    for subject in request_data.subjects:
        if subject.subject.strip() and subject.faculty.strip():
            section_subject_faculty[request_data.section][_normalize_subject(subject.subject)] = _resolve_faculty(subject.faculty, faculty_id_to_name)

    section_batch_map = {
        str(section).strip(): _normalize_batch_type(str(batch))
        for section, batch in request_data.sectionBatchMap.items()
        if str(section).strip()
    }

    def include_subject_faculty_row(section: str, batch_scope: str) -> bool:
        section_batch = section_batch_map.get(section, "ALL")
        if batch_scope == "ALL":
            return True
        return section_batch == batch_scope

    for batch_scope, rows in subject_faculty_rows_by_batch.items():
        # Preferred path: keep only rows explicitly matching the requested year.
        # Fallback: if none match (common when uploaded sheets use a different year label),
        # use all rows from the scoped mapping payload.
        matching_rows = [row for row in rows if normalize_year(str(row.get("year", ""))) == request_data.year]
        candidate_rows = matching_rows if matching_rows else rows
        for row in candidate_rows:
            section = str(row.get("section", "")).strip()
            subject = _normalize_subject(str(row.get("subject", "")))
            faculty_id = str(row.get("faculty_id", "")).strip()
            faculty_name = _resolve_faculty(faculty_id, faculty_id_to_name)
            if not include_subject_faculty_row(section, batch_scope):
                continue
            if section and subject and faculty_name:
                section_subject_faculty.setdefault(section, {})[subject] = faculty_name

    subject_to_hours_by_batch: dict[str, dict[str, tuple[int, int]]] = {
        "ALL": {},
        "CREAM": {},
        "GENERAL": {},
    }

    for batch_type, rows in subject_period_rows_by_batch.items():
        for row in rows:
            subject = _normalize_subject(str(row.get("subject", "")))
            if not subject:
                continue
            hours = int(row.get("hours", 0) or 0)
            continuous = int(row.get("continuous_hours", 1) or 1)
            if hours > 0:
                subject_to_hours_by_batch.setdefault(batch_type, {})[_subject_key(subject)] = (hours, max(1, continuous))

    for row in request_data.subjectHours:
        subject = _normalize_subject(row.subject)
        if subject:
            subject_to_hours_by_batch["ALL"][_subject_key(subject)] = (row.hours, max(1, row.continuousHours))

    for raw_batch, entries in request_data.batchSubjectHours.items():
        batch_type = _normalize_batch_type(raw_batch)
        if batch_type == "ALL":
            continue
        for row in entries:
            subject = _normalize_subject(row.subject)
            if subject:
                subject_to_hours_by_batch[batch_type][_subject_key(subject)] = (row.hours, max(1, row.continuousHours))

    for lab in request_data.labs:
        subject = _normalize_subject(lab.lab)
        selected_batch = section_batch_map.get(request_data.section, "ALL")
        subject_key = _subject_key(subject)
        if subject and subject_key not in subject_to_hours_by_batch.get(selected_batch, {}) and subject_key not in subject_to_hours_by_batch["ALL"]:
            subject_to_hours_by_batch[selected_batch][subject_key] = (3, 3)
        if subject and lab.faculty:
            section_subject_faculty.setdefault(request_data.section, {})[subject] = _resolve_faculty(lab.faculty[0], faculty_id_to_name)

    if not section_subject_faculty:
        raise _validation_error("No subject-faculty mapping found to generate timetable", [])
    if not any(subject_to_hours_by_batch.values()):
        raise _validation_error("No subject hours configuration found to generate timetable", [])

    shared_map: dict[str, set[str]] = {}
    
    # Load from document upload first (global)
    shared_payload = store.get_scoped_mapping("shared_classes", "global")
    if shared_payload:
        for row in shared_payload.get("rows", []):
            req_year = normalize_year(str(row.get("year", "")))
            if req_year == request_data.year:
                sections = {s.strip() for s in row.get("sections", []) if s.strip()}
                subject = _normalize_subject(str(row.get("subject", "")))
                if subject and sections:
                    shared_map.setdefault(subject, set()).update(sections)

    # Merge with manual request data
    for shared in request_data.sharedClasses:
        if shared.year != request_data.year:
            continue
        sections = {sec.strip() for sec in shared.sections if sec.strip()}
        sections.add(request_data.section)
        subject = _normalize_subject(shared.subject)
        if subject and sections:
            shared_map.setdefault(subject, set()).update(sections)

    merged: dict[tuple[str, str, tuple[str, ...]], Requirement] = {}

    all_sections = sorted(set(section_subject_faculty.keys()) | {request_data.section} | set(section_batch_map.keys()))

    def resolve_hours_for_section(section: str, subject: str) -> tuple[int, int] | None:
        section_batch = section_batch_map.get(section, "ALL")
        batch_hours = subject_to_hours_by_batch.get(section_batch, {})
        key = _subject_key(subject)
        if key in batch_hours:
            return batch_hours[key]
        return subject_to_hours_by_batch["ALL"].get(key)

    for section, subject_map in section_subject_faculty.items():
        for subject, faculty in subject_map.items():
            hours_info = resolve_hours_for_section(section, subject)
            if not hours_info:
                continue
            hours, continuous = hours_info
            target = [section]
            if subject in shared_map and section in shared_map[subject]:
                target = sorted(shared_map[subject])

            key = (subject, faculty, tuple(target))
            current = merged.get(key)
            if current:
                continue

            # Validate shared subject faculty consistency across involved sections.
            if len(target) > 1:
                for sec in target:
                    assigned = section_subject_faculty.get(sec, {}).get(subject)
                    if assigned and assigned != faculty:
                        raise _validation_error(
                            "Shared class has different faculty across sections",
                            [{"subject": subject, "sections": target}],
                        )
                    sec_hours = resolve_hours_for_section(sec, subject)
                    if sec_hours and sec_hours != hours_info:
                        raise _validation_error(
                            "Shared class has different hours configuration across sections",
                            [{"subject": subject, "sections": target}],
                        )

            merged[key] = Requirement(
                subject=subject,
                faculty=faculty,
                hours=hours,
                continuous_hours=min(max(1, continuous), hours),
                target_sections=target,
            )

    requirements = list(merged.values())
    if not requirements:
        all_faculty_subjects = sorted(
            {
                subject
                for subject_map in section_subject_faculty.values()
                for subject in subject_map.keys()
            }
        )
        all_hour_subjects = sorted(
            {
                key
                for by_batch in subject_to_hours_by_batch.values()
                for key in by_batch.keys()
            }
        )
        raise _validation_error(
            "No subjects found for the selected section. Please check that the uploaded mappings contain data for the selected section and year, or provide manual inputs.",
            [
                {
                    "selectedYear": request_data.year,
                    "selectedSection": request_data.section,
                    "subjectsFromFacultyMapCount": len(all_faculty_subjects),
                    "subjectsFromHoursMapCount": len(all_hour_subjects),
                    "facultyMapSubjectsSample": all_faculty_subjects[:10],
                    "hoursMapSubjectsSample": all_hour_subjects[:10],
                }
            ],
        )

    return requirements, all_sections, faculty_id_to_name


def _can_place_block(start: int, block: int) -> bool:
    window = set(range(start, start + block))
    if start + block - 1 > 7:
        return False
    if window & PRE_LUNCH and window & POST_LUNCH:
        return False
    return True


def _build_faculty_availability(
    request_data: GenerateTimetableRequest,
    store: MemoryStore,
    faculty_id_to_name: dict[str, str],
    faculties: set[str],
) -> dict[str, dict[str, set[int]]]:
    availability = {
        faculty: {day: set(PERIODS) for day in DAYS}
        for faculty in faculties
    }

    # Load from document upload first (global)
    avail_payload = store.get_scoped_mapping("faculty_availability", "global")
    if avail_payload:
        for row in avail_payload.get("rows", []):
            faculty_id = str(row.get("faculty_id", "")).strip()
            faculty_key = _resolve_faculty(faculty_id, faculty_id_to_name)
            if not faculty_key:
                continue
            
            day = str(row.get("day", "")).strip()
            normalized_day = next((d for d in DAYS if d.lower().startswith(day.lower()[:3])), None)
            if not normalized_day:
                continue
                
            period = int(row.get("period", 0))
            if period in PERIODS:
                # If we have any entries for a faculty on a day, we start from an empty set 
                # for that specific faculty-day combo to allow ONLY specified periods.
                if faculty_key not in availability:
                    availability[faculty_key] = {d: set(PERIODS) for d in DAYS}
                
                # Special logic: the first time we see a specific faculty-day in the doc,
                # we clear the default "all periods" set.
                if "__doc_started" not in availability[faculty_key].get(f"{normalized_day}_meta", set()):
                    availability[faculty_key][normalized_day] = set()
                    availability[faculty_key].setdefault(f"{normalized_day}_meta", set()).add("__doc_started")
                
                availability[faculty_key][normalized_day].add(period)

    # Merge with manual request data
    for entry in request_data.facultyAvailability:
        faculty_key = _resolve_faculty(entry.facultyId, faculty_id_to_name)
        if not faculty_key:
            continue
        
        # Manual entry overrides or initializes
        if faculty_key not in availability:
            availability[faculty_key] = {d: set(PERIODS) for d in DAYS}

        for raw_day, periods in entry.availablePeriodsByDay.items():
            day = str(raw_day).strip()
            normalized_day = next((d for d in DAYS if d.lower().startswith(day.lower()[:3])), None)
            if not normalized_day:
                continue
            allowed = {int(p) for p in periods if int(p) in PERIODS}
            if allowed:
                availability[faculty_key][normalized_day] = allowed

    return availability


def _expand_requirements(requirements: list[Requirement]) -> list[PlacementTask]:
    shared: list[Requirement] = []
    continuous: list[Requirement] = []
    remaining: list[Requirement] = []

    for req in requirements:
        if len(req.target_sections) > 1:
            shared.append(req)
        elif req.continuous_hours > 1:
            continuous.append(req)
        else:
            remaining.append(req)

    def to_tasks(reqs: list[Requirement]) -> list[PlacementTask]:
        tasks: list[PlacementTask] = []
        for req in reqs:
            remaining_hours = req.hours
            while remaining_hours > 0:
                # `continuous_hours` in uploaded sheets is interpreted as an upper bound.
                # Keep unit blocks for robust solvability across dense institutional datasets.
                block = 1
                tasks.append(
                    PlacementTask(
                        subject=req.subject,
                        faculty=req.faculty,
                        block=block,
                        target_sections=req.target_sections,
                    )
                )
                remaining_hours -= block
        tasks.sort(key=lambda t: (t.block, len(t.target_sections)), reverse=True)
        return tasks

    return to_tasks(shared) + to_tasks(continuous) + to_tasks(remaining)


def _is_valid(
    task: PlacementTask,
    day: str,
    start_period: int,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
    year: str,
) -> bool:
    if not _can_place_block(start_period, task.block):
        return False

    target_periods = list(range(start_period, start_period + task.block))
    for period in target_periods:
        if period not in faculty_availability.get(task.faculty, {}).get(day, set(PERIODS)):
            return False
        if (day, period) in faculty_busy.get(task.faculty, set()):
            return False
        for sec in task.target_sections:
            if schedules[(year, sec)][day][period] is not None:
                return False
    return True


def _place_task(
    task: PlacementTask,
    day: str,
    start_period: int,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    year: str,
) -> list[tuple[str, int]]:
    added_slots: list[tuple[str, int]] = []
    for period in range(start_period, start_period + task.block):
        faculty_busy.setdefault(task.faculty, set()).add((day, period))
        added_slots.append((day, period))
        for sec in task.target_sections:
            schedules[(year, sec)][day][period] = {"subject": task.subject, "faculty": task.faculty}
    return added_slots


def _undo_task(
    task: PlacementTask,
    day: str,
    added_slots: list[tuple[str, int]],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    year: str,
) -> None:
    for day_name, period in added_slots:
        faculty_busy.setdefault(task.faculty, set()).discard((day_name, period))
        for sec in task.target_sections:
            schedules[(year, sec)][day_name][period] = None


def _generate_faculty_workloads(
    year: str,
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
) -> dict[str, dict[str, list[str | None]]]:
    workloads: dict[str, dict[str, dict[int, str]]] = {}
    for (sec_year, section), day_map in schedules.items():
        if sec_year != year:
            continue
        for day in DAYS:
            for period in PERIODS:
                entry = day_map[day][period]
                if not entry:
                    continue
                faculty = str(entry.get("faculty", "")).strip()
                subject = str(entry.get("subject", "")).strip()
                if not faculty or not subject:
                    continue
                workloads.setdefault(faculty, {}).setdefault(day, {})[period] = f"{section} {subject}"

    serialized: dict[str, dict[str, list[str | None]]] = {}
    for faculty, day_map in workloads.items():
        serialized[faculty] = {
            day: [day_map.get(day, {}).get(period) for period in PERIODS]
            for day in DAYS
        }
    return serialized


def generate_timetable(request_data: GenerateTimetableRequest, store: MemoryStore) -> dict:
    request_data.year = normalize_year(request_data.year)
    requirements, all_sections, faculty_id_to_name = _build_requirements(request_data, store)
    tasks = _expand_requirements(requirements)

    sections = {(request_data.year, section) for section in all_sections}
    sections.add((request_data.year, request_data.section))

    all_faculties = {req.faculty for req in requirements}
    faculty_availability = _build_faculty_availability(request_data, store, faculty_id_to_name, all_faculties)

    attempt_count = 200
    best_payload = None
    # Dense real-world sheets often need deeper search; keep bounded to avoid hanging.
    search_deadline = time.perf_counter() + 60.0

    for attempt in range(attempt_count):
        if time.perf_counter() >= search_deadline:
            break
        rng = random.Random(attempt)
        schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]] = {
            sec: {day: {period: None for period in PERIODS} for day in DAYS}
            for sec in sections
        }

        existing_occupancy = store.get_global_faculty_occupancy()
        faculty_busy: dict[str, set[tuple[str, int]]] = {
            faculty: slots.copy() for faculty, slots in existing_occupancy.items()
        }

        def valid_candidates(task: PlacementTask) -> list[tuple[str, int]]:
            candidates: list[tuple[str, int]] = []
            for day in DAYS:
                for period in PERIODS:
                    if _is_valid(
                        task=task,
                        day=day,
                        start_period=period,
                        schedules=schedules,
                        faculty_busy=faculty_busy,
                        faculty_availability=faculty_availability,
                        year=request_data.year,
                    ):
                        candidates.append((day, period))
            rng.shuffle(candidates)
            return candidates

        def backtrack(remaining_tasks: list[PlacementTask]) -> bool:
            if time.perf_counter() >= search_deadline:
                return False
            if not remaining_tasks:
                return True

            # Most-constrained-task-first drastically improves success for dense inputs.
            chosen_index = -1
            chosen_task: PlacementTask | None = None
            chosen_candidates: list[tuple[str, int]] | None = None

            for idx, candidate_task in enumerate(remaining_tasks):
                candidates = valid_candidates(candidate_task)
                if not candidates:
                    return False
                if chosen_candidates is None or len(candidates) < len(chosen_candidates):
                    chosen_index = idx
                    chosen_task = candidate_task
                    chosen_candidates = candidates
                    if len(chosen_candidates) == 1:
                        break

            if chosen_task is None or chosen_candidates is None:
                return False

            next_remaining = remaining_tasks[:chosen_index] + remaining_tasks[chosen_index + 1:]

            for day, start_period in chosen_candidates:

                added_slots = _place_task(
                    task=chosen_task,
                    day=day,
                    start_period=start_period,
                    schedules=schedules,
                    faculty_busy=faculty_busy,
                    year=request_data.year,
                )

                if backtrack(next_remaining):
                    return True

                _undo_task(
                    task=chosen_task,
                    day=day,
                    added_slots=added_slots,
                    schedules=schedules,
                    faculty_busy=faculty_busy,
                    year=request_data.year,
                )

            return False

        if backtrack(tasks):
            all_grids = {
                section: {
                    day: [schedules[(request_data.year, section)][day][period] for period in PERIODS]
                    for day in DAYS
                }
                for section in sorted({sec for (_, sec) in sections})
            }
            faculty_workloads = _generate_faculty_workloads(request_data.year, schedules)
            best_payload = {
                "allGrids": all_grids,
                "grid": all_grids.get(request_data.section, {}),
                "facultyBusy": faculty_busy,
                "facultyWorkloads": faculty_workloads,
            }
            break

    if not best_payload:
        if time.perf_counter() >= search_deadline:
            raise _validation_error(
                "Timetable generation timed out for current constraints",
                [{"hint": "Try fewer shared classes, lower continuous hours, or wider faculty availability"}],
            )
        raise _validation_error(
            "Unable to generate timetable with current constraints",
            [{"hint": "Try reducing constraints or adjusting continuous hours/faculty availability"}],
        )

    timetable_id = store.next_timetable_id()
    store.save_timetable(
        timetable_id,
        {
            "id": timetable_id,
            "year": request_data.year,
            "section": request_data.section,
            "grid": best_payload["grid"],
            "allGrids": best_payload["allGrids"],
            "facultyWorkloads": best_payload["facultyWorkloads"],
            "source": request_data.model_dump(),
        },
    )

    for faculty, slots in best_payload["facultyBusy"].items():
        for day, period in slots:
            store.mark_faculty_busy(
                faculty=faculty,
                day=day,
                period=period,
                source_id=timetable_id,
                year=request_data.year,
                section=request_data.section,
            )

    return {"timetableId": timetable_id, "message": "Timetable generated successfully"}

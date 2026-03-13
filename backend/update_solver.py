import sys

new_content = """from __future__ import annotations

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
    subject_id: str
    faculty_id: str
    hours: int
    continuous_hours: int
    target_sections: list[str]

@dataclass
class PlacementTask:
    subject_id: str
    faculty_id: str
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
    return " ".join(name.strip().lower().split())

def _resolve_faculty(token: str, faculty_id_to_name: dict[str, str]) -> str:
    cleaned = token.strip()
    return faculty_id_to_name.get(cleaned, cleaned)

def _resolve_subject(token: str, subject_id_to_name: dict[str, str]) -> str:
    cleaned = token.strip()
    return subject_id_to_name.get(cleaned, cleaned)

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
    availability: dict[str, dict[str, set[int]]] = {
        faculty: {day: set(PERIODS) for day in DAYS}
        for faculty in faculties
    }

    doc_seen: set[tuple[str, str]] = set()

    avail_payload = store.get_scoped_mapping("faculty_availability", "global")
    if avail_payload:
        for row in avail_payload.get("rows", []):
            faculty_id = str(row.get("faculty_id", "")).strip()
            if not faculty_id:
                continue
            
            # Allow use of resolved map or raw id if not in map
            faculty_key = _resolve_faculty(faculty_id, faculty_id_to_name)

            day = str(row.get("day", "")).strip()
            normalized_day = next((d for d in DAYS if d.lower().startswith(day.lower()[:3])), None)
            if not normalized_day:
                continue

            period = int(row.get("period", 0))
            if period not in PERIODS:
                continue

            if faculty_key not in availability:
                availability[faculty_key] = {day_k: set(PERIODS) for day_k in DAYS}

            pair = (faculty_key, normalized_day)
            if pair not in doc_seen:
                availability[faculty_key][normalized_day] = set()
                doc_seen.add(pair)

            availability[faculty_key][normalized_day].add(period)

    for entry in request_data.facultyAvailability:
        faculty_key = _resolve_faculty(entry.facultyId, faculty_id_to_name)
        if not faculty_key:
            continue

        if faculty_key not in availability:
            availability[faculty_key] = {day_k: set(PERIODS) for day_k in DAYS}

        for raw_day, periods in entry.availablePeriodsByDay.items():
            day = str(raw_day).strip()
            normalized_day = next((d for d in DAYS if d.lower().startswith(day.lower()[:3])), None)
            if not normalized_day:
                continue
            allowed = {int(p) for p in periods if int(p) in PERIODS}
            availability[faculty_key][normalized_day] = allowed

    return availability

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
        if period not in faculty_availability.get(task.faculty_id, {}).get(day, set(PERIODS)):
            return False
        if (day, period) in faculty_busy.get(task.faculty_id, set()):
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
        faculty_busy.setdefault(task.faculty_id, set()).add((day, period))
        added_slots.append((day, period))
        for sec in task.target_sections:
            schedules[(year, sec)][day][period] = {"subject": task.subject_id, "faculty": task.faculty_id}
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
        faculty_busy.setdefault(task.faculty_id, set()).discard((day_name, period))
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
    year = request_data.year
    
    # 1. Load Mappings
    faculty_id_to_name = {}
    subject_id_to_name = {}
    compulsory_continuous = {}
    
    fac_map_payload = store.get_scoped_mapping("faculty_id_map", "global")
    if fac_map_payload:
        for row in fac_map_payload.get("rows", []):
            if row.get("faculty_id"):
                faculty_id_to_name[str(row["faculty_id"]).strip()] = str(row.get("faculty_name", "")).strip()

    sub_map_payload = store.get_scoped_mapping("subject_id_mapping", "global")
    if sub_map_payload:
        for row in sub_map_payload.get("rows", []):
            if row.get("subject_id"):
                subject_id_to_name[str(row["subject_id"]).strip()] = str(row.get("subject_name", "")).strip()
                
    rule_payload = store.get_scoped_mapping("subject_continuous_rules", "global")
    if rule_payload:
        for row in rule_payload.get("rows", []):
            sub_id = str(row.get("subject_id", "")).strip()
            if sub_id:
                compulsory_continuous[sub_id] = int(row.get("compulsory_continuous_hours", 1))

    # 2. Extract Data from Main File and Labs
    main_payload = store.get_scoped_mapping("main_timetable_config", f"year:{year}")
    lab_payload = store.get_scoped_mapping("lab_timetable_config", f"year:{year}")
    
    raw_main_rows = main_payload.get("rows", []) if main_payload else []
    raw_lab_rows = lab_payload.get("rows", []) if lab_payload else []
    
    # Merge manual entries
    for m in request_data.manualEntries:
        if m.year == year:
            raw_main_rows.append({
                "year": m.year,
                "subject_id": m.subjectId,
                "section": m.section,
                "hours": m.noOfHours,
                "faculty_id": m.facultyId,
                "continuous_hours": m.continuousHours
            })
            if m.compulsoryContinuousHours:
                compulsory_continuous[m.subjectId] = m.compulsoryContinuousHours

    # 3. Validation Rule (Critical)
    # Sum of hours + lab hours for EVERY section must equal exactly 42
    section_hours_sum = {}
    
    # Accumulate Main File Hours
    for r in raw_main_rows:
        sec = str(r["section"]).strip()
        hrs = int(r.get("hours", 0))
        section_hours_sum[sec] = section_hours_sum.get(sec, 0) + hrs
        
    # Accumulate Lab Hours
    for r in raw_lab_rows:
        sec = str(r["section"]).strip()
        hrs_list = r.get("hours", [])
        section_hours_sum[sec] = section_hours_sum.get(sec, 0) + len(hrs_list)

    if not section_hours_sum:
        raise _validation_error("No configurable sections found for the specified year.", [])

    violating_sections = []
    for sec, tot in section_hours_sum.items():
        if tot != 42:
            violating_sections.append(f"{sec} ({tot} hrs)")
            
    if violating_sections:
        raise _validation_error(
            "Timetable constraint failed: Every section must have exactly 42 hours scheduled (Main + Labs).",
            [{"violating_sections": violating_sections}]
        )
        
    # Gather shared properties
    # Example format of Global Shared Classes Upload: 
    # {"subject": "10", "sections": ["C1", "C2"]}
    shared_map: dict[str, list[set[str]]] = {}
    shared_payload = store.get_scoped_mapping("shared_classes", "global")
    if shared_payload:
        for row in shared_payload.get("rows", []):
            req_year = normalize_year(str(row.get("year", "")))
            if req_year == year:
                sections = {s.strip() for s in row.get("sections", []) if s.strip()}
                subject = str(row.get("subject", "")).strip()
                if subject and sections:
                    shared_map.setdefault(subject, []).append(sections)
                    
    # Also shared manual classes
    for shared in request_data.sharedClasses:
        if shared.year != year:
            continue
        sections = {sec.strip() for sec in shared.sections if sec.strip()}
        subject = str(shared.subject).strip()
        if subject and sections:
            shared_map.setdefault(subject, []).append(sections)

    # Building requirements array from raw_main_rows mapping identical sections if shared
    merged_main: dict[tuple[str, str, tuple[str, ...]], Requirement] = {}
    
    # section -> subject_id -> faculty_id
    section_subject_faculty = {}
    
    for r in raw_main_rows:
        sec = str(r["section"]).strip()
        sub = str(r["subject_id"]).strip()
        fac = str(r["faculty_id"]).strip()
        
        section_subject_faculty.setdefault(sec, {})[sub] = fac
    
    all_sections = set(section_hours_sum.keys())
    
    for r in raw_main_rows:
        sec = str(r["section"]).strip()
        sub = str(r["subject_id"]).strip()
        fac = str(r["faculty_id"]).strip()
        raw_hours = int(r.get("hours", 0))
        max_cont = int(r.get("continuous_hours", 1))
        
        # Determine actual continuous via compulsory
        actual_cont = min(compulsory_continuous.get(sub, max_cont), max_cont)
        
        target = [sec]
        if sub in shared_map:
            for group in shared_map[sub]:
                if sec in group:
                    target = sorted(group)
                    break
                    
        key = (sub, fac, tuple(target))
        if key in merged_main:
            continue
            
        merged_main[key] = Requirement(
            subject_id=sub,
            faculty_id=fac,
            hours=raw_hours,
            continuous_hours=actual_cont,
            target_sections=target
        )
        
    requirements = list(merged_main.values())
    
    # Generate PlacementTasks
    tasks: list[PlacementTask] = []
    for req in requirements:
        remaining = req.hours
        while remaining > 0:
            block = req.continuous_hours if remaining >= req.continuous_hours else remaining
            tasks.append(
                PlacementTask(
                    subject_id=req.subject_id,
                    faculty_id=req.faculty_id,
                    block=block,
                    target_sections=req.target_sections
                )
            )
            remaining -= block
            
    # Sort largest block & longest target list first
    tasks.sort(key=lambda t: (t.block, len(t.target_sections)), reverse=True)
    
    # Initialize Schedules
    sections_pairs = {(year, sec) for sec in all_sections}
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]] = {
        sec: {day: {period: None for period in PERIODS} for day in DAYS}
        for sec in sections_pairs
    }
    
    all_faculties = set()
    for req in requirements:
        all_faculties.add(req.faculty_id)
    for row in raw_lab_rows:
        # shared labs mean multiple rows have same subject + same day + same period... but we process them iteratively
        pass

    faculty_availability = _build_faculty_availability(request_data, store, faculty_id_to_name, all_faculties)
    existing_occupancy = store.get_global_faculty_occupancy()
    
    faculty_busy: dict[str, set[tuple[str, int]]] = {
        fac: slots.copy() for fac, slots in existing_occupancy.items()
    }
    
    # Step 1 & 2 -> Assign fixed labs from lab file
    # We must lock those slots. Also apply shared lab logic if multiple sections have exact same config.
    # Group lab rows by (year, day, hours tuple, subject_id, venue)
    # wait, venue might be identical or different, prompt says 'choose any one of the provided venues' if shared.
    
    # Process labs simply: they are fixed. Just place them directly into schedules.
    for r in raw_lab_rows:
        sec = str(r["section"]).strip()
        sub = str(r["subject_id"]).strip()
        day_idx = int(r["day"])
        venue = str(r.get("venue", "")).strip()
        hours_list = r.get("hours", [])
        
        # day map: 1 -> Monday
        if day_idx < 1 or day_idx > 6:
            continue
        day_str = DAYS[day_idx - 1]
        
        for period in hours_list:
            if 0 < period <= 7:
                # We do not strictly need faculty for lab if not provided, but we can look it up if we want.
                # However, the user said section_subject_faculty mapping.
                # In the new structure, faculty is assigned strictly in the main config. If not, it can be left blank or assigned.
                # Let's assume the faculty is mapped or we just don't trace faculty_busy for purely venue labs, unless we have faculty.
                faculty = section_subject_faculty.get(sec, {}).get(sub, "")
                if faculty:
                    faculty_busy.setdefault(faculty, set()).add((day_str, period))
                
                schedules[(year, sec)][day_str][period] = {
                    "subject": sub,
                    "faculty": faculty,
                    "venue": venue,
                    "isLab": True
                }

    attempt_count = 200
    best_payload = None
    search_deadline = time.perf_counter() + 60.0

    for attempt in range(attempt_count):
        if time.perf_counter() >= search_deadline:
            break
            
        rng = random.Random(attempt)
        
        # Deep copy base schedules (which now includes labs!)
        import copy
        current_schedules = copy.deepcopy(schedules)
        current_busy = copy.deepcopy(faculty_busy)

        def valid_candidates(task: PlacementTask) -> list[tuple[str, int]]:
            candidates: list[tuple[str, int]] = []
            for day in DAYS:
                for period in PERIODS:
                    if _is_valid(
                        task=task,
                        day=day,
                        start_period=period,
                        schedules=current_schedules,
                        faculty_busy=current_busy,
                        faculty_availability=faculty_availability,
                        year=year,
                    ):
                        candidates.append((day, period))
            rng.shuffle(candidates)
            return candidates

        def backtrack(remaining_tasks: list[PlacementTask]) -> bool:
            if time.perf_counter() >= search_deadline:
                return False
            if not remaining_tasks:
                return True

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
                    schedules=current_schedules,
                    faculty_busy=current_busy,
                    year=year,
                )

                if backtrack(next_remaining):
                    return True

                _undo_task(
                    task=chosen_task,
                    day=day,
                    added_slots=added_slots,
                    schedules=current_schedules,
                    faculty_busy=current_busy,
                    year=year,
                )

            return False

        if backtrack(tasks):
            # Apply names resolution into the grid before saving
            for sec_key, day_map in current_schedules.items():
                for day, p_map in day_map.items():
                    for period, entry in p_map.items():
                        if entry:
                            # Convert IDs to Names mapping
                            sid = entry.get("subject", "")
                            fid = entry.get("faculty", "")
                            entry["subjectName"] = _resolve_subject(sid, subject_id_to_name)
                            entry["facultyName"] = _resolve_faculty(fid, faculty_id_to_name)

            all_grids = {
                section: {
                    day: [current_schedules[(year, section)][day][period] for period in PERIODS]
                    for day in DAYS
                }
                for section in sorted({sec for (_, sec) in sections_pairs})
            }
            faculty_workloads = _generate_faculty_workloads(year, current_schedules)
            
            # Use request_data.section if it exists in all_sections
            sec_req = request_data.section if request_data.section in all_sections else next(iter(all_sections))

            best_payload = {
                "allGrids": all_grids,
                "grid": all_grids.get(sec_req, {}),
                "facultyBusy": current_busy,
                "facultyWorkloads": faculty_workloads,
                "assignedSection": sec_req
            }
            break

    if not best_payload:
        if time.perf_counter() >= search_deadline:
            raise _validation_error(
                "Timetable generation timed out for current constraints",
                [{"hint": "Try fewer shared classes, lower continuous hours, or wider faculty availability"}]
            )
        raise _validation_error(
            "Unable to generate timetable with current constraints",
            [{"hint": "Check if hours are too compacted or if labs occupy too many critical slots."}]
        )

    timetable_id = store.next_timetable_id()
    store.save_timetable(
        timetable_id,
        {
            "id": timetable_id,
            "year": year,
            "section": best_payload["assignedSection"],
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
                year=year,
                section=best_payload["assignedSection"],
            )

    return {"timetableId": timetable_id, "message": "Timetable generated successfully"}

"""

with open(r"c:\\Users\\rajas\\OneDrive\\Desktop\\Timetable\\backend\\services\\timetable_generator.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Solver updated successfully")

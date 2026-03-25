from __future__ import annotations

import base64
import random
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


@dataclass
class Requirement:
    subject_id: str
    faculty_id: str
    faculty_options: tuple[str, ...]
    sections: tuple[str, ...]
    hours: int
    min_consecutive_hours: int
    max_consecutive_hours: int
    shared: bool
    phase: int = 4


@dataclass(frozen=True)
class SlotCandidate:
    day: str
    start_period: int
    block_size: int
    faculty_id: str
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
        faculty_id = str(raw_id).strip()
        if faculty_id:
            return faculty_id
        faculty_name = str(raw_name).strip()
        return reverse_faculty_name_map.get(faculty_name, faculty_name)

    uploaded_payload = store.get_scoped_mapping("faculty_availability", "global")
    if uploaded_payload:
        for row in uploaded_payload.get("rows", []):
            faculty_key = resolve_faculty_key(row.get("faculty_id", ""), row.get("faculty_name", ""))
            day = _normalize_day(str(row.get("day", "")))
            period = int(row.get("period", 0) or 0)
            if not faculty_key or not day or period not in PERIODS:
                continue
            availability.setdefault(faculty_key, {name: set(PERIODS) for name in DAYS})
            availability[faculty_key][day].add(period)

    for entry in request_data.facultyAvailability:
        faculty_key = str(entry.facultyId).strip()
        if not faculty_key:
            continue
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
    faculty_token = str(raw_faculty_id).strip()
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

    split_tokens = [faculty_token]
    for delimiter in [",", "/", "|", "+", "&"]:
        next_tokens: list[str] = []
        for token in split_tokens:
            next_tokens.extend(part.strip() for part in token.split(delimiter))
        split_tokens = next_tokens
    cleaned_split = tuple(sorted({token for token in split_tokens if token}))
    if len(cleaned_split) > 1:
        return cleaned_split
    return (faculty_token,)


def _choose_faculty_for_slot(
    requirement: Requirement,
    day: str,
    start_period: int,
    block_size: int,
    faculty_busy: dict[str, set[tuple[str, int]]],
    faculty_availability: dict[str, dict[str, set[int]]],
) -> str | None:
    periods = range(start_period, start_period + block_size)
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
        base = 30
    elif section_count <= 10:
        base = 90
    else:
        base = 180
    if requirement_count >= 20:
        base += 20
    if requirement_count >= 35:
        base += 30
    return min(180, base)


def _requirement_priority(
    requirement: Requirement,
    faculty_availability: dict[str, dict[str, set[int]]],
) -> tuple[int, int, int, int, str, str]:
    weekly_capacity = _requirement_weekly_capacity(requirement, faculty_availability)
    strict_availability = len(DAYS) * len(PERIODS) - weekly_capacity
    return (
        requirement.phase,
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

                candidates.append(
                    SlotCandidate(
                        day=day,
                        start_period=start_period,
                        block_size=block_size,
                        faculty_id=faculty_id,
                        score=_score_slot_candidate(
                            requirement,
                            faculty_id,
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
    best_key: tuple[int, int, int, int, str, str] | None = None

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
    faculty_id: str,
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
    faculty_id, faculty_name = _resolve_faculty_output(faculty_id, faculty_id_to_name)
    periods = list(range(start_period, start_period + block_size))
    for period in periods:
        if faculty_id:
            faculty_busy.setdefault(faculty_id, set()).add((day, period))
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
    faculty_id: str,
    placements: list[tuple[str, int]],
    schedules: dict[tuple[str, str], dict[str, dict[int, dict | None]]],
    faculty_busy: dict[str, set[tuple[str, int]]],
    year: str,
    session_log: list[dict],
) -> None:
    for day, period in placements:
        if faculty_id:
            faculty_busy.setdefault(faculty_id, set()).discard((day, period))
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
        faculty_name = str(session.get("faculty_name", "")).strip()
        faculty_id = str(session.get("faculty_id", "")).strip()
        faculty_key = faculty_name or faculty_id
        if not faculty_key:
            continue
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
        return workbook

    for faculty_id, workload in sorted(faculty_workloads.items()):
        faculty_name = faculty_id_to_name.get(faculty_id, faculty_id)
        worksheet = workbook.create_sheet(title=f"{faculty_name}"[:31])
        worksheet.append(["DAY", *PERIODS])
        for day in DAYS:
            row = [day]
            row.extend(workload.get(day, [None] * len(PERIODS)))
            worksheet.append(row)
    return workbook


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


def generate_timetable(request_data: GenerateTimetableRequest, store: MemoryStore) -> dict:
    request_data.year = normalize_year(request_data.year)
    year = request_data.year

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
        # Strip .0 from numeric faculty ID
        fid = str(entry.facultyId).strip()
        if fid.endswith(".0"):
            fid = fid[:-2]
        
        raw_main_rows.append(
            {
                "year": entry_year,
                "section": str(entry.section).strip(),
                "subject_id": str(entry.subjectId).strip(),
                "faculty_id": fid,
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
        raise HTTPException(status_code=400, detail="No configurable sections found for the specified year.")

    section_total_hours: dict[str, int] = {}
    main_rows_by_section_subject: dict[tuple[str, str], dict] = {}
    section_subject_faculty: dict[tuple[str, str], str] = {}
    for row in raw_main_rows:
        section = str(row.get("section", "")).strip()
        subject_id = str(row.get("subject_id", "")).strip()
        faculty_id = str(row.get("faculty_id", "")).strip()
        if faculty_id.endswith(".0"):
            faculty_id = faculty_id[:-2]
            
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
        str(item.get("faculty_id", "")).strip()
        for item in main_rows_by_section_subject.values()
        if str(item.get("faculty_id", "")).strip()
    }
    faculty_availability = _build_faculty_availability(request_data, store, all_faculties, faculty_id_to_name)
    faculty_busy: dict[str, set[tuple[str, int]]] = {}
    session_log: list[dict] = []
    constraint_violations: list[dict] = []
    lab_assigned_hours: dict[tuple[str, str], int] = {}

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
            subject_id = str(row.get("subject", row.get("subject_id", ""))).strip()
            sections = _resolve_shared_sections(
                row.get("sections", []),
                int(row.get("sections_count", 0) or 0) if str(row.get("sections_count", "")).strip() else None,
            )
            if subject_id and sections:
                shared_constraints.setdefault(subject_id, []).append(sections)

    for shared in request_data.sharedClasses:
        if normalize_year(shared.year) != year:
            continue
        subject_id = str(shared.subject).strip()
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
        subject_id = str(row.get("subject_id", "")).strip()
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
        faculty_id_resolved, faculty_name = _resolve_faculty_output(faculty_id, faculty_id_to_name)
        session_key = (year, subject_id_resolved, faculty_id_resolved, day, periods)
        placed_sections: set[str] = set()
        placed_periods: list[int] = []
        for period in periods:
            period_sections: list[str] = []
            for section in sections:
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
                period_sections.append(section)
                placed_sections.add(section)
            if not period_sections:
                continue
            placed_periods.append(period)
            if faculty_id_resolved:
                if period not in faculty_availability.get(faculty_id_resolved, {day_name: set(PERIODS) for day_name in DAYS}).get(
                    day, set(PERIODS)
                ):
                    constraint_violations.append(
                        {
                            "year": year,
                            "sections": period_sections,
                            "subject_id": subject_id,
                            "faculty_id": faculty_id_resolved,
                            "constraint": "faculty availability conflict",
                            "detail": f"Locked lab on {day} period {period} is outside allowed faculty availability.",
                        }
                    )
                existing_session = faculty_slot_sessions.setdefault(faculty_id_resolved, {}).get((day, period))
                if existing_session and existing_session != session_key:
                    constraint_violations.append(
                        {
                            "year": year,
                            "sections": period_sections,
                            "subject_id": subject_id,
                            "faculty_id": faculty_id_resolved,
                            "constraint": "faculty workload conflict",
                            "detail": f"Locked lab on {day} period {period} overlaps an existing faculty assignment.",
                        }
                    )
                faculty_busy.setdefault(faculty_id_resolved, set()).add((day, period))
                faculty_slot_sessions.setdefault(faculty_id_resolved, {})[(day, period)] = session_key

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
                "sections": sorted(placed_sections),
                "day": day,
                "periods": placed_periods,
                "venue": venue,
                "isLab": True,
                "shared": len(placed_sections) > 1,
                "source": "lab",
            }
        )

    requirements: list[Requirement] = []
    covered_shared_subjects: set[tuple[str, str]] = set()

    def build_requirement_from_rows(
        subject_id: str,
        sections: tuple[str, ...],
        section_rows: list[dict],
        shared: bool,
    ) -> Requirement | None:
        raw_faculty_ids = {str(row.get("faculty_id", "")).strip() for row in section_rows if row}
        faculty_pools = {
            _resolve_faculty_pool(raw_faculty_id, faculty_id_to_name, faculty_availability)
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
        faculty_options = next(iter(faculty_pools), ())
        faculty_label = next(iter(raw_faculty_ids), "")

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
        return Requirement(
            subject_id=subject_id,
            faculty_id=faculty_label,
            faculty_options=resolved_faculty_options,
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
        faculty_options = _resolve_faculty_pool(str(row.get("faculty_id", "")).strip(), faculty_id_to_name, faculty_availability)
        requirements.append(
            Requirement(
                subject_id=subject_id,
                faculty_id=str(row.get("faculty_id", "")).strip(),
                faculty_options=faculty_options,
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

    requirements.sort(key=lambda item: _requirement_priority(item, faculty_availability))

    for section in all_sections:
        reqs_for_sec = [req for req in requirements if section in req.sections]
        remaining_slots = sum(
            1 for day in DAYS for period in PERIODS
            if schedules[(year, section)][day][period] is None
        )
        required_hours = sum(r.hours for r in reqs_for_sec)
        
        if required_hours > remaining_slots:
            excess = required_hours - remaining_slots
            adjustable_reqs = [r for r in reqs_for_sec if not r.shared]
            adjustable_reqs.sort(key=lambda item: _requirement_priority(item, faculty_availability), reverse=True)
            
            for req in adjustable_reqs:
                if excess <= 0:
                    break
                reduction = min(req.hours, excess)
                idx = requirements.index(req)
                new_hours = req.hours - reduction
                if new_hours > 0:
                    requirements[idx] = Requirement(
                        subject_id=req.subject_id,
                        faculty_id=req.faculty_id,
                        faculty_options=req.faculty_options,
                        sections=req.sections,
                        hours=new_hours,
                        min_consecutive_hours=min(new_hours, req.min_consecutive_hours),
                        max_consecutive_hours=min(new_hours, req.max_consecutive_hours),
                        shared=req.shared,
                        phase=req.phase,
                    )
                else:
                    requirements.pop(idx)
                excess -= reduction

    requirements.sort(key=lambda item: _requirement_priority(item, faculty_availability))


    timeout_seconds = _compute_timeout_seconds(len(all_sections), len(requirements))
    total_deadline = time.perf_counter() + timeout_seconds
    retry_orders: list[tuple[list[str], list[int]]] = [
        (list(DAYS), list(PERIODS)),
        (list(DAYS), list(reversed(PERIODS))),
        (list(reversed(DAYS)), list(PERIODS)),
        (list(reversed(DAYS)), list(reversed(PERIODS))),
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
    per_attempt_budgets = [
        max(10, timeout_seconds // 6),
        max(10, timeout_seconds // 5),
        max(15, timeout_seconds // 4),
        max(15, timeout_seconds // 3),
        timeout_seconds,
    ]

    def _reset_non_lab_assignments() -> None:
        while len(session_log) > initial_log_length:
            session = session_log.pop()
            for period in session["periods"]:
                fac_id = str(session.get("faculty_id", "")).strip()
                if fac_id:
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
            if time.perf_counter() >= attempt_deadline:
                return False
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
                    candidate.faculty_id,
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
                _undo_block(requirement, candidate.faculty_id, placements, schedules, faculty_busy, year, session_log)
            return False

        return backtrack()

    solved = False
    attempt_strategy_names: list[str] = []
    for attempt in range(5):
        if time.perf_counter() >= total_deadline:
            break
        _reset_non_lab_assignments()

        strategy_name, strategy_key = strategy_orderings[min(attempt, len(strategy_orderings) - 1)]
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
        candidate_limit = min(36, 14 + attempt * 6)
        attempt_deadline = min(total_deadline, time.perf_counter() + per_attempt_budgets[attempt])
        if _solve_with_orders(days_order, periods_order, candidate_limit, attempt_deadline):
            solved = True
            break

    if not solved:
        _reset_non_lab_assignments()
        for req_idx, requirement in enumerate(requirements):
            remaining = remaining_by_req.get(req_idx, requirement.hours)
            if remaining <= 0:
                continue
            if not requirement.faculty_id:
                reason = "missing faculty mapping"
            elif time.perf_counter() >= total_deadline:
                reason = "solver timeout"
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

    shared_workbook = _build_shared_classes_workbook(shared_sessions)
    constraint_workbook = _build_constraint_report_workbook(constraint_violations, unscheduled_subjects)

    generated_files = {
        "sharedClassesReport": _encode_workbook("shared_classes_report.xlsx", shared_workbook),
    }
    section_workbook = _build_section_timetables_workbook(year, all_sections, schedules)
    faculty_workbook = _build_faculty_workload_workbook(faculty_workloads, faculty_id_to_name)
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
            "hasValidTimetable": True,
            "hasConstraintViolations": has_constraint_failures,
            "generatedFiles": generated_files,
            "generationMeta": {
                "timeoutSeconds": timeout_seconds,
                "retryStrategies": 5,
                "attemptStrategies": attempt_strategy_names,
                "deterministic": False,
            },
        },
    )

    if has_constraint_failures:
        return {
            "timetableId": timetable_id,
            "message": "Timetable generated with constraint violations. Check Generated Outputs for details.",
        }
    return {"timetableId": timetable_id, "message": "Timetable generated successfully."}

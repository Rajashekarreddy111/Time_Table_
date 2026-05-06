import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.schemas import (  # noqa: E402
    FacultyWeeklyAvailabilityEntry,
    GenerateTimetableRequest,
    ManualEntryMode,
    ManualLabEntry,
    SharedClassEntry,
)
from services.timetable_generator import (  # noqa: E402
    DAYS,
    _allocate_classrooms_to_schedule,
    _build_room_inventory,
    _build_section_strength_map,
    generate_timetable,
)
from storage.memory_store import MemoryStore  # noqa: E402


def _count_filled_slots(grid: dict[str, list[dict | None]]) -> int:
    return sum(1 for day in DAYS for entry in grid[day] if entry is not None)


def _collect_subject_slots(grid: dict[str, list[dict | None]], subject_id: str) -> list[tuple[str, int]]:
    slots: list[tuple[str, int]] = []
    for day in DAYS:
        for period_index, entry in enumerate(grid[day], start=1):
            if entry and entry.get("subject") == subject_id:
                slots.append((day, period_index))
    return slots


def _metadata() -> dict[str, object]:
    return {
        "academicYear": "2026-2027",
        "semester": 2,
        "withEffectFrom": "2026-06-01",
    }


class TimetableSolverTests(unittest.TestCase):
    def test_single_section_keeps_same_room_within_session(self) -> None:
        year = "2nd Year"
        schedules = {
            (year, "A"): {day: {period: None for period in range(1, 8)} for day in DAYS},
        }
        schedules[(year, "A")]["Monday"][1] = {
            "subject": "SUB1",
            "isLab": False,
            "sharedSections": [],
        }
        schedules[(year, "A")]["Monday"][2] = {
            "subject": "SUB2",
            "isLab": False,
            "sharedSections": [],
        }
        session_log = [
            {"day": "Monday", "periods": [1], "sections": ["A"], "isLab": False},
            {"day": "Monday", "periods": [2], "sections": ["A"], "isLab": False},
        ]
        constraint_violations: list[dict] = []

        _allocate_classrooms_to_schedule(
            year,
            ["A"],
            schedules,
            session_log,
            ["C101", "C102"],
            constraint_violations,
            [1, 2, 3, 4, 5, 6, 7],
            [(1, 2), (3, 4), (5, 6, 7)],
            section_strength_map={"A": 30},
        )

        self.assertEqual([], constraint_violations)
        self.assertEqual(
            schedules[(year, "A")]["Monday"][1].get("classroom"),
            schedules[(year, "A")]["Monday"][2].get("classroom"),
        )

    def test_partial_session_shared_class_uses_same_room_only_for_shared_period(self) -> None:
        year = "2nd Year"
        sections = ["A", "B"]
        schedules = {
            (year, "A"): {day: {period: None for period in range(1, 8)} for day in DAYS},
            (year, "B"): {day: {period: None for period in range(1, 8)} for day in DAYS},
        }
        schedules[(year, "A")]["Monday"][1] = {
            "subject": "A1",
            "isLab": False,
            "sharedSections": [],
        }
        schedules[(year, "B")]["Monday"][1] = {
            "subject": "B1",
            "isLab": False,
            "sharedSections": [],
        }
        schedules[(year, "A")]["Monday"][2] = {
            "subject": "SHARED",
            "isLab": False,
            "sharedSections": ["A", "B"],
        }
        schedules[(year, "B")]["Monday"][2] = {
            "subject": "SHARED",
            "isLab": False,
            "sharedSections": ["A", "B"],
        }
        session_log = [
            {"day": "Monday", "periods": [1], "sections": ["A"], "isLab": False},
            {"day": "Monday", "periods": [1], "sections": ["B"], "isLab": False},
            {"day": "Monday", "periods": [2], "sections": ["A", "B"], "isLab": False},
        ]
        constraint_violations: list[dict] = []

        _allocate_classrooms_to_schedule(
            year,
            sections,
            schedules,
            session_log,
            ["C101", "C102", "C103"],
            constraint_violations,
            [1, 2, 3, 4, 5, 6, 7],
            [(1, 2), (3, 4), (5, 6, 7)],
            section_strength_map={"A": 30, "B": 30},
        )

        self.assertEqual([], constraint_violations)
        self.assertNotEqual(
            schedules[(year, "A")]["Monday"][1].get("classroom"),
            schedules[(year, "B")]["Monday"][1].get("classroom"),
        )
        self.assertEqual(
            schedules[(year, "A")]["Monday"][2].get("classroom"),
            schedules[(year, "B")]["Monday"][2].get("classroom"),
        )

    def test_strength_can_push_allocation_to_lab_room_when_needed(self) -> None:
        year = "2nd Year"
        schedules = {
            (year, "A"): {day: {period: None for period in range(1, 8)} for day in DAYS},
        }
        schedules[(year, "A")]["Monday"][1] = {
            "subject": "BIG",
            "isLab": False,
            "sharedSections": [],
        }
        schedules[(year, "A")]["Monday"][2] = {
            "subject": "BIG2",
            "isLab": False,
            "sharedSections": [],
        }
        session_log = [
            {"day": "Monday", "periods": [1], "sections": ["A"], "isLab": False},
            {"day": "Monday", "periods": [2], "sections": ["A"], "isLab": False},
        ]
        constraint_violations: list[dict] = []

        _allocate_classrooms_to_schedule(
            year,
            ["A"],
            schedules,
            session_log,
            ["C101", "L201"],
            constraint_violations,
            [1, 2, 3, 4, 5, 6, 7],
            [(1, 2), (3, 4), (5, 6, 7)],
            lab_room_names={"L201"},
            room_capacity_map={"C101": 60, "L201": 80},
            section_strength_map={"2nd Year|A": 75},
        )

        self.assertEqual([], constraint_violations)
        self.assertEqual("L201", schedules[(year, "A")]["Monday"][1].get("classroom"))
        self.assertEqual("L201", schedules[(year, "A")]["Monday"][2].get("classroom"))

    def test_classroom_template_2c1_section_maps_strength_from_same_file(self) -> None:
        store = MemoryStore()
        store.save_scoped_mapping(
            "classrooms",
            "global",
            {
                "rows": [
                    {"class_number": "1101", "room_type": "classroom", "capacity": 75, "section": "2C1", "strength": 70},
                    {"class_number": "1108", "room_type": "classroom", "capacity": 170, "section": "2G1", "strength": 70},
                    {"class_number": "2301", "room_type": "lab", "capacity": "", "section": "3C4", "strength": 70},
                ]
            },
            allow_overwrite=True,
        )
        request = GenerateTimetableRequest(
            year="2nd Year",
            section="C1",
            timetableMetadata=_metadata(),
        )

        room_inventory = _build_room_inventory(request, store)
        section_strength_map = _build_section_strength_map(request, store)

        self.assertEqual(70, section_strength_map.get("2nd Year|C1"))
        self.assertEqual("1101", room_inventory[0].get("name"))
        self.assertEqual(75, room_inventory[0].get("capacity"))

    def test_post_allocation_assigns_classroom_and_keeps_continuous_block_room(self) -> None:
        store = MemoryStore()
        store.save_scoped_mapping(
            "classrooms",
            "global",
            {"rows": [{"class_number": "C101"}, {"class_number": "C102"}]},
            allow_overwrite=True,
        )
        request = GenerateTimetableRequest(
            year="2nd Year",
            section="A",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="BLOCK",
                    facultyId="FBLOCK",
                    noOfHours=2,
                    continuousHours=2,
                    compulsoryContinuousHours=2,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="FILL",
                    facultyId="FFILL",
                    noOfHours=40,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
            ],
        )

        result = generate_timetable(request, store)
        payload = store.get_timetable(result["timetableId"])

        self.assertTrue(payload["hasValidTimetable"])
        self.assertEqual([], [v for v in payload["constraintViolations"] if v.get("constraint") == "classroom allocation constraint"])

        grid = payload["allGrids"]["A"]
        block_slots = _collect_subject_slots(grid, "BLOCK")
        self.assertEqual(2, len(block_slots))
        block_rooms = {
            grid[day][period - 1].get("classroom")
            for day, period in block_slots
            if grid[day][period - 1]
        }
        self.assertEqual({"C101"}, block_rooms)

        for day in DAYS:
            for cell in grid[day]:
                if not cell or cell.get("isLab"):
                    continue
                self.assertTrue(cell.get("classroom"))

    def test_post_allocation_reports_insufficient_classrooms(self) -> None:
        store = MemoryStore()
        store.save_scoped_mapping(
            "classrooms",
            "global",
            {"rows": [{"class_number": "C101"}]},
            allow_overwrite=True,
        )
        request = GenerateTimetableRequest(
            year="2nd Year",
            section="A",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="A_MAIN",
                    facultyId="FA",
                    noOfHours=42,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="B",
                    subjectId="B_MAIN",
                    facultyId="FB",
                    noOfHours=42,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
            ],
        )

        result = generate_timetable(request, store)
        payload = store.get_timetable(result["timetableId"])

        classroom_violations = [
            v for v in payload["constraintViolations"]
            if v.get("constraint") == "classroom allocation constraint"
        ]
        self.assertGreater(len(classroom_violations), 0)

    def test_solver_does_not_auto_group_matching_subjects_across_sections(self) -> None:
        store = MemoryStore()
        request = GenerateTimetableRequest(
            year="2nd Year",
            section="A",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="GLOBAL",
                    facultyId="VERBAL_POOL",
                    noOfHours=2,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="B",
                    subjectId="GLOBAL",
                    facultyId="VERBAL_POOL",
                    noOfHours=2,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="A_FILL",
                    facultyId="FA",
                    noOfHours=40,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="B",
                    subjectId="B_FILL",
                    facultyId="FB",
                    noOfHours=40,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
            ],
            facultyIdNameMapping=[
                {"facultyId": "FVA", "facultyName": "VERBAL_POOL Alpha"},
                {"facultyId": "FVB", "facultyName": "VERBAL_POOL Beta"},
            ],
            facultyAvailability=[
                FacultyWeeklyAvailabilityEntry(
                    facultyId="FVA",
                    availablePeriodsByDay={
                        "Monday": [1, 2],
                        "Tuesday": [],
                        "Wednesday": [],
                        "Thursday": [],
                        "Friday": [],
                        "Saturday": [],
                    },
                ),
                FacultyWeeklyAvailabilityEntry(
                    facultyId="FVB",
                    availablePeriodsByDay={
                        "Monday": [],
                        "Tuesday": [1, 2],
                        "Wednesday": [],
                        "Thursday": [],
                        "Friday": [],
                        "Saturday": [],
                    },
                )
            ],
        )

        result = generate_timetable(request, store)
        payload = store.get_timetable(result["timetableId"])

        self.assertTrue(payload["hasValidTimetable"])
        self.assertEqual([], payload["sharedClasses"])
        self.assertEqual(42, _count_filled_slots(payload["allGrids"]["A"]))
        self.assertEqual(42, _count_filled_slots(payload["allGrids"]["B"]))
        self.assertEqual(2, len(_collect_subject_slots(payload["allGrids"]["A"], "GLOBAL")))
        self.assertEqual(2, len(_collect_subject_slots(payload["allGrids"]["B"], "GLOBAL")))

    def test_solver_prioritizes_scarce_slots_over_high_hour_subject(self) -> None:
        store = MemoryStore()
        request = GenerateTimetableRequest(
            year="2nd Year",
            section="A",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="FLEX",
                    facultyId="F3",
                    noOfHours=40,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="LIMITED_MON",
                    facultyId="F1",
                    noOfHours=1,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="LIMITED_TUE",
                    facultyId="F2",
                    noOfHours=1,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
            ],
            facultyAvailability=[
                FacultyWeeklyAvailabilityEntry(
                    facultyId="F1",
                    availablePeriodsByDay={
                        "Monday": [1],
                        "Tuesday": [],
                        "Wednesday": [],
                        "Thursday": [],
                        "Friday": [],
                        "Saturday": [],
                    },
                ),
                FacultyWeeklyAvailabilityEntry(
                    facultyId="F2",
                    availablePeriodsByDay={
                        "Monday": [],
                        "Tuesday": [1],
                        "Wednesday": [],
                        "Thursday": [],
                        "Friday": [],
                        "Saturday": [],
                    },
                ),
            ],
        )

        result = generate_timetable(request, store)
        payload = store.get_timetable(result["timetableId"])

        self.assertTrue(payload["hasValidTimetable"])
        self.assertEqual([], payload["constraintViolations"])
        self.assertEqual([], payload["unscheduledSubjects"])
        self.assertEqual(30, payload["generationMeta"]["timeoutSeconds"])  # §18: small config ≤5 sections = 30s
        self.assertEqual(5, payload["generationMeta"]["retryStrategies"])
        self.assertIn("shared-first", payload["generationMeta"]["attemptStrategies"])
        self.assertEqual(42, _count_filled_slots(payload["allGrids"]["A"]))
        self.assertEqual("LIMITED_MON", payload["allGrids"]["A"]["Monday"][0]["subject"])
        self.assertEqual("LIMITED_TUE", payload["allGrids"]["A"]["Tuesday"][0]["subject"])

    def test_solver_generates_full_timetable_with_locked_and_shared_sessions(self) -> None:
        store = MemoryStore()
        request = GenerateTimetableRequest(
            year="3rd Year",
            section="A",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="3rd Year",
                    section="A",
                    subjectId="LABSH",
                    facultyId="FLAB",
                    noOfHours=3,
                    continuousHours=3,
                    compulsoryContinuousHours=3,
                ),
                ManualEntryMode(
                    year="3rd Year",
                    section="B",
                    subjectId="LABSH",
                    facultyId="FLAB",
                    noOfHours=3,
                    continuousHours=3,
                    compulsoryContinuousHours=3,
                ),
                ManualEntryMode(
                    year="3rd Year",
                    section="A",
                    subjectId="SHARED",
                    facultyId="FSH",
                    noOfHours=3,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="3rd Year",
                    section="B",
                    subjectId="SHARED",
                    facultyId="FSH",
                    noOfHours=3,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="3rd Year",
                    section="A",
                    subjectId="A_ONLY",
                    facultyId="FA",
                    noOfHours=36,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="3rd Year",
                    section="B",
                    subjectId="B_ONLY",
                    facultyId="FB",
                    noOfHours=36,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
            ],
            manualLabEntries=[
                ManualLabEntry(year="3rd Year", section="A", subjectId="LABSH", day=1, hours=[1, 2, 3], venue="Lab 1"),
                ManualLabEntry(year="3rd Year", section="B", subjectId="LABSH", day=1, hours=[1, 2, 3], venue="Lab 1"),
            ],
            sharedClasses=[SharedClassEntry(year="3rd Year", sections=["A", "B"], subject="SHARED")],
            facultyAvailability=[
                FacultyWeeklyAvailabilityEntry(
                    facultyId="FLAB",
                    availablePeriodsByDay={
                        "Monday": [1, 2, 3],
                        "Tuesday": [],
                        "Wednesday": [],
                        "Thursday": [],
                        "Friday": [],
                        "Saturday": [],
                    },
                ),
                FacultyWeeklyAvailabilityEntry(
                    facultyId="FSH",
                    availablePeriodsByDay={
                        "Monday": [],
                        "Tuesday": [1, 2, 3],
                        "Wednesday": [],
                        "Thursday": [],
                        "Friday": [],
                        "Saturday": [],
                    },
                ),
            ],
        )

        result = generate_timetable(request, store)
        payload = store.get_timetable(result["timetableId"])

        self.assertTrue(payload["hasValidTimetable"])
        self.assertEqual(42, _count_filled_slots(payload["allGrids"]["A"]))
        self.assertEqual(42, _count_filled_slots(payload["allGrids"]["B"]))
        self.assertEqual("LABSH", payload["allGrids"]["A"]["Monday"][0]["subject"])
        self.assertEqual("LABSH", payload["allGrids"]["B"]["Monday"][0]["subject"])
        shared_subjects = {item["subject_id"] for item in payload["sharedClasses"]}
        self.assertIn("LABSH", shared_subjects)
        self.assertIn("SHARED", shared_subjects)
        self.assertEqual([], payload["constraintViolations"])
        self.assertIn("sectionTimetables", payload["generatedFiles"])
        self.assertIn("facultyWorkload", payload["generatedFiles"])
        self.assertIn("sharedClassesReport", payload["generatedFiles"])

    def test_solver_resets_state_between_year_runs(self) -> None:
        store = MemoryStore()
        year_one = GenerateTimetableRequest(
            year="1st Year",
            section="A",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="1st Year",
                    section="A",
                    subjectId="Y1_MAIN",
                    facultyId="F_SHARED",
                    noOfHours=42,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                )
            ],
        )
        year_two = GenerateTimetableRequest(
            year="2nd Year",
            section="A",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="2nd Year",
                    section="A",
                    subjectId="Y2_MAIN",
                    facultyId="F_SHARED",
                    noOfHours=42,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                )
            ],
        )

        first_result = generate_timetable(year_one, store)
        second_result = generate_timetable(year_two, store)
        first_payload = store.get_timetable(first_result["timetableId"])
        second_payload = store.get_timetable(second_result["timetableId"])

        self.assertTrue(first_payload["hasValidTimetable"])
        self.assertTrue(second_payload["hasValidTimetable"])
        self.assertEqual(42, _count_filled_slots(second_payload["allGrids"]["A"]))


    def test_lab_shared_session_no_false_faculty_conflict(self) -> None:
        """
        Requirement §10: Faculty teaching multiple sections the SAME lab at the
        same time is VALID. This must not produce a faculty conflict violation.
        C4 and C5 both have Lab FL1 with faculty FLAB, Monday P3+P4.
        Expected: no constraint violations, one shared lab entry in sharedClasses.
        """
        store = MemoryStore()
        request = GenerateTimetableRequest(
            year="2nd Year",
            section="C4",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="2nd Year",
                    section="C4",
                    subjectId="FL1",
                    facultyId="FLAB",
                    noOfHours=2,
                    continuousHours=2,
                    compulsoryContinuousHours=2,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="C4",
                    subjectId="FILL_C4",
                    facultyId="FA",
                    noOfHours=40,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="C5",
                    subjectId="FL1",
                    facultyId="FLAB",
                    noOfHours=2,
                    continuousHours=2,
                    compulsoryContinuousHours=2,
                ),
                ManualEntryMode(
                    year="2nd Year",
                    section="C5",
                    subjectId="FILL_C5",
                    facultyId="FB",
                    noOfHours=40,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
            ],
            manualLabEntries=[
                ManualLabEntry(year="2nd Year", section="C4", subjectId="FL1", day=1, hours=[3, 4]),
                ManualLabEntry(year="2nd Year", section="C5", subjectId="FL1", day=1, hours=[3, 4]),
            ],
        )

        result = generate_timetable(request, store)
        payload = store.get_timetable(result["timetableId"])

        # No faculty conflicts — same faculty same session across two sections is valid
        faculty_conflict_violations = [
            v for v in payload["constraintViolations"]
            if "faculty" in v.get("constraint", "").lower()
        ]
        self.assertEqual([], faculty_conflict_violations, f"Unexpected faculty conflicts: {faculty_conflict_violations}")

        # The lab session should appear in sharedClasses (source = "lab")
        lab_shared = [s for s in payload["sharedClasses"] if s.get("subject_id") == "FL1"]
        self.assertGreater(len(lab_shared), 0, "FL1 lab should appear in shared class report")

        # Both sections should be in the shared entry
        for entry in lab_shared:
            self.assertIn("C4", entry.get("sections", []))
            self.assertIn("C5", entry.get("sections", []))

        # Both sections fully scheduled
        self.assertTrue(payload["hasValidTimetable"])

    def test_shared_report_only_contains_file_driven_sessions(self) -> None:
        """
        Requirement §21: The shared class report must NEVER include auto-detected
        sessions. Two sections with the same subject + same faculty should NOT
        appear in sharedClasses unless explicitly declared in the shared class file.
        """
        store = MemoryStore()
        # Two sections X and Y both have COMMON taught by FCOMMON — but NO shared class declaration
        request = GenerateTimetableRequest(
            year="3rd Year",
            section="X",
            timetableMetadata=_metadata(),
            manualEntries=[
                ManualEntryMode(
                    year="3rd Year",
                    section="X",
                    subjectId="COMMON",
                    facultyId="FCOMMON",
                    noOfHours=2,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="3rd Year",
                    section="X",
                    subjectId="FILL_X",
                    facultyId="FX",
                    noOfHours=40,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="3rd Year",
                    section="Y",
                    subjectId="COMMON",
                    facultyId="FCOMMON",
                    noOfHours=2,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
                ManualEntryMode(
                    year="3rd Year",
                    section="Y",
                    subjectId="FILL_Y",
                    facultyId="FY",
                    noOfHours=40,
                    continuousHours=1,
                    compulsoryContinuousHours=1,
                ),
            ],
            # NO sharedClasses entry for COMMON — it must NOT appear in shared report
        )

        result = generate_timetable(request, store)
        payload = store.get_timetable(result["timetableId"])

        # COMMON must NOT appear in the shared class report (it's solver-placed, not file-driven)
        common_in_shared = [s for s in payload["sharedClasses"] if s.get("subject_id") == "COMMON"]
        self.assertEqual(
            [],
            common_in_shared,
            f"COMMON was auto-detected as shared — this is wrong! Entries: {common_in_shared}",
        )
        self.assertTrue(payload["hasValidTimetable"])


if __name__ == "__main__":
    unittest.main()

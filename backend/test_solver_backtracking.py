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
from services.timetable_generator import DAYS, generate_timetable  # noqa: E402
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


class TimetableSolverTests(unittest.TestCase):
    def test_solver_does_not_auto_group_matching_subjects_across_sections(self) -> None:
        store = MemoryStore()
        request = GenerateTimetableRequest(
            year="2nd Year",
            section="A",
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
        self.assertEqual(60, payload["generationMeta"]["timeoutSeconds"])
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


if __name__ == "__main__":
    unittest.main()

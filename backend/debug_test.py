import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.schemas import (
    GenerateTimetableRequest,
    ManualEntryMode,
    ManualLabEntry,
)
from services.timetable_generator import generate_timetable
from storage.memory_store import MemoryStore


def test_lab_conflict():
    store = MemoryStore()
    request = GenerateTimetableRequest(
        year="2nd Year",
        section="C4",
        manualEntries=[
            ManualEntryMode(year="2nd Year", section="C4", subjectId="FL1", facultyId="FLAB", noOfHours=2, continuousHours=2, compulsoryContinuousHours=2),
            ManualEntryMode(year="2nd Year", section="C4", subjectId="FILL_C4", facultyId="FA", noOfHours=40, continuousHours=1, compulsoryContinuousHours=1),
            ManualEntryMode(year="2nd Year", section="C5", subjectId="FL1", facultyId="FLAB", noOfHours=2, continuousHours=2, compulsoryContinuousHours=2),
            ManualEntryMode(year="2nd Year", section="C5", subjectId="FILL_C5", facultyId="FB", noOfHours=40, continuousHours=1, compulsoryContinuousHours=1),
        ],
        manualLabEntries=[
            ManualLabEntry(year="2nd Year", section="C4", subjectId="FL1", day=1, hours=[3, 4]),
            ManualLabEntry(year="2nd Year", section="C5", subjectId="FL1", day=1, hours=[3, 4]),
        ],
    )
    result = generate_timetable(request, store)
    payload = store.get_timetable(result["timetableId"])
    print("hasValidTimetable:", payload["hasValidTimetable"])
    print("constraintViolations:", payload["constraintViolations"])
    print("unscheduledSubjects:", payload["unscheduledSubjects"])
    print("sharedClasses:", payload["sharedClasses"])
    fl1_shared = [s for s in payload["sharedClasses"] if s.get("subject_id") == "FL1"]
    print("FL1 in sharedClasses:", fl1_shared)
    print("All sections:", list(payload["allGrids"].keys()))


test_lab_conflict()
print("DONE")

import unittest

from services.faculty_availability import get_bulk_available_faculty
from storage.memory_store import MemoryStore


class FacultyAvailabilityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryStore()

    def test_bulk_selection_is_fairly_rotated(self) -> None:
        workload_rows = []
        for faculty_name in ["A.Aparna", "B.Ramesh", "C.Sujatha"]:
            for day in ["Monday", "Tuesday", "Wednesday"]:
                for period in [1, 2]:
                    workload_rows.append(
                        {
                            "faculty_id": faculty_name,
                            "faculty_name": faculty_name,
                            "day": day,
                            "period": period,
                            "year": "",
                            "section": "",
                            "subject": "",
                            "is_available": True,
                        }
                    )

        self.store.save_file_map(
            "favail_test",
            {"id": "favail_test", "rows": workload_rows},
        )
        self.store.save_file_map(
            "fquery_test",
            {
                "id": "fquery_test",
                "rows": [
                    {"date": "2026-03-23", "facultyRequired": 2, "periods": [1]},
                    {"date": "2026-03-24", "facultyRequired": 2, "periods": [1]},
                    {"date": "2026-03-25", "facultyRequired": 2, "periods": [1]},
                ],
            },
        )

        result = get_bulk_available_faculty(
            store=self.store,
            availability_file_id="favail_test",
            query_file_id="fquery_test",
            ignored_years=[],
            ignored_sections=[],
            faculty_id_map_file_id=None,
        )

        counts = {"A.Aparna": 0, "B.Ramesh": 0, "C.Sujatha": 0}
        for row in result["results"]:
            for faculty in row["faculty"]:
                counts[faculty] += 1

        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_insufficient_faculty_returns_shortage_details(self) -> None:
        self.store.save_file_map(
            "favail_short",
            {
                "id": "favail_short",
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Monday",
                        "period": 1,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                    {
                        "faculty_id": "B.Ramesh",
                        "faculty_name": "B.Ramesh",
                        "day": "Monday",
                        "period": 1,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                ],
            },
        )
        self.store.save_file_map(
            "fquery_short",
            {
                "id": "fquery_short",
                "rows": [
                    {"date": "2026-03-23", "facultyRequired": 4, "periods": [1]},
                ],
            },
        )

        result = get_bulk_available_faculty(
            store=self.store,
            availability_file_id="favail_short",
            query_file_id="fquery_short",
            ignored_years=[],
            ignored_sections=[],
            faculty_id_map_file_id=None,
        )

        item = result["results"][0]
        self.assertEqual(item["availableFacultyCount"], 2)
        self.assertFalse(item["sufficientFaculty"])
        self.assertEqual(item["shortageCount"], 2)
        self.assertIn("No sufficient faculty available", item["message"])


if __name__ == "__main__":
    unittest.main()

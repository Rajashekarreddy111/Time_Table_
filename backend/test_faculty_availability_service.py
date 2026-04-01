import unittest
from datetime import time

from fastapi import HTTPException

from services.faculty_availability import (
    get_bulk_available_faculty,
    get_available_faculty_for_all_periods,
    _build_schedules_from_upload,
    _is_faculty_free_for_period,
    _resolve_periods_from_time_range,
)
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

    def test_time_range_includes_partially_overlapping_period(self) -> None:
        self.assertEqual(_resolve_periods_from_time_range("2:00", "4:00"), [5, 6, 7])

    def test_time_range_accepts_excel_time_cells(self) -> None:
        self.assertEqual(_resolve_periods_from_time_range(time(14, 0), time(15, 0)), [5, 6])

    def test_bulk_query_marks_faculty_busy_when_time_range_overlaps_period(self) -> None:
        self.store.save_file_map(
            "favail_overlap",
            {
                "id": "favail_overlap",
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 5,
                        "year": "II Year",
                        "section": "C1",
                        "subject": "Maths",
                        "is_available": False,
                    },
                    {
                        "faculty_id": "B.Ramesh",
                        "faculty_name": "B.Ramesh",
                        "day": "Thursday",
                        "period": 5,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                    {
                        "faculty_id": "B.Ramesh",
                        "faculty_name": "B.Ramesh",
                        "day": "Thursday",
                        "period": 6,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                    {
                        "faculty_id": "B.Ramesh",
                        "faculty_name": "B.Ramesh",
                        "day": "Thursday",
                        "period": 7,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                ],
            },
        )
        self.store.save_file_map(
            "fquery_overlap",
            {
                "id": "fquery_overlap",
                "rows": [
                    {
                        "date": "2026-03-26",
                        "facultyRequired": 1,
                        "periods": [],
                        "startTime": "2:00",
                        "endTime": "4:00",
                    },
                ],
            },
        )

        result = get_bulk_available_faculty(
            store=self.store,
            availability_file_id="favail_overlap",
            query_file_id="fquery_overlap",
            ignored_years=[],
            ignored_sections=[],
            faculty_id_map_file_id=None,
        )

        item = result["results"][0]
        self.assertEqual([period["period"] for period in item["periods"]], [5, 6, 7])
        self.assertEqual(item["faculty"], ["B.Ramesh"])
        self.assertEqual(item["availableFacultyCount"], 1)

    def test_unknown_faculty_day_does_not_default_to_free(self) -> None:
        self.store.save_file_map(
            "favail_modes",
            {
                "id": "favail_modes",
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 5,
                        "year": "II Year",
                        "section": "C1",
                        "subject": "Maths",
                        "is_available": False,
                    },
                ],
            },
        )
        schedules, explicit_free_days, schedule_modes = _build_schedules_from_upload(
            self.store,
            "favail_modes",
            {},
        )

        self.assertFalse(
            _is_faculty_free_for_period(
                "A.Aparna",
                "Friday",
                5,
                schedules,
                explicit_free_days,
                schedule_modes,
                [],
                [],
            )
        )

    def test_known_occupancy_day_still_treats_missing_period_as_free(self) -> None:
        self.store.save_file_map(
            "favail_occupancy_mode",
            {
                "id": "favail_occupancy_mode",
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 5,
                        "year": "II Year",
                        "section": "C1",
                        "subject": "Maths",
                        "is_available": False,
                    },
                ],
            },
        )
        schedules, explicit_free_days, schedule_modes = _build_schedules_from_upload(
            self.store,
            "favail_occupancy_mode",
            {},
        )

        self.assertTrue(
            _is_faculty_free_for_period(
                "A.Aparna",
                "Thursday",
                6,
                schedules,
                explicit_free_days,
                schedule_modes,
                [],
                [],
            )
        )

    def test_explicit_file_id_is_used_even_when_global_mapping_exists(self) -> None:
        self.store.save_scoped_mapping(
            "faculty_availability",
            "global",
            {
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 5,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 6,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 7,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                ],
            },
            allow_overwrite=True,
        )
        self.store.save_file_map(
            "favail_busy_specific",
            {
                "id": "favail_busy_specific",
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 5,
                        "year": "II Year",
                        "section": "C1",
                        "subject": "Maths",
                        "is_available": False,
                    },
                ],
            },
        )
        self.store.save_file_map(
            "fquery_specific",
            {
                "id": "fquery_specific",
                "rows": [
                    {
                        "date": "2026-03-26",
                        "facultyRequired": 1,
                        "periods": [],
                        "startTime": "2:00",
                        "endTime": "4:00",
                    },
                ],
            },
        )

        result = get_bulk_available_faculty(
            store=self.store,
            availability_file_id="favail_busy_specific",
            query_file_id="fquery_specific",
            ignored_years=[],
            ignored_sections=[],
            faculty_id_map_file_id=None,
        )

        self.assertEqual(result["results"][0]["faculty"], [])

    def test_mixed_modes_for_same_faculty_day_are_rejected(self) -> None:
        self.store.save_file_map(
            "favail_mixed_mode",
            {
                "id": "favail_mixed_mode",
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 5,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 6,
                        "year": "II Year",
                        "section": "C1",
                        "subject": "Maths",
                        "is_available": False,
                    },
                ],
            },
        )

        with self.assertRaises(HTTPException) as exc:
            _build_schedules_from_upload(self.store, "favail_mixed_mode", {})

        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("Mixed faculty availability dataset detected", str(exc.exception.detail))

    def test_bulk_query_rejects_rows_without_periods_or_time_range(self) -> None:
        self.store.save_file_map(
            "favail_empty_periods",
            {
                "id": "favail_empty_periods",
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
                ],
            },
        )
        self.store.save_file_map(
            "fquery_empty_periods",
            {
                "id": "fquery_empty_periods",
                "rows": [
                    {"date": "2026-03-23", "facultyRequired": 1, "periods": []},
                ],
            },
        )

        with self.assertRaises(HTTPException) as exc:
            get_bulk_available_faculty(
                store=self.store,
                availability_file_id="favail_empty_periods",
                query_file_id="fquery_empty_periods",
                ignored_years=[],
                ignored_sections=[],
                faculty_id_map_file_id=None,
            )

        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("At least one period must be selected", str(exc.exception.detail))

    def test_single_query_supports_time_range_without_periods(self) -> None:
        self.store.save_file_map(
            "favail_single_time",
            {
                "id": "favail_single_time",
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 5,
                        "year": "II Year",
                        "section": "C1",
                        "subject": "Maths",
                        "is_available": False,
                    },
                    {
                        "faculty_id": "B.Ramesh",
                        "faculty_name": "B.Ramesh",
                        "day": "Thursday",
                        "period": 5,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                    {
                        "faculty_id": "B.Ramesh",
                        "faculty_name": "B.Ramesh",
                        "day": "Thursday",
                        "period": 6,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                    {
                        "faculty_id": "B.Ramesh",
                        "faculty_name": "B.Ramesh",
                        "day": "Thursday",
                        "period": 7,
                        "year": "",
                        "section": "",
                        "subject": "",
                        "is_available": True,
                    },
                ],
            },
        )

        result = get_available_faculty_for_all_periods(
            store=self.store,
            date_value="2026-03-26",
            periods=[],
            start_time="2:00",
            end_time="4:00",
            faculty_required=1,
            ignored_years=[],
            ignored_sections=[],
            availability_file_id="favail_single_time",
            faculty_id_map_file_id=None,
        )

        self.assertEqual([period["period"] for period in result["periods"]], [5, 6, 7])
        self.assertEqual(result["faculty"], ["B.Ramesh"])

    def test_occupancy_dataset_treats_missing_day_as_free_for_known_faculty(self) -> None:
        self.store.save_file_map(
            "favail_missing_day",
            {
                "id": "favail_missing_day",
                "facultyNames": ["A.Aparna", "B.Ramesh"],
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Thursday",
                        "period": 5,
                        "year": "II Year",
                        "section": "C1",
                        "subject": "Maths",
                        "is_available": False,
                    },
                ],
            },
        )

        result = get_available_faculty_for_all_periods(
            store=self.store,
            date_value="2026-03-27",
            periods=[5],
            start_time=None,
            end_time=None,
            faculty_required=2,
            ignored_years=[],
            ignored_sections=[],
            availability_file_id="favail_missing_day",
            faculty_id_map_file_id=None,
        )

        self.assertEqual(result["faculty"], ["A.Aparna", "B.Ramesh"])

    def test_known_faculty_without_rows_is_still_considered_in_workload_mode(self) -> None:
        self.store.save_file_map(
            "favail_known_faculty",
            {
                "id": "favail_known_faculty",
                "facultyNames": ["A.Aparna", "B.Ramesh", "C.Sujatha"],
                "rows": [
                    {
                        "faculty_id": "A.Aparna",
                        "faculty_name": "A.Aparna",
                        "day": "Saturday",
                        "period": 5,
                        "year": "II Year",
                        "section": "C1",
                        "subject": "Maths",
                        "is_available": False,
                    },
                    {
                        "faculty_id": "B.Ramesh",
                        "faculty_name": "B.Ramesh",
                        "day": "Saturday",
                        "period": 5,
                        "year": "II Year",
                        "section": "C2",
                        "subject": "Physics",
                        "is_available": False,
                    },
                ],
            },
        )

        result = get_available_faculty_for_all_periods(
            store=self.store,
            date_value="2026-03-28",
            periods=[5],
            start_time=None,
            end_time=None,
            faculty_required=1,
            ignored_years=[],
            ignored_sections=[],
            availability_file_id="favail_known_faculty",
            faculty_id_map_file_id=None,
        )

        self.assertEqual(result["faculty"], ["C.Sujatha"])


if __name__ == "__main__":
    unittest.main()

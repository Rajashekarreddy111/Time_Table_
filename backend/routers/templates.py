from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from services.file_parser import create_excel_template, create_grouped_main_timetable_template

router = APIRouter(tags=["templates"])


def _template_response(
    file_name: str,
    records: list[dict],
    template_type: Literal["example", "empty"],
) -> StreamingResponse:
    content = create_excel_template(records, include_example_rows=template_type == "example")
    stream = BytesIO(content)
    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def _grouped_template_response(
    file_name: str,
    records: list[dict],
    template_type: Literal["example", "empty"],
) -> StreamingResponse:
    content = create_grouped_main_timetable_template(records, include_example_rows=template_type == "example")
    stream = BytesIO(content)
    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/templates/main-timetable-config")
async def main_timetable_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _grouped_template_response(
        "main-timetable-template.xlsx",
        [
            {
                "YEAR": "2",
                "SUBJECT_ID": "2",
                "C1_HOURS": 4,
                "C1_FACULTY_ID": "5",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 4,
                "C2_FACULTY_ID": "5",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 4,
                "C3_FACULTY_ID": "6",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "3",
                "C1_HOURS": 4,
                "C1_FACULTY_ID": "40",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 4,
                "C2_FACULTY_ID": "40",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 4,
                "C3_FACULTY_ID": "19",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "4",
                "C1_HOURS": 4,
                "C1_FACULTY_ID": "10",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 4,
                "C2_FACULTY_ID": "3",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 4,
                "C3_FACULTY_ID": "12",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "5",
                "C1_HOURS": 3,
                "C1_FACULTY_ID": "28",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 3,
                "C2_FACULTY_ID": "38",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 3,
                "C3_FACULTY_ID": "1",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "6",
                "C1_HOURS": 1,
                "C1_FACULTY_ID": "11",
                "C1_CONTINUOUS_HOURS": 1,
                "C2_HOURS": 1,
                "C2_FACULTY_ID": "38,11",
                "C2_CONTINUOUS_HOURS": 1,
                "C3_HOURS": 1,
                "C3_FACULTY_ID": "11,31",
                "C3_CONTINUOUS_HOURS": 1,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "7",
                "C1_HOURS": 2,
                "C1_FACULTY_ID": "3",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 2,
                "C2_FACULTY_ID": "2",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 2,
                "C3_FACULTY_ID": "2",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "8",
                "C1_HOURS": 2,
                "C1_FACULTY_ID": "10",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 2,
                "C2_FACULTY_ID": "3",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 2,
                "C3_FACULTY_ID": "12",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "9",
                "C1_HOURS": 3,
                "C1_FACULTY_ID": "34",
                "C1_CONTINUOUS_HOURS": 3,
                "C2_HOURS": 3,
                "C2_FACULTY_ID": "34",
                "C2_CONTINUOUS_HOURS": 3,
                "C3_HOURS": 3,
                "C3_FACULTY_ID": "10",
                "C3_CONTINUOUS_HOURS": 3,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "10",
                "C1_HOURS": 2,
                "C1_FACULTY_ID": "40",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 2,
                "C2_FACULTY_ID": "40",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 2,
                "C3_FACULTY_ID": "19",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "11",
                "C1_HOURS": 4,
                "C1_FACULTY_ID": "53",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 4,
                "C2_FACULTY_ID": "53",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 4,
                "C3_FACULTY_ID": "54",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "12",
                "C1_HOURS": 4,
                "C1_FACULTY_ID": "50",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 4,
                "C2_FACULTY_ID": "50",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 4,
                "C3_FACULTY_ID": "51",
                "C3_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "21",
                "C1_HOURS": 4,
                "C1_FACULTY_ID": "48",
                "C1_CONTINUOUS_HOURS": 4,
                "C2_HOURS": 4,
                "C2_FACULTY_ID": "48",
                "C2_CONTINUOUS_HOURS": 4,
                "C3_HOURS": 4,
                "C3_FACULTY_ID": "49",
                "C3_CONTINUOUS_HOURS": 4,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "1",
                "C1_HOURS": 3,
                "C1_FACULTY_ID": "32",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 3,
                "C2_FACULTY_ID": "15",
                "C2_CONTINUOUS_HOURS": 2,
                "C3_HOURS": 3,
                "C3_FACULTY_ID": "32",
                "C3_CONTINUOUS_HOURS": 2,
            },
        ],
        template_type,
    )


@router.get("/templates/lab-timetable")
async def lab_timetable_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _template_response(
        "lab-timetable-template.xlsx",
        [
            {"YEAR": "2", "SECTION": "C1", "SUBJECT_ID": "7", "DAY": "1", "HOURS": "1,2", "VENUE": "2201"},
            {"YEAR": "2", "SECTION": "C2", "SUBJECT_ID": "10", "DAY": "1", "HOURS": "3,4", "VENUE": "2202"},
        ],
        template_type,
    )


@router.get("/templates/subject-id-mapping")
async def subject_id_mapping_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _template_response(
        "subject-id-mapping-template.xlsx",
        [
            {"SUBJECT_ID": "7", "SUBJECT_NAME": "Data Structures"},
            {"SUBJECT_ID": "10", "SUBJECT_NAME": "DBMS"},
        ],
        template_type,
    )


@router.get("/templates/subject-continuous-rules")
async def subject_continuous_rules_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _template_response(
        "subject-continuous-rules-template.xlsx",
        [
            {"SUBJECT_ID": "7", "COMPULSORY_CONTINUOUS_HOURS": 2},
            {"SUBJECT_ID": "10", "COMPULSORY_CONTINUOUS_HOURS": 3},
        ],
        template_type,
    )


@router.get("/templates/faculty-id-map")
async def faculty_id_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _template_response(
        "faculty-id-map-template.xlsx",
        [
            {"faculty name": "faculty-1", "id assigned": "F001"},
            {"faculty name": "faculty-2", "id assigned": "F002"},
            {"faculty name": "faculty-3", "id assigned": "F003"},
        ],
        template_type,
    )


@router.get("/templates/faculty-availability")
async def faculty_availability_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _template_response(
        "faculty-availability-template.xlsx",
        [
            {"Faculty ID": "F001", "Monday": "1, 2, 3", "Tuesday": "4, 5", "Wednesday": "", "Thursday": "", "Friday": "1, 2", "Saturday": ""},
            {"Faculty ID": "F002", "Monday": "", "Tuesday": "1, 2, 3, 4", "Wednesday": "5, 6, 7", "Thursday": "", "Friday": "", "Saturday": "1"},
        ],
        template_type,
    )


@router.get("/templates/faculty-workload")
async def faculty_workload_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _template_response(
        "faculty-workload-template.xlsx",
        [
            {"id assigned": "F001", "faculty name": "faculty-1", "day": "Monday", "period": 1, "year": "2nd Year", "section": "A", "subject": "Data Structures"},
            {"id assigned": "F001", "faculty name": "faculty-1", "day": "Friday", "period": 7, "year": "4th Year", "section": "B", "subject": "OS Lab"},
            {"id assigned": "F003", "faculty name": "faculty-3", "day": "Wednesday", "period": 4, "year": "3rd Year", "section": "A", "subject": "Machine Learning"},
        ],
        template_type,
    )

@router.get("/templates/shared-classes")
async def shared_classes_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _template_response(
        "shared-classes-template.xlsx",
        [
            {"year": "1st Year", "sections": "B, C", "subject": "subject-3"},
            {"year": "2nd Year", "sections": "A, D", "subject": "Data Structures"},
        ],
        template_type,
    )

@router.get("/templates/faculty-availability-query")
async def faculty_availability_query_template(
    template_type: Literal["example", "empty"] = Query("example", alias="type"),
):
    return _template_response(
        "faculty-availability-query-template.xlsx",
        [
            {"Date": "2026-04-01", "Number of Faculty Required": 1, "Start Time": "09:10", "End Time": "10:50"},
            {"Date": "2026-04-02", "Number of Faculty Required": 2, "Start Time": "12:40", "End Time": "16:00"},
            {"Date": "2026-04-03", "Number of Faculty Required": 1, "Start Time": "10:55", "End Time": "12:40"},
        ],
        template_type,
    )

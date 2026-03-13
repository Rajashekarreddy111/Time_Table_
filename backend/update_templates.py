import os

new_content = """from io import BytesIO

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from services.file_parser import create_excel_template

router = APIRouter(tags=["templates"])


def _template_response(file_name: str, records: list[dict]) -> StreamingResponse:
    content = create_excel_template(records)
    stream = BytesIO(content)
    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/templates/main-timetable-config")
async def main_timetable_template():
    return _template_response(
        "main-timetable-template.xlsx",
        [
            {
                "YEAR": "2",
                "SUBJECT_ID": "7",
                "C1_HOURS": 4,
                "C1_FACULTY_ID": "5",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 4,
                "C2_FACULTY_ID": "5",
                "C2_CONTINUOUS_HOURS": 2,
            },
            {
                "YEAR": "2",
                "SUBJECT_ID": "10",
                "C1_HOURS": 3,
                "C1_FACULTY_ID": "10",
                "C1_CONTINUOUS_HOURS": 2,
                "C2_HOURS": 3,
                "C2_FACULTY_ID": "40",
                "C2_CONTINUOUS_HOURS": 2,
            },
        ],
    )


@router.get("/templates/lab-timetable")
async def lab_timetable_template():
    return _template_response(
        "lab-timetable-template.xlsx",
        [
            {"YEAR": "2", "SECTION": "C1", "SUBJECT_ID": "7", "DAY": "1", "HOURS": "1,2", "VENUE": "2201"},
            {"YEAR": "2", "SECTION": "C2", "SUBJECT_ID": "10", "DAY": "1", "HOURS": "3,4", "VENUE": "2202"},
        ],
    )


@router.get("/templates/subject-id-mapping")
async def subject_id_mapping_template():
    return _template_response(
        "subject-id-mapping-template.xlsx",
        [
            {"SUBJECT_ID": "7", "SUBJECT_NAME": "Data Structures"},
            {"SUBJECT_ID": "10", "SUBJECT_NAME": "DBMS"},
        ],
    )


@router.get("/templates/subject-continuous-rules")
async def subject_continuous_rules_template():
    return _template_response(
        "subject-continuous-rules-template.xlsx",
        [
            {"SUBJECT_ID": "7", "COMPULSORY_CONTINUOUS_HOURS": 2},
            {"SUBJECT_ID": "10", "COMPULSORY_CONTINUOUS_HOURS": 3},
        ],
    )


@router.get("/templates/faculty-id-map")
async def faculty_id_template():
    return _template_response(
        "faculty-id-map-template.xlsx",
        [
            {"faculty name": "faculty-1", "id assigned": "F001"},
            {"faculty name": "faculty-2", "id assigned": "F002"},
            {"faculty name": "faculty-3", "id assigned": "F003"},
        ],
    )


@router.get("/templates/faculty-availability")
async def faculty_availability_template():
    return _template_response(
        "faculty-availability-template.xlsx",
        [
            {"Faculty ID": "F001", "Monday": "1, 2, 3", "Tuesday": "4, 5", "Wednesday": "", "Thursday": "", "Friday": "1, 2", "Saturday": ""},
            {"Faculty ID": "F002", "Monday": "", "Tuesday": "1, 2, 3, 4", "Wednesday": "5, 6, 7", "Thursday": "", "Friday": "", "Saturday": "1"},
        ],
    )


@router.get("/templates/faculty-workload")
async def faculty_workload_template():
    return _template_response(
        "faculty-workload-template.xlsx",
        [
            {"id assigned": "F001", "faculty name": "faculty-1", "day": "Monday", "period": 1, "year": "2nd Year", "section": "A", "subject": "Data Structures"},
            {"id assigned": "F001", "faculty name": "faculty-1", "day": "Friday", "period": 7, "year": "4th Year", "section": "B", "subject": "OS Lab"},
            {"id assigned": "F003", "faculty name": "faculty-3", "day": "Wednesday", "period": 4, "year": "3rd Year", "section": "A", "subject": "Machine Learning"},
        ],
    )

@router.get("/templates/shared-classes")
async def shared_classes_template():
    return _template_response(
        "shared-classes-template.xlsx",
        [
            {"year": "1st Year", "sections": "B, C", "subject": "subject-3"},
            {"year": "2nd Year", "sections": "A, D", "subject": "Data Structures"},
        ],
    )

@router.get("/templates/faculty-availability-query")
async def faculty_availability_query_template():
    return _template_response(
        "faculty-availability-query-template.xlsx",
        [
            {"Date": "2024-03-20", "Number of Faculty Required": 1, "Periods": "1, 2, 3"},
            {"Date": "2024-03-21", "Number of Faculty Required": 2, "Periods": "4, 5"},
            {"Date": "Monday", "Number of Faculty Required": 1, "Periods": "1, 6"},
        ],
    )
"""

with open(r"c:\\Users\\rajas\\OneDrive\\Desktop\\Timetable\\backend\\routers\\templates.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Templates updated successfully")

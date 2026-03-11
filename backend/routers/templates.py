from io import BytesIO

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from services.file_parser import create_excel_template

router = APIRouter(tags=["templates"])


def _build_alpha_sections(count: int) -> list[str]:
    sections: list[str] = []
    for idx in range(max(0, count)):
        if idx < 26:
            sections.append(chr(65 + idx))
        else:
            sections.append(f"S{idx + 1}")
    return sections


def _resolve_subject_faculty_sections(
    section_list: str | None,
    has_cream_general: bool,
    section_count: int,
    cream_section_count: int,
    general_section_count: int,
) -> list[str]:
    if section_list:
        parsed = [item.strip() for item in section_list.split(",") if item.strip()]
        if parsed:
            return parsed

    if has_cream_general:
        cream = [f"C{i + 1}" for i in range(max(0, cream_section_count))]
        general = [f"G{i + 1}" for i in range(max(0, general_section_count))]
        sections = cream + general
        if sections:
            return sections

    fallback_count = section_count if section_count > 0 else 4
    return _build_alpha_sections(fallback_count)


def _template_response(file_name: str, records: list[dict]) -> StreamingResponse:
    content = create_excel_template(records)
    stream = BytesIO(content)
    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
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


@router.get("/templates/subject-faculty-map")
async def subject_faculty_template(
    year: str = Query(default="2nd Year"),
    sectionCount: int = Query(default=4),
    hasCreamGeneral: bool = Query(default=False),
    creamSectionCount: int = Query(default=0),
    generalSectionCount: int = Query(default=0),
    sectionList: str | None = Query(default=None),
):
    year_value = year.strip() or "2nd Year"
    sections = _resolve_subject_faculty_sections(
        section_list=sectionList,
        has_cream_general=hasCreamGeneral,
        section_count=max(0, sectionCount),
        cream_section_count=max(0, creamSectionCount),
        general_section_count=max(0, generalSectionCount),
    )

    records: list[dict] = []
    for section in sections:
        records.append(
            {
                "year": year_value,
                "section/subject": section,
                "subject-1": "",
                "subject-2": "",
                "subject-3": "",
                "lab-1": "",
                "lab-2": "",
                "lab-3": "",
            }
        )

    return _template_response(
        "subject-faculty-map-template.xlsx",
        records,
    )


@router.get("/templates/subject-periods-map")
async def subject_periods_template(batchType: str | None = Query(default=None)):
    normalized = (batchType or "ALL").strip().upper()
    if normalized == "CREAM":
        return _template_response(
            "cream-subject-periods-map-template.xlsx",
            [
                {"subject/lab": "Data Structures", "number of hours": 4, "continuous hours that can be allocated": 1},
                {"subject/lab": "DBMS", "number of hours": 4, "continuous hours that can be allocated": 1},
                {"subject/lab": "Operating Systems", "number of hours": 3, "continuous hours that can be allocated": 1},
                {"subject/lab": "DS Lab", "number of hours": 3, "continuous hours that can be allocated": 3},
            ],
        )

    if normalized == "GENERAL":
        return _template_response(
            "general-subject-periods-map-template.xlsx",
            [
                {"subject/lab": "Data Structures", "number of hours": 3, "continuous hours that can be allocated": 1},
                {"subject/lab": "DBMS", "number of hours": 3, "continuous hours that can be allocated": 1},
                {"subject/lab": "Operating Systems", "number of hours": 2, "continuous hours that can be allocated": 1},
                {"subject/lab": "DS Lab", "number of hours": 2, "continuous hours that can be allocated": 2},
            ],
        )

    return _template_response(
        "subject-periods-map-template.xlsx",
        [
            {"subject/lab": "subject-1", "number of hours": 4, "continuous hours that can be allocated": 1},
            {"subject/lab": "subject-2", "number of hours": 4, "continuous hours that can be allocated": 1},
            {"subject/lab": "lab-1", "number of hours": 3, "continuous hours that can be allocated": 3},
            {"subject/lab": "", "number of hours": "", "continuous hours that can be allocated": ""},
            {"subject/lab": "", "number of hours": "", "continuous hours that can be allocated": ""},
        ],
    )


@router.get("/templates/subject-periods-map-cream")
async def subject_periods_template_cream():
    return await subject_periods_template(batchType="CREAM")


@router.get("/templates/subject-periods-map-general")
async def subject_periods_template_general():
    return await subject_periods_template(batchType="GENERAL")


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

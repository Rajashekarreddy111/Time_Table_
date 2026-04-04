from fastapi import APIRouter

from models.schemas import FacultyAvailabilityRequest, FacultyAvailabilityResponse
from services.faculty_availability import get_available_faculty_for_all_periods
from storage.memory_store import store

router = APIRouter(tags=["faculty"])


@router.post("/faculty/availability", response_model=FacultyAvailabilityResponse)
async def faculty_availability(payload: FacultyAvailabilityRequest):
    result = get_available_faculty_for_all_periods(
        store=store,
        date_value=payload.date,
        periods=payload.periods,
        start_time=payload.startTime,
        end_time=payload.endTime,
        faculty_required=payload.facultyRequired,
        ignored_years=payload.ignoredYears,
        ignored_sections=payload.ignoredSections,
        availability_file_id=payload.availabilityFileId,
        faculty_id_map_file_id=payload.facultyIdMapFileId,
    )
    return FacultyAvailabilityResponse(**result)


from models.schemas import BulkFacultyAvailabilityRequest, BulkFacultyAvailabilityResponse, GeneratedWorkbookFile
from services.faculty_availability import build_bulk_faculty_availability_workbook, get_bulk_available_faculty

@router.post("/faculty/availability/bulk", response_model=BulkFacultyAvailabilityResponse)
async def bulk_faculty_availability(payload: BulkFacultyAvailabilityRequest):
    result = get_bulk_available_faculty(
        store=store,
        availability_file_id=payload.availabilityFileId,
        query_file_id=payload.queryFileId,
        ignored_years=payload.ignoredYears,
        ignored_sections=payload.ignoredSections,
        faculty_id_map_file_id=payload.facultyIdMapFileId,
    )
    return BulkFacultyAvailabilityResponse(**result)


@router.post("/faculty/availability/bulk/export-selected", response_model=GeneratedWorkbookFile)
async def bulk_faculty_availability_selected_export(payload: BulkFacultyAvailabilityRequest):
    result = get_bulk_available_faculty(
        store=store,
        availability_file_id=payload.availabilityFileId,
        query_file_id=payload.queryFileId,
        ignored_years=payload.ignoredYears,
        ignored_sections=payload.ignoredSections,
        faculty_id_map_file_id=payload.facultyIdMapFileId,
    )
    return GeneratedWorkbookFile(**build_bulk_faculty_availability_workbook(result.get("results", []), mode="selected"))


@router.post("/faculty/availability/bulk/export-available", response_model=GeneratedWorkbookFile)
async def bulk_faculty_availability_available_export(payload: BulkFacultyAvailabilityRequest):
    result = get_bulk_available_faculty(
        store=store,
        availability_file_id=payload.availabilityFileId,
        query_file_id=payload.queryFileId,
        ignored_years=payload.ignoredYears,
        ignored_sections=payload.ignoredSections,
        faculty_id_map_file_id=payload.facultyIdMapFileId,
    )
    return GeneratedWorkbookFile(**build_bulk_faculty_availability_workbook(result.get("results", []), mode="available"))

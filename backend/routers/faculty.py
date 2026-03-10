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
        faculty_required=payload.facultyRequired,
        ignored_years=payload.ignoredYears,
        ignored_sections=payload.ignoredSections,
        availability_file_id=payload.availabilityFileId,
        faculty_id_map_file_id=payload.facultyIdMapFileId,
    )
    return FacultyAvailabilityResponse(**result)

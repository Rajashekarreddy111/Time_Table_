from fastapi import APIRouter, HTTPException

from models.schemas import GenerateTimetableRequest, GenerateTimetableResponse
from services.timetable_generator import generate_timetable
from storage.memory_store import store

router = APIRouter(tags=["timetables"])


@router.post("/timetables/generate", response_model=GenerateTimetableResponse)
async def create_timetable(payload: GenerateTimetableRequest):
    result = generate_timetable(payload, store)
    return GenerateTimetableResponse(**result)


@router.get("/timetables")
async def list_generated_timetables():
    return {"items": store.list_timetables()}


@router.get("/timetables/{timetable_id}")
async def get_generated_timetable(timetable_id: str):
    payload = store.get_timetable(timetable_id)
    if not payload:
        raise HTTPException(
            status_code=404,
            detail={"error": "NotFound", "message": "Timetable not found", "details": []},
        )
    return payload
@router.delete("/timetables/{timetable_id}")
async def delete_timetable(timetable_id: str):
    success = store.delete_timetable(timetable_id)
    if not success:
        raise HTTPException(status_code=404, detail="Timetable not found")
    store.delete_occupancy_by_source(timetable_id)
    return {"message": "Timetable deleted successfully"}

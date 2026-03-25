from typing import Any

from fastapi import APIRouter, HTTPException

from models.schemas import GenerateTimetableRequest, GenerateTimetableResponse
from services.timetable_generator import generate_timetable
from storage.memory_store import store

router = APIRouter(tags=["timetables"])


def _normalize_subject_token(value: Any) -> str:
    token = str(value or "").strip()
    if token.endswith(".0"):
        token = token[:-2]
    return token


def _build_subject_name_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    payload = store.get_scoped_mapping("subject_id_mapping", "global")
    if not payload:
        return mapping
    for row in payload.get("rows", []):
        sid = _normalize_subject_token(row.get("subject_id", ""))
        sname = str(row.get("subject_name", "")).strip()
        if sid:
            mapping[sid] = sname or sid
    return mapping


def _enrich_subject_names(record: dict[str, Any]) -> dict[str, Any]:
    subject_map = _build_subject_name_map()
    if not subject_map:
        return record

    def enrich_grid(grid: dict[str, list[Any]] | None) -> None:
        if not isinstance(grid, dict):
            return
        for _day, slots in grid.items():
            if not isinstance(slots, list):
                continue
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                sid = _normalize_subject_token(slot.get("subjectId") or slot.get("subject"))
                if not sid:
                    continue
                subject_name = subject_map.get(sid, sid)
                slot["subjectId"] = sid
                slot["subjectName"] = subject_name
                slot["subject"] = subject_name

    if isinstance(record.get("allGrids"), dict):
        for grid in record["allGrids"].values():
            enrich_grid(grid)
    else:
        enrich_grid(record.get("grid"))

    for key in ("sharedClasses", "constraintViolations", "unscheduledSubjects"):
        items = record.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            sid = _normalize_subject_token(item.get("subject_id", ""))
            if not sid:
                continue
            item["subject_id"] = sid
            item["subject_name"] = subject_map.get(sid, sid)
    return record


@router.post("/timetables/generate", response_model=GenerateTimetableResponse)
async def create_timetable(payload: GenerateTimetableRequest):
    result = generate_timetable(payload, store)
    return GenerateTimetableResponse(**result)


@router.get("/timetables")
async def list_generated_timetables():
    items = [_enrich_subject_names(item) for item in store.list_timetables()]
    return {"items": items}


@router.get("/timetables/{timetable_id}")
async def get_generated_timetable(timetable_id: str):
    payload = store.get_timetable(timetable_id)
    if not payload:
        raise HTTPException(
            status_code=404,
            detail={"error": "NotFound", "message": "Timetable not found", "details": []},
        )
    return _enrich_subject_names(payload)
@router.delete("/timetables/{timetable_id}")
async def delete_timetable(timetable_id: str):
    success = store.delete_timetable(timetable_id)
    if not success:
        raise HTTPException(status_code=404, detail="Timetable not found")
    store.delete_occupancy_by_source(timetable_id)
    return {"message": "Timetable deleted successfully"}

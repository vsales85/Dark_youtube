"""Voice-over ("narração") for finished clips."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...narration import list_voices, normalize_ranges, write_script
from ...services.narration_service import get_narration_status, set_narration_status
from ...services.task_service import TaskService
from ...workers.job_queue import JobQueue
from .tasks import _read_json_object, _require_task_owner

logger = logging.getLogger(__name__)

router = APIRouter(tags=["narration"])


async def _owned_clip(request: Request, db: AsyncSession, task_id: str, clip_id: str):
    service = TaskService(db)
    await _require_task_owner(request, service, db, task_id)
    clip = await service.clip_repo.get_clip_by_id(db, clip_id)
    if not clip or clip["task_id"] != task_id:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


@router.get("/tasks/{task_id}/narration/voices")
async def get_voices(task_id: str):
    try:
        return {"voices": await list_voices()}
    except Exception as exc:
        logger.warning("Voice service unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Serviço de voz indisponível (VOICE_CLONE_URL)")


@router.post("/tasks/{task_id}/clips/{clip_id}/narration/script")
async def generate_script(task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await _read_json_object(request)
    clip = await _owned_clip(request, db, task_id, clip_id)
    duration = float(clip["duration"])
    try:
        ranges = normalize_ranges(payload.get("original_ranges"), duration)
        script = await write_script(clip.get("text") or "", duration, ranges, str(payload.get("instructions") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Narration script failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Falha ao gerar roteiro: {exc}")
    return {"script": script}


@router.post("/tasks/{task_id}/clips/{clip_id}/narration")
async def start_narration(task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await _read_json_object(request)
    clip = await _owned_clip(request, db, task_id, clip_id)
    script = str(payload.get("script") or "").strip()
    voice = str(payload.get("voice") or "").strip()
    if not script or not voice:
        raise HTTPException(status_code=400, detail="script and voice are required")
    try:
        volume = float(payload.get("original_volume", 0.15))
        ranges = normalize_ranges(payload.get("original_ranges"), float(clip["duration"]))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    options = {
        "script": script,
        "voice": voice,
        "original_volume": max(0.0, min(1.0, volume)),
        "original_ranges": [list(r) for r in ranges],
    }
    await set_narration_status(clip_id, {"status": "queued"})
    await JobQueue.enqueue_job("narrate_clip_job", task_id, clip_id, options)
    return {"status": "queued"}


@router.get("/tasks/{task_id}/clips/{clip_id}/narration")
async def narration_status(task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await _owned_clip(request, db, task_id, clip_id)
    return await get_narration_status(clip_id) or {"status": "none"}

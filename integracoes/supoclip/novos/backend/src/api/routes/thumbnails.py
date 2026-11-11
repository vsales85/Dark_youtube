"""Impact thumbnails (9:16 Shorts cover, 16:9 YouTube) for clips."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_config
from ...database import get_db
from ...media_storage import MediaStorage
from ...thumbnails import FORMATS, candidate_frames, extract_frame, render_thumbnail
from ...utils.async_helpers import run_in_thread
from .narration import _owned_clip
from .tasks import _read_json_object

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks/{task_id}/clips/{clip_id}/thumbnail", tags=["thumbnails"])


def _thumb_dir() -> Path:
    path = Path(get_config().temp_dir) / "thumbnails"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _clip_path(request: Request, db: AsyncSession, task_id: str, clip_id: str):
    clip = await _owned_clip(request, db, task_id, clip_id)
    path = await run_in_thread(MediaStorage().local_path, clip["file_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found")
    return clip, path


@router.get("/candidates")
async def thumbnail_candidates(task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    clip, path = await _clip_path(request, db, task_id, clip_id)
    times = await run_in_thread(candidate_frames, path)
    return {"times": times, "text": clip.get("hook_title") or ""}


@router.get("/frame")
async def thumbnail_frame(task_id: str, clip_id: str, t: float, request: Request, db: AsyncSession = Depends(get_db)):
    _, path = await _clip_path(request, db, task_id, clip_id)
    out = _thumb_dir() / f"{clip_id}_frame_{int(t * 100)}.jpg"
    if not out.exists():
        await run_in_thread(extract_frame, path, t, out)
    return FileResponse(out, media_type="image/jpeg")


@router.post("")
async def create_thumbnails(task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await _read_json_object(request)
    _, path = await _clip_path(request, db, task_id, clip_id)
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        seconds = float(payload.get("time", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="time must be a number")
    for fmt in FORMATS:
        try:
            await run_in_thread(render_thumbnail, path, seconds, text, fmt, _thumb_dir() / f"{clip_id}_{fmt}.jpg")
        except Exception as exc:
            logger.error("Thumbnail %s failed: %s", fmt, getattr(exc, "stderr", exc))
            raise HTTPException(status_code=500, detail=f"Falha ao gerar thumbnail {fmt}")
    return {"formats": list(FORMATS)}


@router.get("/{fmt}.jpg")
async def get_thumbnail(task_id: str, clip_id: str, fmt: str, request: Request, db: AsyncSession = Depends(get_db)):
    await _owned_clip(request, db, task_id, clip_id)
    out = _thumb_dir() / f"{clip_id}_{fmt}.jpg"
    if fmt not in FORMATS or not out.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(out, media_type="image/jpeg", filename=f"thumb_{fmt}.jpg")

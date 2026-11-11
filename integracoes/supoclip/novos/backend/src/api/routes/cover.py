"""Cover burned-in subtitles of the source with a blur or dark band.

Creates a new clip version right after the original; the band is given as
fractions of the frame height so it matches what the user marked on a preview.
"""

import logging
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...clip_source_map import load_clip_caption_settings, save_clip_caption_settings, save_clip_source_ranges
from ...database import get_db
from ...media_storage import MediaStorage
from ...services.task_service import TaskService
from ...utils.async_helpers import run_in_thread
from .narration import _owned_clip
from .tasks import _read_json_object

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cover"])


def cover_band(input_path: Path, output_dir: Path, top: float, height: float, mode: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"covered_{uuid.uuid4().hex[:12]}.mp4"
    y, h = f"trunc(ih*{top:.4f}/2)*2", f"trunc(ih*{height:.4f}/2)*2"
    if mode == "dark":
        graph = f"[0:v]drawbox=x=0:y={y}:w=iw:h={h}:color=black@0.85:t=fill[v]"
    else:
        graph = (
            f"[0:v]split[base][band];"
            f"[band]crop=iw:{h}:0:{y},boxblur=30:3[blur];"
            f"[base][blur]overlay=0:{y.replace('ih', 'H')}[v]"
        )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-filter_complex", graph,
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(output_path)],
        check=True, capture_output=True, text=True,
    )
    return output_path


@router.post("/tasks/{task_id}/clips/{clip_id}/cover")
async def cover_clip(task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await _read_json_object(request)
    clip = await _owned_clip(request, db, task_id, clip_id)
    try:
        top = float(payload.get("top", 0))
        height = float(payload.get("height", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="top and height must be numbers")
    if not (0 <= top < 1 and 0.02 <= height <= 1 - top):
        raise HTTPException(status_code=400, detail="Invalid band")
    mode = "dark" if payload.get("mode") == "dark" else "blur"

    service = TaskService(db)
    input_path = await run_in_thread(MediaStorage().local_path, clip["file_path"])
    try:
        output_path = await run_in_thread(
            cover_band, input_path, Path(service.config.temp_dir) / "clips", top, height, mode
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Cover band failed: %s", exc.stderr[-500:] if exc.stderr else exc)
        raise HTTPException(status_code=500, detail="Falha ao cobrir a legenda")
    new_clip_id = await _add_version(db, service, task_id, clip, input_path, output_path, "Legenda original coberta")
    return {"new_clip_id": new_clip_id}


async def _add_version(db, service, task_id: str, clip: dict, input_path: Path, output_path: Path, reasoning: str) -> str:
    """Insert ``output_path`` as a new clip right after ``clip``, keeping its metadata."""
    save_clip_source_ranges(output_path, await run_in_thread(service._get_clip_source_ranges, clip))
    if settings := load_clip_caption_settings(input_path):
        save_clip_caption_settings(output_path, settings)
    order = clip.get("clip_order", 1) + 1
    await service.clip_repo.make_room_for_clip(db, task_id, order)
    new_clip_id = await service.clip_repo.create_clip(
        db,
        task_id=task_id,
        filename=output_path.name,
        file_path=str(output_path),
        start_time=clip["start_time"],
        end_time=clip["end_time"],
        duration=float(clip["duration"]),
        text=clip.get("text") or "",
        relevance_score=clip.get("relevance_score", 0.5),
        reasoning=reasoning,
        clip_order=order,
        virality_score=clip.get("virality_score", 0),
        hook_score=clip.get("hook_score", 0),
        engagement_score=clip.get("engagement_score", 0),
        value_score=clip.get("value_score", 0),
        shareability_score=clip.get("shareability_score", 0),
        hook_type=clip.get("hook_type"),
        hook_title=clip.get("hook_title"),
    )
    await service.clip_repo.reorder_task_clips(db, task_id)
    return new_clip_id


# Colour looks (from ClippyMe's colour-grade idea), as ffmpeg filter chains.
COLOR_PRESETS = {
    "cinema": ("Cinema", "eq=contrast=1.12:saturation=0.9,colorbalance=rs=-0.04:bs=0.06:rh=0.07:bh=-0.05,vignette=PI/5"),
    "vibrante": ("Vibrante", "eq=contrast=1.08:saturation=1.4:brightness=0.02"),
    "dramatico": ("Dramático", "eq=contrast=1.3:saturation=1.1:brightness=-0.03,vignette=PI/4"),
    "quente": ("Quente", "colorbalance=rs=0.08:gs=0.02:bs=-0.08:rm=0.05:bm=-0.05,eq=saturation=1.1"),
    "frio": ("Frio", "colorbalance=rs=-0.06:bs=0.1:rm=-0.03:bm=0.06,eq=contrast=1.05"),
    "vintage": ("Vintage", "curves=preset=vintage,eq=saturation=0.85"),
    "pb": ("Preto e branco", "hue=s=0,eq=contrast=1.2"),
}


def apply_color(input_path: Path, output_dir: Path, preset: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"color_{preset}_{uuid.uuid4().hex[:12]}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-vf", f"{COLOR_PRESETS[preset][1]},format=yuv420p",
         "-map", "0:v", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-c:a", "copy", "-movflags", "+faststart", str(output_path)],
        check=True, capture_output=True, text=True,
    )
    return output_path


def color_preview(input_path: Path, out_path: Path, preset: str, seconds: float) -> Path:
    chain = COLOR_PRESETS[preset][1] + "," if preset in COLOR_PRESETS else ""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, seconds):.2f}", "-i", str(input_path),
         "-frames:v", "1", "-vf", f"{chain}scale=270:-2", "-q:v", "4", str(out_path)],
        check=True, capture_output=True, text=True,
    )
    return out_path


@router.get("/tasks/{task_id}/clips/{clip_id}/color/presets")
async def color_presets(task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await _owned_clip(request, db, task_id, clip_id)
    return {"presets": [{"id": key, "label": label} for key, (label, _) in COLOR_PRESETS.items()]}


@router.get("/tasks/{task_id}/clips/{clip_id}/color/preview/{preset}.jpg")
async def color_preview_image(task_id: str, clip_id: str, preset: str, request: Request, db: AsyncSession = Depends(get_db)):
    clip = await _owned_clip(request, db, task_id, clip_id)
    if preset != "original" and preset not in COLOR_PRESETS:
        raise HTTPException(status_code=404, detail="Filtro desconhecido")
    input_path = await run_in_thread(MediaStorage().local_path, clip["file_path"])
    out = Path(TaskService(db).config.temp_dir) / "thumbnails" / f"{clip_id}_color_{preset}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        await run_in_thread(color_preview, input_path, out, preset, min(3.0, float(clip["duration"]) / 2))
    return FileResponse(out, media_type="image/jpeg")


@router.post("/tasks/{task_id}/clips/{clip_id}/color")
async def color_clip(task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await _read_json_object(request)
    clip = await _owned_clip(request, db, task_id, clip_id)
    preset = str(payload.get("preset") or "")
    if preset not in COLOR_PRESETS:
        raise HTTPException(status_code=400, detail="Filtro desconhecido")
    service = TaskService(db)
    input_path = await run_in_thread(MediaStorage().local_path, clip["file_path"])
    try:
        output_path = await run_in_thread(apply_color, input_path, Path(service.config.temp_dir) / "clips", preset)
    except subprocess.CalledProcessError as exc:
        logger.error("Colour grade failed: %s", exc.stderr[-500:] if exc.stderr else exc)
        raise HTTPException(status_code=500, detail="Falha ao aplicar a cor")
    new_clip_id = await _add_version(db, service, task_id, clip, input_path, output_path, f"Cor: {COLOR_PRESETS[preset][0]}")
    return {"new_clip_id": new_clip_id}

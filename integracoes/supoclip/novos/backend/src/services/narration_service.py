"""Voice-over versions of clips, rendered on the worker.

Job state lives in Redis under ``narration:{clip_id}`` so the clip page can
poll it: queued -> rendering -> done (new_clip_id) | error.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import redis.asyncio as redis

from ..clip_source_map import (
    load_clip_caption_settings,
    save_clip_caption_settings,
    save_clip_source_ranges,
)
from ..config import get_config
from ..media_storage import MediaStorage
from ..narration import normalize_ranges, render_narration
from ..utils.async_helpers import run_in_thread

logger = logging.getLogger(__name__)

STATUS_TTL_SECONDS = 24 * 3600


def _redis() -> redis.Redis:
    config = get_config()
    return redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        password=config.redis_password,
        decode_responses=True,
    )


async def set_narration_status(clip_id: str, status: Dict[str, Any]) -> None:
    client = _redis()
    try:
        await client.set(f"narration:{clip_id}", json.dumps(status), ex=STATUS_TTL_SECONDS)
    finally:
        await client.aclose()


async def get_narration_status(clip_id: str) -> Optional[Dict[str, Any]]:
    client = _redis()
    try:
        raw = await client.get(f"narration:{clip_id}")
    finally:
        await client.aclose()
    return json.loads(raw) if raw else None


async def narrate_clip_job(ctx, task_id: str, clip_id: str, options: Dict[str, Any]) -> Dict[str, Any]:
    from ..database import AsyncSessionLocal
    from .task_service import TaskService

    await set_narration_status(clip_id, {"status": "rendering"})
    try:
        async with AsyncSessionLocal() as db:
            service = TaskService(db)
            clip = await service.clip_repo.get_clip_by_id(db, clip_id)
            if not clip or clip["task_id"] != task_id:
                raise ValueError("Clip not found")
            input_path = await run_in_thread(MediaStorage().local_path, clip["file_path"])
            ranges = normalize_ranges(options.get("original_ranges"), float(clip["duration"]))
            output_path = await run_in_thread(
                render_narration,
                input_path,
                Path(service.config.temp_dir) / "clips",
                options["script"],
                options["voice"],
                float(options.get("original_volume", 0.15)),
                ranges,
            )
            source_ranges = await run_in_thread(service._get_clip_source_ranges, clip)
            save_clip_source_ranges(output_path, source_ranges)
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
                text=options["script"],
                relevance_score=clip.get("relevance_score", 0.5),
                reasoning="Versão narrada",
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
    except Exception as exc:
        logger.error("Narration for clip %s failed: %s", clip_id, exc, exc_info=True)
        await set_narration_status(clip_id, {"status": "error", "error": str(exc)[:300]})
        return {"status": "error"}

    await set_narration_status(clip_id, {"status": "done", "new_clip_id": new_clip_id})
    return {"status": "done", "new_clip_id": new_clip_id}

"""Auto-cut new uploads from monitored channels (worker cron).

A channel with ``auto`` on gets every *new* upload sent to the normal task
creation route, signed as its owner like the frontend does, so plan limits,
YouTube checks and queueing all stay in one place. Uploads that existed when
auto was switched on are marked seen and never cut.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict

import httpx

from ..config import get_config
from ..trending import channel_feed
from ..utils.async_helpers import run_in_thread

logger = logging.getLogger(__name__)

MAX_CUTS_PER_RUN = 2
MAX_AGE_SECONDS = 48 * 3600
LOG_LIMIT = 50


def _signed_headers(user_id: str) -> dict:
    timestamp = str(int(time.time()))
    secret = get_config().backend_auth_secret or ""
    signature = hmac.new(secret.encode(), f"{user_id}:{timestamp}".encode(), hashlib.sha256).hexdigest()
    return {"x-supoclip-user-id": user_id, "x-supoclip-ts": timestamp, "x-supoclip-signature": signature}


def seen_key(user_id: str, channel_id: str) -> str:
    return f"trending:seen:{user_id}:{channel_id}"


async def mark_current_uploads_seen(client, user_id: str, channel_id: str) -> None:
    """Called when auto is switched on: existing uploads are never cut."""
    videos = await run_in_thread(channel_feed, channel_id)
    ids = [v["id"] for v in videos if v.get("id")]
    if ids:
        await client.sadd(seen_key(user_id, channel_id), *ids)
    else:
        await client.sadd(seen_key(user_id, channel_id), "_")


async def auto_cut_channels(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from ..api.routes.studio import _redis

    backend = os.getenv("BACKEND_INTERNAL_URL", "http://backend:8000").rstrip("/")
    client = _redis()
    created = 0
    try:
        async for key in client.scan_iter("trending:channels:*"):
            user_id = key.rsplit(":", 1)[-1]
            channels = json.loads(await client.get(key) or "[]")
            cuts = 0
            for channel in channels:
                if not channel.get("auto") or cuts >= MAX_CUTS_PER_RUN:
                    continue
                try:
                    videos = await run_in_thread(channel_feed, channel["channel_id"])
                except Exception as exc:
                    logger.info("Feed %s failed: %s", channel["channel_id"], exc)
                    continue
                for video in videos:
                    if cuts >= MAX_CUTS_PER_RUN:
                        break
                    if not await client.sadd(seen_key(user_id, channel["channel_id"]), video["id"]):
                        continue  # already seen
                    try:
                        published = datetime.fromisoformat(video["published"]).timestamp()
                    except (TypeError, ValueError):
                        published = time.time()
                    if time.time() - published > MAX_AGE_SECONDS:
                        continue
                    async with httpx.AsyncClient(timeout=120) as http:
                        response = await http.post(
                            f"{backend}/tasks/",
                            json={"source": {"url": video["url"], "title": video["title"]}},
                            headers=_signed_headers(user_id),
                        )
                    entry = {"title": video["title"], "channel": channel["name"], "url": video["url"], "at": time.time()}
                    if response.status_code < 300:
                        entry["task_id"] = response.json().get("task_id")
                        cuts += 1
                        created += 1
                        logger.info("Auto-cut queued for %s (%s)", video["id"], channel["name"])
                    else:
                        entry["error"] = str(response.json().get("detail", response.status_code))[:200]
                        logger.warning("Auto-cut of %s refused: %s", video["id"], entry["error"])
                    await client.lpush(f"trending:autocuts:{user_id}", json.dumps(entry, ensure_ascii=False))
                    await client.ltrim(f"trending:autocuts:{user_id}", 0, LOG_LIMIT - 1)
    finally:
        await client.aclose()
    return {"created": created}

"""'Em alta': search videos that are taking off and watch favourite channels."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...trending import PERIODS, channel_feed, resolve_channel, search_trending
from ...utils.async_helpers import run_in_thread
from .studio import _redis, _user
from .tasks import _read_json_object

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks/trending", tags=["trending"])

SEARCH_CACHE_SECONDS = 15 * 60
MAX_CHANNELS = 30


@router.get("/search")
async def search(request: Request, q: str, period: str = "semana", shorts: bool = False, reusable: bool = False, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    query = q.strip()[:120]
    if not query:
        raise HTTPException(status_code=400, detail="Digite um tema para buscar")
    period = period if period in PERIODS else "semana"
    key = f"trending:v3:{period}:{int(shorts)}:{int(reusable)}:{query.lower()}"
    client = _redis()
    try:
        if cached := await client.get(key):
            return {"videos": json.loads(cached), "cached": True}
        try:
            videos = await run_in_thread(search_trending, query, period, shorts, reusable)
        except Exception as exc:
            logger.warning("Trending search failed: %s", exc)
            raise HTTPException(status_code=502, detail="O YouTube não respondeu à busca. Tente de novo em instantes.")
        await client.set(key, json.dumps(videos), ex=SEARCH_CACHE_SECONDS)
    finally:
        await client.aclose()
    return {"videos": videos, "cached": False}


def _channels_key(user_id: str) -> str:
    return f"trending:channels:{user_id}"


async def _load_channels(user_id: str) -> list[dict]:
    client = _redis()
    try:
        raw = await client.get(_channels_key(user_id))
    finally:
        await client.aclose()
    return json.loads(raw) if raw else []


async def _save_channels(user_id: str, channels: list[dict]) -> None:
    client = _redis()
    try:
        await client.set(_channels_key(user_id), json.dumps(channels, ensure_ascii=False))
    finally:
        await client.aclose()


@router.get("/channels")
async def list_channels(request: Request, db: AsyncSession = Depends(get_db)):
    return {"channels": await _load_channels(await _user(request, db))}


@router.post("/channels")
async def add_channel(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    payload = await _read_json_object(request)
    text = str(payload.get("channel") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Cole o link ou @ do canal")
    try:
        channel = await run_in_thread(resolve_channel, text)
    except Exception:
        raise HTTPException(status_code=404, detail="Não encontrei esse canal. Cole o link do canal ou o @nome.")
    channels = [c for c in await _load_channels(user_id) if c["channel_id"] != channel["channel_id"]]
    if len(channels) >= MAX_CHANNELS:
        raise HTTPException(status_code=400, detail=f"Limite de {MAX_CHANNELS} canais")
    channels.append(channel)
    await _save_channels(user_id, channels)
    return {"channels": channels}


@router.delete("/channels/{channel_id}")
async def remove_channel(channel_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    channels = [c for c in await _load_channels(user_id) if c["channel_id"] != channel_id]
    await _save_channels(user_id, channels)
    return {"channels": channels}


@router.get("/feed")
async def feed(request: Request, db: AsyncSession = Depends(get_db)):
    """Newest uploads from every monitored channel, newest first."""
    user_id = await _user(request, db)
    channels = await _load_channels(user_id)

    async def one(channel: dict) -> list[dict]:
        try:
            return await run_in_thread(channel_feed, channel["channel_id"])
        except Exception as exc:
            logger.info("Feed for %s failed: %s", channel["channel_id"], exc)
            return []

    lists = await asyncio.gather(*(one(c) for c in channels))
    videos = sorted((v for vs in lists for v in vs[:6]), key=lambda v: v.get("published") or "", reverse=True)
    return {"videos": videos[:60]}


@router.post("/channels/{channel_id}/auto")
async def set_channel_auto(channel_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Turn automatic cutting of this channel's *new* uploads on or off."""
    from ...services.monitor_service import mark_current_uploads_seen

    user_id = await _user(request, db)
    payload = await _read_json_object(request)
    enabled = payload.get("auto") is True
    channels = await _load_channels(user_id)
    channel = next((c for c in channels if c["channel_id"] == channel_id), None)
    if not channel:
        raise HTTPException(status_code=404, detail="Canal não encontrado")
    if enabled and not channel.get("auto"):
        client = _redis()
        try:
            await mark_current_uploads_seen(client, user_id, channel_id)
        finally:
            await client.aclose()
    channel["auto"] = enabled
    await _save_channels(user_id, channels)
    return {"channels": channels}


@router.get("/autocuts")
async def autocuts(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    client = _redis()
    try:
        raw = await client.lrange(f"trending:autocuts:{user_id}", 0, 19)
    finally:
        await client.aclose()
    return {"items": [json.loads(r) for r in raw]}


# Public-sector channels whose content is generally free to reuse with credit.
OFFICIAL_CHANNELS = [
    {"channel_id": "UCLgti7NuK0RuW9wty-fxPjQ", "name": "TV Senado"},
    {"channel_id": "UCxxSKD4_88tT_tKit2Nywew", "name": "Agência Brasil Áudio e Vídeo"},
]


@router.post("/channels/official")
async def add_official_channels(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    channels = await _load_channels(user_id)
    known = {c["channel_id"] for c in channels}
    channels += [dict(c) for c in OFFICIAL_CHANNELS if c["channel_id"] not in known]
    await _save_channels(user_id, channels[:MAX_CHANNELS])
    return {"channels": channels[:MAX_CHANNELS]}


@router.post("/analyze")
async def analyze_video(request: Request, db: AsyncSession = Depends(get_db)):
    """Why is this posted video (not) growing, and what to change next time."""
    from ...studio import analyze_posted_video
    from ...trending import video_facts

    await _user(request, db)
    payload = await _read_json_object(request)
    url = str(payload.get("url") or "").strip()
    if "youtu" not in url:
        raise HTTPException(status_code=400, detail="Cole o link de um vídeo do YouTube")
    try:
        facts = await run_in_thread(video_facts, url)
    except Exception as exc:
        logger.warning("Video facts failed: %s", exc)
        raise HTTPException(status_code=404, detail="Não consegui ler esse vídeo. Ele está público?")
    try:
        analysis = await analyze_posted_video(facts)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha na análise: {exc}")
    facts.pop("transcript", None)
    return {"facts": facts, "analysis": analysis}

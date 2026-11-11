"""'Vídeo do zero': narrated videos built from a script and background images."""

import base64
import json
import logging
import re
import shutil
import time
import uuid
from pathlib import Path

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth_headers import resolve_authenticated_user_id
from ...config import get_config
from ...database import get_db
from ...studio import FORMATS, TRANSITIONS, apply_pronunciation, list_voices, parse_pronunciation, parse_voice_settings, review_pronunciation, fix_spelling, suggest_ideas, fact_check, synthesize, write_post_text, write_script
from ...utils.async_helpers import run_in_thread
from ...workers.job_queue import JobQueue
from .tasks import _read_json_object

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks/studio", tags=["studio"])

MAX_IMAGES = 12
MAX_FILE_BYTES = 150 * 1024 * 1024
STATUS_TTL = 30 * 24 * 3600
# Allows parameters such as "audio/webm;codecs=opus" from browser recordings.
DATA_URL = re.compile(r"^data:([\w/+.-]+)(?:;[\w.+-]+=[\w.+-]+)*;base64,(.*)$", re.S)


def studio_dir(job_id: str) -> Path:
    return Path(get_config().temp_dir) / "studio" / job_id


def _redis() -> redis.Redis:
    config = get_config()
    return redis.Redis(host=config.redis_host, port=config.redis_port, password=config.redis_password, decode_responses=True)


async def save_status(job_id: str, status: dict) -> None:
    client = _redis()
    try:
        await client.set(f"studio:{job_id}", json.dumps(status), ex=STATUS_TTL)
    finally:
        await client.aclose()


async def load_status(job_id: str) -> dict | None:
    client = _redis()
    try:
        raw = await client.get(f"studio:{job_id}")
    finally:
        await client.aclose()
    return json.loads(raw) if raw else None


async def _user(request: Request, db: AsyncSession) -> str:
    return await resolve_authenticated_user_id(request, db, get_config())


async def _owned(request: Request, db: AsyncSession, job_id: str) -> dict:
    user_id = await _user(request, db)
    status = await load_status(job_id) if re.fullmatch(r"[0-9a-f]{32}", job_id) else None
    if not status or status.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    return status


def _decode(data_url: str, allowed: tuple[str, ...]) -> tuple[bytes, str]:
    match = DATA_URL.match(data_url or "")
    if not match or not match.group(1).startswith(allowed):
        raise HTTPException(status_code=400, detail="Arquivo inválido")
    data = base64.b64decode(match.group(2))
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo muito grande (máx. 150 MB)")
    return data, match.group(1).split("/")[-1].split("+")[0]


@router.get("/voices")
async def voices(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    return {"voices": await list_voices()}


@router.post("/sample")
async def sample(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    payload = await _read_json_object(request)
    voice = str(payload.get("voice") or "")
    text = str(payload.get("text") or "Olá! Esta é a minha voz. Que o seu dia seja cheio de paz e esperança.")[:300]
    out = Path(get_config().temp_dir) / "studio" / "samples" / f"{uuid.uuid4().hex}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        spoken = apply_pronunciation(text, parse_pronunciation(payload.get("pronunciation")))
        await run_in_thread(
            synthesize, voice, spoken, int(payload.get("speed", 0)), out, parse_voice_settings(payload.get("voice_settings"))
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:300])
    data = out.read_bytes()
    out.unlink(missing_ok=True)
    return Response(data, media_type="audio/wav")


@router.post("/script")
async def script(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    payload = await _read_json_object(request)
    theme = str(payload.get("theme") or "").strip()
    if not theme:
        raise HTTPException(status_code=400, detail="Informe o tema")
    logger.info("Studio script requested (%s s): %.60s", payload.get("seconds", 45), theme)
    try:
        text = await write_script(theme, int(payload.get("seconds", 45)), str(payload.get("instructions") or ""))
    except Exception as exc:
        logger.error("Studio script failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Falha ao gerar roteiro: {exc}")
    return {"script": text}


@router.post("/videos")
async def create_video(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    payload = await _read_json_object(request)
    script_text = str(payload.get("script") or "").strip()
    voice = str(payload.get("voice") or "")
    fmt = payload.get("format") if payload.get("format") in FORMATS else "vertical"
    images = payload.get("images") or []
    if not script_text or not voice:
        raise HTTPException(status_code=400, detail="Roteiro e voz são obrigatórios")
    auto_background = payload.get("auto_background") is True
    picks = [p for p in payload.get("picks") or [] if isinstance(p, dict)][:MAX_IMAGES]
    if not isinstance(images, list) or len(images) + len(picks) > MAX_IMAGES or (not images and not picks and not auto_background):
        raise HTTPException(status_code=400, detail=f"Envie de 1 a {MAX_IMAGES} fotos ou vídeos de fundo, ou ligue o fundo automático")

    job_id = uuid.uuid4().hex
    directory = studio_dir(job_id)
    directory.mkdir(parents=True, exist_ok=True)
    image_names = []
    image_credits = []
    for index, pick in enumerate(picks):
        # Chosen in the background picker: copy the server-side file, keep its credit.
        token, name = str(pick.get("token") or ""), str(pick.get("file") or "")
        if not re.fullmatch(r"[0-9a-f]{32}", token) or not re.fullmatch(r"p\d{2}_[\w]+\.jpg", name) or await _pick_owner(token) != user_id:
            continue
        source = _picks_dir(token) / name
        if source.exists():
            target = f"pick_{index:02d}.jpg"
            shutil.copy(source, directory / target)
            image_names.append(target)
            if isinstance(pick.get("credit"), dict):
                image_credits.append({k: str(v)[:120] for k, v in pick["credit"].items() if k in ("title", "author", "license", "source", "ai")})
    starts: dict[str, float] = {}
    ends: dict[str, float] = {}
    for index, item in enumerate(images):
        data, ext = _decode(item, ("image/", "video/"))
        if item.startswith("data:video/"):
            name = f"bg_{index}.{ext if ext in ('mp4', 'webm', 'quicktime') else 'mp4'}"
        else:
            name = f"bg_{index}.{ext if ext in ('png', 'jpeg', 'jpg', 'webp') else 'jpg'}"
        (directory / name).write_bytes(data)
        image_names.append(name)
        # Per-video start offset in seconds ("Começar em"), same order as images.
        try:
            start = float((payload.get("image_starts") or [])[index] or 0)
        except (IndexError, TypeError, ValueError):
            start = 0.0
        if start > 0 and item.startswith("data:video/"):
            starts[name] = min(start, 600.0)
        try:
            end = float((payload.get("image_ends") or [])[index] or 0)
        except (IndexError, TypeError, ValueError):
            end = 0.0
        if end > start and item.startswith("data:video/"):
            ends[name] = min(end, 600.0)
    music_name = None
    music_credit = ""
    if payload.get("music_track"):
        # Picked in the music picker (catalogue or library): copy it into the job.
        from ...music import resolve_track

        try:
            track_path, music_credit = await run_in_thread(resolve_track, str(payload["music_track"]))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Música indisponível: {exc}")
        music_name = f"music{track_path.suffix.lower() or '.mp3'}"
        shutil.copy(track_path, directory / music_name)
    if payload.get("music") and not music_name:
        data, ext = _decode(payload["music"], ("audio/",))
        music_name = f"music.{ext if ext in ('mpeg', 'mp3', 'wav', 'ogg', 'aac') else 'mp3'}"
        (directory / music_name).write_bytes(data)

    (directory / "script.txt").write_text(script_text, encoding="utf-8")
    options = {
        "script": script_text,
        "voice": voice,
        "speed": int(payload.get("speed", 0)),
        "format": fmt,
        "captions": bool(payload.get("captions", True)),
        "images": image_names,
        "music": music_name,
        "music_volume": max(0.0, min(1.0, float(payload.get("music_volume", 0.12)))),
        "transition": payload.get("transition") if payload.get("transition") in TRANSITIONS else "fade",
        "voice_settings": parse_voice_settings(payload.get("voice_settings")),
        "pause": max(0.1, min(1.5, float(payload.get("pause") or 0.25))),
        "auto_background": auto_background,
        "music_credit": music_credit,
        "music_track": str(payload.get("music_track") or "")[:200],
        "outro": _outro_option(user_id, payload),
        "starts": starts,
        "ends": ends,
        "image_credits": image_credits,
        "look": str(payload.get("look") or "")[:20],
        "hook": payload.get("hook") is True,
        "hook_text": str(payload.get("hook_text") or "").strip()[:60],
        "sources": [str(x).strip()[:120] for x in payload.get("sources") or [] if str(x).strip()][:10],
        "cta_text": str(payload.get("cta_text") or "").strip()[:200],
        "cta_link": str(payload.get("cta_link") or "").strip()[:500],
        "pronunciation": [{"from": a, "to": b} for a, b in parse_pronunciation(payload.get("pronunciation"))],
        "effect": payload.get("effect") if payload.get("effect") in ("zoom", "pan", "static") else "zoom",
    }
    title = str(payload.get("title") or script_text[:60])
    await save_status(job_id, {"status": "queued", "user_id": user_id, "title": title, "format": fmt, "created_at": time.time()})
    client = _redis()
    try:
        await client.lpush(f"studio:user:{user_id}", job_id)
        await client.ltrim(f"studio:user:{user_id}", 0, 99)
    finally:
        await client.aclose()
    # Kept so "Editar" can reopen this video with the same choices.
    (directory / "options.json").write_text(json.dumps({**options, "title": title}, ensure_ascii=False), encoding="utf-8")
    await JobQueue.enqueue_job("studio_render_job", job_id, options)
    return {"id": job_id, "status": "queued"}


@router.get("/videos")
async def list_videos(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    client = _redis()
    try:
        ids = await client.lrange(f"studio:user:{user_id}", 0, 99)
    finally:
        await client.aclose()
    videos = []
    for job_id in ids:
        status = await load_status(job_id)
        if status and status.get("user_id") == user_id:
            videos.append({"id": job_id, **{k: v for k, v in status.items() if k != "user_id"}})
    return {"videos": videos}


@router.get("/videos/{job_id}")
async def video_status(job_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    status = await _owned(request, db, job_id)
    return {"id": job_id, **{k: v for k, v in status.items() if k != "user_id"}}


@router.get("/videos/{job_id}/file")
async def video_file(job_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await _owned(request, db, job_id)
    path = studio_dir(job_id) / "video.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Vídeo ainda não está pronto")
    return FileResponse(path, media_type="video/mp4", filename=f"video_{job_id[:8]}.mp4")


@router.delete("/videos/{job_id}")
async def delete_video(job_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    status = await _owned(request, db, job_id)
    if status.get("status") in ("queued", "rendering"):
        raise HTTPException(status_code=409, detail="Espere o vídeo terminar de gerar para excluir")
    client = _redis()
    try:
        await client.lrem(f"studio:user:{status['user_id']}", 0, job_id)
        await client.delete(f"studio:{job_id}")
    finally:
        await client.aclose()
    await run_in_thread(shutil.rmtree, studio_dir(job_id), True)
    return {"deleted": job_id}


def _pron_key(user_id: str) -> str:
    return f"studio:pron:{user_id}"


async def load_pronunciations(user_id: str) -> list[dict]:
    client = _redis()
    try:
        raw = await client.get(_pron_key(user_id))
    finally:
        await client.aclose()
    return json.loads(raw) if raw else [{"from": "Getúlio", "to": "Jetúlio"}]


@router.get("/pronunciations")
async def get_pronunciations(request: Request, db: AsyncSession = Depends(get_db)):
    return {"items": await load_pronunciations(await _user(request, db))}


@router.put("/pronunciations")
async def put_pronunciations(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    payload = await _read_json_object(request)
    items = [{"from": a, "to": b} for a, b in parse_pronunciation(payload.get("items"))]
    client = _redis()
    try:
        await client.set(_pron_key(user_id), json.dumps(items, ensure_ascii=False))
    finally:
        await client.aclose()
    return {"items": items}


@router.post("/pronunciations/review")
async def review_script_pronunciation(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    payload = await _read_json_object(request)
    script_text = str(payload.get("script") or "").strip()
    if not script_text:
        raise HTTPException(status_code=400, detail="Escreva o roteiro primeiro")
    known = [item["from"] for item in await load_pronunciations(user_id)]
    try:
        hints = await review_pronunciation(script_text, known)
    except Exception as exc:
        logger.error("Pronunciation review failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Falha na revisão: {exc}")
    return {"hints": hints}


@router.post("/videos/{job_id}/post-text")
async def regenerate_post_text(job_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """(Re)write title options, description and hashtags from the video's script."""
    status = await _owned(request, db, job_id)
    script_path = studio_dir(job_id) / "script.txt"
    script_text = script_path.read_text(encoding="utf-8") if script_path.exists() else status.get("title", "")
    try:
        status["post"] = await write_post_text(script_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao gerar o texto: {exc}")
    await save_status(job_id, status)
    return status["post"]


@router.post("/script/fix")
async def fix_script(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    payload = await _read_json_object(request)
    text = str(payload.get("script") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Escreva o roteiro primeiro")
    try:
        return {"script": await fix_spelling(text)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha na correção: {exc}")


@router.post("/ideas")
async def ideas(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    payload = await _read_json_object(request)
    subject = str(payload.get("subject") or "").strip()
    if not subject:
        raise HTTPException(status_code=400, detail="Diga o assunto do canal")
    avoid = [str(a) for a in payload.get("avoid") or [] if isinstance(a, str)]
    try:
        return {"ideas": await suggest_ideas(subject, 8, avoid)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao sugerir temas: {exc}")


# "Monte sua voz": same folder, cleanup and metadata as the VTube app, so a
# voice made in either app shows up in both (voice-clone service reads /vozes).
VOICES_DIR = Path("/vozes")
VOICE_FILTER = "highpass=f=70,afftdn=nf=-25,loudnorm=I=-18:TP=-2,silenceremove=start_periods=1:start_threshold=-45dB"
VOICE_MIN_SECONDS, VOICE_MAX_SECONDS = 5.0, 30.0


def _voice_slug(name: str) -> str:
    import unicodedata

    plain = "".join(c for c in unicodedata.normalize("NFKD", name.lower()) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:48]


def _make_voice(raw: Path, target: Path) -> float:
    import subprocess

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)],
        capture_output=True, text=True,
    )
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        raise ValueError("Não consegui ler esse áudio. Tente gravar de novo ou enviar MP3/WAV.")
    if duration < VOICE_MIN_SECONDS:
        raise ValueError(f"A gravação precisa de pelo menos {VOICE_MIN_SECONDS:.0f} segundos de fala.")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", VOICE_FILTER, "-t", f"{VOICE_MAX_SECONDS}",
         "-ar", "24000", "-ac", "1", str(target)],
        check=True, capture_output=True,
    )
    return min(duration, VOICE_MAX_SECONDS)


@router.post("/my-voices")
async def create_my_voice(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    payload = await _read_json_object(request)
    name = str(payload.get("name") or "").strip()[:40]
    slug = _voice_slug(name)
    if not slug:
        raise HTTPException(status_code=400, detail="Dê um nome à voz (letras e números).")
    if payload.get("consent") is not True:
        raise HTTPException(status_code=400, detail="Confirme que a voz é sua ou que a pessoa autorizou.")
    gender = payload.get("gender") if payload.get("gender") in ("Male", "Female") else "Male"
    if not VOICES_DIR.is_dir():
        raise HTTPException(status_code=503, detail="Pasta de vozes não encontrada (VOICES_DIR).")
    data, ext = _decode(str(payload.get("audio") or ""), ("audio/", "video/"))
    raw = VOICES_DIR / f".{slug}.upload.{ext or 'bin'}"
    target = VOICES_DIR / f"{slug}.wav"
    raw.write_bytes(data)
    try:
        seconds = await run_in_thread(_make_voice, raw, target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Voice creation failed: %s", getattr(exc, "stderr", exc))
        raise HTTPException(status_code=500, detail="Falha ao preparar a gravação")
    finally:
        raw.unlink(missing_ok=True)
    (VOICES_DIR / f"{slug}.json").write_text(
        json.dumps({"nome": name, "genero": gender, "autorizado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, ensure_ascii=False),
        encoding="utf-8",
    )
    return {"id": f"vs:{slug}", "seconds": round(seconds, 1)}


@router.delete("/my-voices/{slug}")
async def delete_my_voice(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", slug):
        raise HTTPException(status_code=400, detail="Voz inválida")
    for suffix in (".wav", ".json"):
        (VOICES_DIR / f"{slug}{suffix}").unlink(missing_ok=True)
    return {"deleted": slug}


@router.post("/script/check")
async def check_script_facts(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    payload = await _read_json_object(request)
    text = str(payload.get("script") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Escreva o roteiro primeiro")
    try:
        return await fact_check(text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha na conferência: {exc}")


# ---------------------------------------------------------------------------
# Background picker: the user sees and chooses images per part before rendering.

def _picks_dir(token: str) -> Path:
    return Path(get_config().temp_dir) / "studio" / "picks" / token


async def _pick_owner(token: str) -> str | None:
    client = _redis()
    try:
        return await client.get(f"studio:pick:{token}")
    finally:
        await client.aclose()


async def _make_options(directory: Path, part: int, query: str, source: str, style: str, vertical: bool, seeds: list[int], skip: set[str]):
    from ...studio import download_image, generate_ai_image, search_free_options

    options = []
    if source == "ai":
        for seed in seeds:
            name = f"p{part:02d}_ai{seed}.jpg"
            try:
                credit = await run_in_thread(generate_ai_image, query, directory / name, vertical, seed)
                options.append({"file": name, "credit": credit})
            except Exception as exc:
                logger.info("AI image failed: %s", exc)
    else:
        found = await run_in_thread(search_free_options, query, vertical, 6)
        for index, item in enumerate(o for o in found if o["url"] not in skip):
            if len(options) >= len(seeds):
                break
            name = f"p{part:02d}_{uuid.uuid4().hex[:8]}.jpg"
            try:
                await run_in_thread(download_image, item["url"], directory / name)
                options.append({"file": name, "credit": item})
            except Exception as exc:
                logger.info("Free image download failed: %s", exc)
    return options


@router.post("/backgrounds/plan")
async def plan_backgrounds(request: Request, db: AsyncSession = Depends(get_db)):
    """Image suggestions for each part of the script (free photos or AI images)."""
    import asyncio

    from ...studio import STYLES, _script_parts, plan_ai_prompts, plan_background_queries

    user_id = await _user(request, db)
    payload = await _read_json_object(request)
    script_text = str(payload.get("script") or "").strip()
    if not script_text:
        raise HTTPException(status_code=400, detail="Escreva o roteiro primeiro")
    source = "ai" if payload.get("source") == "ai" else "free"
    style = payload.get("style") if payload.get("style") in STYLES else "cinema"
    vertical = payload.get("format") != "horizontal"
    count = max(2, min(12, round(len(script_text.split()) / 2.5 / 4)))
    try:
        queries = await (plan_ai_prompts(script_text, count, style) if source == "ai" else plan_background_queries(script_text, count))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao planejar as imagens: {exc}")
    token = uuid.uuid4().hex
    directory = _picks_dir(token)
    directory.mkdir(parents=True, exist_ok=True)
    client = _redis()
    try:
        await client.set(f"studio:pick:{token}", user_id, ex=7 * 24 * 3600)
    finally:
        await client.aclose()
    semaphore = asyncio.Semaphore(3)

    async def one(index: int, query: str):
        async with semaphore:
            if source == "ai":
                return []  # AI images are slow (free tier: 1 per 45 s); the page asks for them one by one.
            return await _make_options(directory, index, query, source, style, vertical, [1, 2, 3], set())

    options = await asyncio.gather(*(one(i, q) for i, q in enumerate(queries)))
    texts = _script_parts(script_text, count)
    return {
        "token": token,
        "source": source,
        "parts": [{"text": t, "query": q, "options": o} for t, q, o in zip(texts, queries, options)],
    }


@router.post("/backgrounds/more")
async def more_backgrounds(request: Request, db: AsyncSession = Depends(get_db)):
    """Another option for one part (a new AI render or the next free photo)."""
    user_id = await _user(request, db)
    payload = await _read_json_object(request)
    token = str(payload.get("token") or "")
    if not re.fullmatch(r"[0-9a-f]{32}", token) or await _pick_owner(token) != user_id:
        raise HTTPException(status_code=404, detail="Sugestões expiradas. Gere de novo.")
    part = int(payload.get("part", 0))
    seed = int(payload.get("seed", 0)) or int(time.time()) % 100000
    skip = {str(u) for u in payload.get("skip") or []}
    options = await _make_options(
        _picks_dir(token), part, str(payload.get("query") or "")[:900],
        "ai" if payload.get("source") == "ai" else "free", "cinema", payload.get("format") != "horizontal", [seed], skip,
    )
    if not options:
        raise HTTPException(status_code=404, detail="Não achei outra imagem para este trecho. Tente editar a busca.")
    return {"options": options}


@router.get("/backgrounds/{token}/{name}")
async def background_file(token: str, name: str, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    if not re.fullmatch(r"[0-9a-f]{32}", token) or not re.fullmatch(r"p\d{2}_[\w]+\.jpg", name) or await _pick_owner(token) != user_id:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    path = _picks_dir(token) / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(path, media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Channel profiles: each of the user's channels keeps its own defaults.

PROFILE_KEYS = {
    "name": str, "subject": str, "voice": str, "tone": str, "speed": int, "accent": int, "expressive": int,
    "cta_on": bool, "cta_text": str, "cta_link": str, "look": str, "image_source": str, "image_style": str,
    "format": str, "transition": str, "effect": str, "hook": bool, "seconds": int,
    "outro": str, "outro_channel": str, "pause": float, "outro_audio": str, "outro_text": str,
}
MAX_PROFILES = 10


def _clean_profile(raw: dict) -> dict | None:
    profile = {"id": str(raw.get("id") or uuid.uuid4().hex[:12])[:24]}
    for key, kind in PROFILE_KEYS.items():
        value = raw.get(key)
        if value is None:
            continue
        try:
            profile[key] = kind(value) if kind is not str else str(value)[:300]
        except (TypeError, ValueError):
            continue
    return profile if profile.get("name", "").strip() else None


@router.get("/profiles")
async def get_profiles(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    client = _redis()
    try:
        raw = await client.get(f"studio:profiles:{user_id}")
    finally:
        await client.aclose()
    return {"profiles": json.loads(raw) if raw else []}


@router.put("/profiles")
async def put_profiles(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _user(request, db)
    payload = await _read_json_object(request)
    profiles = [p for p in (_clean_profile(r) for r in payload.get("profiles") or [] if isinstance(r, dict)) if p][:MAX_PROFILES]
    client = _redis()
    try:
        await client.set(f"studio:profiles:{user_id}", json.dumps(profiles, ensure_ascii=False))
    finally:
        await client.aclose()
    return {"profiles": profiles}


# ---------------------------------------------------------------------------
# Background music: AI suggestions (Incompetech, CC BY), the user's library
# folder (/musicas) and uploads from the PC. Every track can be played first.

@router.post("/music/suggest")
async def music_suggest(request: Request, db: AsyncSession = Depends(get_db)):
    from ...music import suggest_tracks

    await _user(request, db)
    payload = await _read_json_object(request)
    text = str(payload.get("script") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Escreva o roteiro primeiro")
    try:
        return await suggest_tracks(text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao sugerir músicas: {exc}")


@router.get("/music/library")
async def music_library(request: Request, db: AsyncSession = Depends(get_db)):
    from ...music import library_tracks

    await _user(request, db)
    return {"tracks": await run_in_thread(library_tracks)}


@router.post("/music/library")
async def music_upload(request: Request, db: AsyncSession = Depends(get_db)):
    from ...music import AUDIO_SUFFIXES, LIBRARY_DIR

    await _user(request, db)
    payload = await _read_json_object(request)
    data, _ = _decode(str(payload.get("audio") or ""), ("audio/",))
    original = Path(str(payload.get("name") or "musica.mp3")).name
    stem = re.sub(r"[^\w\- ]+", "", Path(original).stem).strip()[:60] or "musica"
    suffix = Path(original).suffix.lower() if Path(original).suffix.lower() in AUDIO_SUFFIXES else ".mp3"
    if not LIBRARY_DIR.is_dir():
        raise HTTPException(status_code=503, detail="Pasta de músicas não encontrada")
    target = LIBRARY_DIR / f"{stem}{suffix}"
    copy = 2
    while target.exists():
        # Never overwrite a track another video or channel profile already uses.
        target = LIBRARY_DIR / f"{stem}-{copy}{suffix}"
        copy += 1
    target.write_bytes(data)
    return {"id": f"local:{target.name}", "title": stem}


@router.get("/music/play")
async def music_play(id: str, request: Request, db: AsyncSession = Depends(get_db)):
    from ...music import resolve_track

    await _user(request, db)
    try:
        path, _ = await run_in_thread(resolve_track, id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=502, detail="Não consegui baixar essa música agora")
    media = {".wav": "audio/wav", ".ogg": "audio/ogg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".flac": "audio/flac"}
    return FileResponse(path, media_type=media.get(path.suffix.lower(), "audio/mpeg"))


MEDIA_NAME = re.compile(r"^(bg_\d+|pick_\d+|auto_\d+)\.(mp4|webm|quicktime|png|jpeg|jpg|webp)$")


@router.get("/videos/{job_id}/settings")
async def video_settings(job_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Choices used for a video, so the studio can reopen it for editing."""
    status = await _owned(request, db, job_id)
    directory = studio_dir(job_id)
    saved = directory / "options.json"
    if saved.exists():
        options = json.loads(saved.read_text(encoding="utf-8"))
    else:
        # Videos made before settings were saved: script and media only.
        script_path = directory / "script.txt"
        options = {
            "script": script_path.read_text(encoding="utf-8") if script_path.exists() else "",
            "title": status.get("title", ""),
            "format": status.get("format", "vertical"),
            "images": sorted(p.name for p in directory.glob("*") if MEDIA_NAME.match(p.name)),
        }
    media = [name for name in options.get("images") or [] if MEDIA_NAME.match(name) and (directory / name).exists()]
    if options.get("auto_background"):
        # Images found automatically during the render reopen as normal backgrounds.
        media += sorted(p.name for p in directory.glob("auto_*.jpg") if MEDIA_NAME.match(p.name))
    return {"options": options, "media": media}


@router.get("/videos/{job_id}/media/{name}")
async def video_media(job_id: str, name: str, request: Request, db: AsyncSession = Depends(get_db)):
    await _owned(request, db, job_id)
    path = studio_dir(job_id) / name
    if not MEDIA_NAME.match(name) or not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    types = {".mp4": "video/mp4", ".webm": "video/webm", ".quicktime": "video/quicktime", ".png": "image/png", ".webp": "image/webp"}
    return FileResponse(path, media_type=types.get(path.suffix.lower(), "image/jpeg"))


# ---------------------------------------------------------------------------
# Outros (vinhetas finais), kept per channel in canais/<canal>/vinhetas/.
# The outro can keep its own sound or have the narrator say a line over it.

CHANNELS_DIR = Path("/canais")
OUTRO_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v"}


def _safe_part(value: str) -> str:
    return re.sub(r"[^\w\- &.()]+", "", value).strip(" .")[:60]


def _outro_file(outro_id: str) -> Path | None:
    """``<canal>/<arquivo>`` -> the file in canais/<canal>/vinhetas, if it exists."""
    channel, _, name = (outro_id or "").partition("/")
    if not channel or not name or _safe_part(channel) != channel or _safe_part(name) != name:
        return None
    path = CHANNELS_DIR / channel / "vinhetas" / name
    return path if path.suffix.lower() in OUTRO_SUFFIXES and path.is_file() else None


@router.get("/outros")
async def list_outros(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    channels = []
    for folder in sorted(CHANNELS_DIR.glob("*/vinhetas")) if CHANNELS_DIR.is_dir() else []:
        outros = [
            {"id": f"{folder.parent.name}/{f.name}", "name": f.stem}
            for f in sorted(folder.iterdir()) if f.suffix.lower() in OUTRO_SUFFIXES
        ]
        if outros:
            cta = folder.parent / "cta.txt"
            channels.append({
                "channel": folder.parent.name,
                "outros": outros,
                "cta": cta.read_text(encoding="utf-8").strip() if cta.is_file() else "",
            })
    return {"channels": channels}


@router.post("/outros/cta")
async def save_outro_cta(request: Request, db: AsyncSession = Depends(get_db)):
    """Frase final que o narrador fala sobre a vinheta, guardada por canal (canais/<canal>/cta.txt)."""
    await _user(request, db)
    payload = await _read_json_object(request)
    channel = _safe_part(str(payload.get("channel") or ""))
    text = str(payload.get("text") or "").strip()[:300]
    if not channel or not (CHANNELS_DIR / channel).is_dir():
        raise HTTPException(status_code=404, detail="Canal não encontrado")
    (CHANNELS_DIR / channel / "cta.txt").write_text(text, encoding="utf-8")
    return {"channel": channel, "cta": text}


@router.get("/outros/file")
async def outro_file(id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    path = _outro_file(id)
    if not path:
        raise HTTPException(status_code=404, detail="Vinheta não encontrada")
    return FileResponse(path, media_type="video/mp4")


@router.post("/outros")
async def upload_outro(request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    payload = await _read_json_object(request)
    channel = _safe_part(str(payload.get("channel") or "")) or "Geral"
    name = _safe_part(Path(str(payload.get("name") or "vinheta")).stem) or "vinheta"
    data, ext = _decode(str(payload.get("video") or ""), ("video/",))
    folder = CHANNELS_DIR / channel / "vinhetas"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{name}.{ext if ext in ('mp4', 'webm') else 'mp4'}"
    target.write_bytes(data)
    return {"id": f"{channel}/{target.name}"}


@router.delete("/outros")
async def delete_outro(id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await _user(request, db)
    if path := _outro_file(id):
        path.unlink(missing_ok=True)
    return {"deleted": id}


def _outro_option(user_id: str, payload: dict) -> dict | None:
    path = _outro_file(str(payload.get("outro") or ""))
    if not path:
        return None
    narrator = payload.get("outro_audio") == "narrator"
    return {
        "style": "custom",
        "id": str(payload.get("outro")),
        "path": str(path),
        "audio": "narrator" if narrator else "original",
        "text": str(payload.get("outro_text") or "").strip()[:200] if narrator else "",
    }

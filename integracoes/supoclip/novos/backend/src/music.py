"""Background music without copyright trouble.

Two sources: the Incompetech catalogue (Kevin MacLeod, CC BY 4.0, ~1,400
tracks tagged by mood; credit goes into the description) and the user's own
library folder (/musicas), e.g. tracks downloaded from the YouTube Audio
Library. The AI reads the script and picks moods; tracks are ranked by them.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
from pathlib import Path

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .config import get_config

logger = logging.getLogger(__name__)

CATALOGUE_URL = "https://incompetech.com/music/royalty-free/pieces.json"
TRACK_URL = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
USER_AGENT = "SupoClipLocal/1.0 (https://github.com/FujiwaraChoki/supoclip; self-hosted)"
LIBRARY_DIR = Path("/musicas")
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}
FEELS = [
    "Dark", "Grooving", "Relaxed", "Bright", "Calming", "Bouncy", "Driving", "Mysterious", "Intense", "Eerie",
    "Unnerving", "Somber", "Mystical", "Uplifting", "Humorous", "Epic", "Action", "Suspenseful", "Aggressive",
]
_catalogue: list[dict] | None = None
_catalogue_at = 0.0


def catalogue() -> list[dict]:
    """Incompetech pieces, cached for a day. Blocking."""
    global _catalogue, _catalogue_at
    cache = Path(get_config().temp_dir) / "music" / "incompetech.json"
    if _catalogue is not None and time.time() - _catalogue_at < 86400:
        return _catalogue
    try:
        if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
            _catalogue = json.loads(cache.read_text(encoding="utf-8"))
        else:
            response = httpx.get(CATALOGUE_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
            response.raise_for_status()
            _catalogue = response.json()
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(_catalogue), encoding="utf-8")
    except Exception as exc:
        logger.warning("Incompetech catalogue unavailable: %s", exc)
        _catalogue = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else []
    _catalogue_at = time.time()
    return _catalogue


def _seconds(length: str) -> int:
    try:
        h, m, s = (int(x) for x in (length or "0:0:0").split(":"))
        return h * 3600 + m * 60 + s
    except ValueError:
        return 0


class MusicBrief(BaseModel):
    feels: list[str] = Field(description="2 a 4 climas da lista dada, do mais importante para o menos")
    keywords: list[str] = Field(description="3 a 6 palavras em inglês para a descrição da música (ex.: piano, choir, cinematic, tension)")
    reason: str = Field(description="Uma frase em português explicando o clima escolhido")


async def suggest_tracks(script: str, limit: int = 8) -> dict:
    """AI picks the mood for the script; returns the best-matching catalogue tracks."""
    from .ai import _build_transcript_model

    config = get_config()
    agent = Agent(
        model=_build_transcript_model(config, config.studio_llm),
        output_type=MusicBrief,
        system_prompt=(
            "Você é editor musical de vídeos curtos. Leia o roteiro e escolha o clima da trilha de fundo, que deve "
            "acompanhar sem competir com a narração. Climas possíveis: " + ", ".join(FEELS)
        ),
    )
    brief = (await agent.run(script.strip()[:4000])).output
    feels = [f for f in brief.feels if f in FEELS] or ["Calming"]
    words = [w.lower() for w in brief.keywords]
    from .utils.async_helpers import run_in_thread

    pieces = await run_in_thread(catalogue)
    scored = []
    for piece in pieces:
        piece_feels = [f.strip() for f in (piece.get("feel") or "").split(",")]
        if not piece.get("filename") or _seconds(piece.get("length")) < 45:
            continue
        score = sum(3 - min(i, 2) for i, f in enumerate(feels) if f in piece_feels)
        text = f"{piece.get('description', '')} {piece.get('instruments', '')}".lower()
        score += sum(1 for w in words if w in text)
        if score > 0:
            scored.append((score, piece))
    scored.sort(key=lambda item: item[0], reverse=True)
    tracks = [
        {
            "id": f"incompetech:{p['filename']}",
            "title": p["title"],
            "description": p.get("description") or "",
            "feel": p.get("feel") or "",
            "length": p.get("length") or "",
            "credit": f"Música: {p['title']} – Kevin MacLeod (incompetech.com), licença CC BY 4.0",
        }
        for _, p in scored[:limit]
    ]
    return {"reason": brief.reason, "feels": feels, "tracks": tracks}


def library_tracks() -> list[dict]:
    if not LIBRARY_DIR.is_dir():
        return []
    return [
        {"id": f"local:{p.name}", "title": p.stem, "description": "Da sua biblioteca", "feel": "", "length": "", "credit": ""}
        for p in sorted(LIBRARY_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if p.suffix.lower() in AUDIO_SUFFIXES and not p.name.startswith(".")
    ]


def resolve_track(track_id: str) -> tuple[Path, str]:
    """Local file for a track id (downloads Incompetech tracks once) and its credit. Blocking."""
    kind, _, name = track_id.partition(":")
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("Música inválida")
    if kind == "local":
        path = LIBRARY_DIR / name
        if not path.is_file():
            raise ValueError("Música não encontrada na biblioteca")
        return path, ""
    if kind == "incompetech":
        piece = next((p for p in catalogue() if p.get("filename") == name), None)
        if not piece:
            raise ValueError("Música não encontrada no catálogo")
        cache = Path(get_config().temp_dir) / "music" / name
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            response = httpx.get(TRACK_URL + urllib.parse.quote(name), headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True)
            response.raise_for_status()
            cache.write_bytes(response.content)
        return cache, f"Música: {piece['title']} – Kevin MacLeod (incompetech.com), licença CC BY 4.0"
    raise ValueError("Música inválida")

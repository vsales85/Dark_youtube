"""News-style voice-over for finished clips.

A narration is a script (written by the configured LLM, edited by the user),
spoken by the local voice-clone service (OpenAI-style /v1/audio/speech) and
mixed over the clip. The original audio stays underneath at a chosen volume
and comes back at full volume inside "original" ranges, where the narration
pauses so the person on screen can be heard.

Script blocks are separated by blank lines; block N is spoken in the N-th gap
between original ranges.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import uuid
from pathlib import Path

import httpx
from pydantic_ai import Agent

from .config import get_config

logger = logging.getLogger(__name__)

WORDS_PER_SECOND = 2.5
MAX_TEMPO = 1.3
SPEECH_TIMEOUT_SECONDS = 600

narration_system_prompt = """Você é roteirista de um canal de notícias e curiosidades em vídeos curtos.
Escreva a narração em português do Brasil, no tom de uma matéria de TV: direta, envolvente, frases curtas.
Abra com um gancho forte na primeira frase. Não invente fatos que não estejam na transcrição.
Responda apenas com o texto a ser falado, sem títulos, aspas, marcações ou instruções de cena.
Quando pedirem vários blocos, separe cada bloco com uma linha em branco."""


def _speech_gaps(duration: float, original_ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Clip spans not covered by original ranges, in order."""
    gaps, cursor = [], 0.0
    for start, end in sorted(original_ranges):
        start, end = max(0.0, start), min(duration, end)
        if end <= start:
            continue
        if start - cursor > 0.5:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if duration - cursor > 0.5:
        gaps.append((cursor, duration))
    return gaps


def normalize_ranges(raw: object, duration: float) -> list[tuple[float, float]]:
    ranges = []
    for item in raw if isinstance(raw, list) else []:
        try:
            start, end = float(item[0]), float(item[1])
        except (TypeError, ValueError, IndexError, KeyError):
            raise ValueError("original_ranges must be [start, end] pairs in seconds")
        start, end = max(0.0, start), min(duration, end)
        if end > start:
            ranges.append((start, end))
    return sorted(ranges)


def split_script(script: str) -> list[str]:
    blocks = [" ".join(block.split()) for block in script.replace("\r\n", "\n").split("\n\n")]
    return [block for block in blocks if block]


async def write_script(transcript: str, duration: float, original_ranges: list[tuple[float, float]], instructions: str = "") -> str:
    from .ai import _build_transcript_model, _get_missing_llm_key_error

    config = get_config()
    if error := _get_missing_llm_key_error(config.llm, config):
        raise RuntimeError(error)
    gaps = _speech_gaps(duration, original_ranges) or [(0.0, duration)]
    budget = "\n".join(
        f"- Bloco {i + 1}: no máximo {max(3, int((end - start) * WORDS_PER_SECOND))} palavras"
        for i, (start, end) in enumerate(gaps)
    )
    prompt = (
        f"O clipe tem {duration:.0f} segundos. Escreva exatamente {len(gaps)} bloco(s) de narração:\n"
        f"{budget}\n\n"
        + (f"Orientação do editor: {instructions.strip()}\n\n" if instructions.strip() else "")
        + f"Transcrição do que é falado no clipe:\n{transcript.strip()[:6000]}"
    )
    agent = Agent(
        model=_build_transcript_model(config, config.llm),
        output_type=str,
        system_prompt=narration_system_prompt,
    )
    result = await agent.run(prompt)
    return result.output.strip()


async def list_voices() -> list[dict]:
    url = f"{get_config().voice_clone_url}/v1/audio/voices"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url)
        response.raise_for_status()
    data = response.json()
    return data.get("data", data) if isinstance(data, dict) else data


def _synthesize(text: str, voice: str, out_path: Path) -> None:
    url = f"{get_config().voice_clone_url}/v1/audio/speech"
    response = httpx.post(
        url,
        json={"voice": voice, "input": text, "response_format": "wav"},
        timeout=SPEECH_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Voice service failed ({response.status_code}): {response.text[:200]}")
    out_path.write_bytes(response.content)


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def render_narration(
    input_path: Path,
    output_dir: Path,
    script: str,
    voice: str,
    original_volume: float,
    original_ranges: list[tuple[float, float]],
) -> Path:
    """Speak the script and mix it over the clip. Blocking; run in a thread."""
    duration = _probe_duration(input_path)
    gaps = _speech_gaps(duration, original_ranges) or [(0.0, duration)]
    blocks = split_script(script)
    if not blocks:
        raise ValueError("Narration script is empty")
    if len(blocks) > len(gaps):
        # More text than gaps: the extra blocks join the last gap.
        blocks = blocks[: len(gaps) - 1] + [" ".join(blocks[len(gaps) - 1:])]

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"narrated_{uuid.uuid4().hex[:12]}.mp4"
    with tempfile.TemporaryDirectory() as work:
        inputs, filters, labels = ["-i", str(input_path)], [], []
        for index, (text, (start, end)) in enumerate(zip(blocks, gaps)):
            wav = Path(work) / f"block_{index}.wav"
            _synthesize(text, voice, wav)
            spoken = _probe_duration(wav)
            room = end - start
            tempo = min(MAX_TEMPO, max(1.0, spoken / room)) if room > 0 else 1.0
            if spoken / tempo > room + 0.05:
                logger.warning("Narration block %s is %.1fs for a %.1fs gap; trimming", index, spoken, room)
            inputs += ["-i", str(wav)]
            delay_ms = int(start * 1000)
            filters.append(
                f"[{index + 1}:a]aresample=48000,atempo={tempo:.3f},atrim=0:{room:.3f},"
                f"adelay={delay_ms}|{delay_ms},apad[n{index}]"
            )
            labels.append(f"[n{index}]")

        loud = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in original_ranges) or "0"
        volume = max(0.0, min(1.0, original_volume))
        filters.append(f"[0:a]aresample=48000,volume='if({loud},1,{volume:.3f})':eval=frame[orig]")
        filters.append(
            f"[orig]{''.join(labels)}amix=inputs={len(labels) + 1}:duration=first:normalize=0,"
            f"alimiter=limit=0.95[aout]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", *inputs,
                "-filter_complex", ";".join(filters),
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(output_path),
            ],
            check=True, capture_output=True, text=True,
        )
    return output_path

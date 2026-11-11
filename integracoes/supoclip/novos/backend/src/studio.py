"""Videos made from scratch: script + narrator voice + background images + captions.

Mirrors the VTube voice setup: Edge TTS (``edge:pt-BR-AntonioNeural``),
Gemini TTS (``gemini:Charon``, needs GEMINI_API_KEY or GOOGLE_API_KEY) and
the local VoiceStudio clone service (``vs:<id>``, VOICE_CLONE_URL).
Captions come from faster-whisper word timings on the finished narration.
"""

from __future__ import annotations

import asyncio
import base64
import threading
import urllib.parse
import logging
import os
import subprocess
from pathlib import Path

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .config import get_config

logger = logging.getLogger(__name__)

GEMINI_VOICES = [
    ("Kore", "Female"), ("Aoede", "Female"), ("Leda", "Female"), ("Zephyr", "Female"),
    ("Callirrhoe", "Female"), ("Autonoe", "Female"), ("Despina", "Female"), ("Erinome", "Female"),
    ("Laomedeia", "Female"), ("Achernar", "Female"), ("Gacrux", "Female"), ("Pulcherrima", "Female"),
    ("Vindemiatrix", "Female"), ("Sulafat", "Female"),
    ("Charon", "Male"), ("Puck", "Male"), ("Fenrir", "Male"), ("Orus", "Male"), ("Enceladus", "Male"),
    ("Iapetus", "Male"), ("Umbriel", "Male"), ("Algieba", "Male"), ("Algenib", "Male"),
    ("Rasalgethi", "Male"), ("Sadachbia", "Male"), ("Sadaltager", "Male"), ("Schedar", "Male"),
    ("Achird", "Male"), ("Zubenelgenubi", "Male"), ("Alnilam", "Male"),
]
GEMINI_TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-2.5-flash-preview-tts"]
FORMATS = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
# Rumble cut, denoise, and a soft gate so pauses are quiet (cloned voices only).
CLONE_VOICE_CLEANUP = "highpass=f=80,afftdn=nf=-30:tn=1,agate=threshold=0.02:ratio=4:attack=5:release=150:range=0.05"
FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
WORDS_PER_SECOND = 2.5

script_system_prompt = """Você é roteirista de vídeos curtos de narração (reflexão, fé, curiosidades, histórias).
Escreva em português do Brasil, para ser falado por um narrador: frases curtas, ritmo calmo e envolvente.
Comece com um gancho forte na primeira frase e termine com uma frase marcante.
Se o tema for bíblico, cite a passagem com fidelidade (livro, capítulo e versículo).
Responda apenas com o texto a ser falado, sem títulos, marcações, emojis ou instruções de cena."""


def _gemini_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or get_config().google_api_key


async def list_voices() -> list[dict]:
    voices: list[dict] = []
    try:
        import edge_tts

        for v in await edge_tts.list_voices():
            if v.get("Locale", "").startswith("pt-"):
                name = v["ShortName"].split("-")[-1].replace("Neural", "").replace("Multilingual", " Multilíngue")
                voices.append({"id": f"edge:{v['ShortName']}", "name": name, "gender": v.get("Gender"), "group": f"Edge ({v['Locale']})"})
    except Exception as exc:
        logger.warning("Edge TTS voices unavailable: %s", exc)
    if _gemini_key():
        voices += [{"id": f"gemini:{n}", "name": n, "gender": g, "group": "Gemini"} for n, g in GEMINI_VOICES]
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{get_config().voice_clone_url}/v1/audio/voices")
            for v in response.json().get("data", []):
                voices.append({"id": f"vs:{v['voice_id']}", "name": v.get("name") or v["voice_id"], "gender": v.get("gender"), "group": "Minhas vozes"})
    except Exception as exc:
        logger.info("Voice clone service unavailable: %s", exc)
    return voices


async def write_script(theme: str, seconds: int, instructions: str = "") -> str:
    from .ai import _build_transcript_model, _get_missing_llm_key_error

    config = get_config()
    if error := _get_missing_llm_key_error(config.studio_llm, config):
        raise RuntimeError(error)
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=str, system_prompt=script_system_prompt)
    prompt = (
        f"Tema: {theme.strip()}\n"
        f"Duração falada: cerca de {seconds} segundos (no máximo {int(seconds * WORDS_PER_SECOND)} palavras).\n"
        + (f"Orientação: {instructions.strip()}\n" if instructions.strip() else "")
    )
    return (await agent.run(prompt)).output.strip()


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, capture_output=True, text=True)


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def parse_pronunciation(raw: object) -> list[tuple[str, str]]:
    """``[{"from": "Getúlio", "to": "Jetúlio"}]`` -> pairs, ignoring blanks."""
    pairs = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            written, spoken = str(item.get("from") or "").strip(), str(item.get("to") or "").strip()
            if written and spoken and written.lower() != spoken.lower():
                pairs.append((written[:60], spoken[:60]))
    return pairs[:200]


def _replace_words(text: str, pairs: list[tuple[str, str]], reverse: bool = False) -> str:
    import re

    for written, spoken in pairs:
        source, target = (spoken, written) if reverse else (written, spoken)
        text = re.sub(rf"(?<!\w){re.escape(source)}(?!\w)", target, text, flags=re.IGNORECASE)
    return text


def apply_pronunciation(text: str, pairs: list[tuple[str, str]]) -> str:
    """Respell words for the voice only; captions keep the original spelling."""
    return _replace_words(text, pairs)


def parse_voice_settings(raw: object) -> dict:
    """Chatterbox knobs for cloned voices: cfg_weight 0-1, exaggeration 0.25-2."""
    settings = {}
    if isinstance(raw, dict):
        for key, low, high in (("cfg_weight", 0.0, 1.0), ("exaggeration", 0.25, 2.0)):
            try:
                if raw.get(key) is not None:
                    settings[key] = min(high, max(low, float(raw[key])))
            except (TypeError, ValueError):
                pass
    return settings


def synthesize(voice: str, text: str, speed: int, out_path: Path, voice_settings: dict | None = None) -> Path:
    """Speak ``text`` into ``out_path`` (wav). ``speed`` is -30..30 percent. Blocking."""
    speed = max(-30, min(30, int(speed)))
    raw = out_path.with_suffix(".raw")
    kind, _, name = voice.partition(":")
    if kind == "edge":
        import edge_tts

        rate = f"{speed:+d}%"
        asyncio.run(edge_tts.Communicate(text, name, rate=rate).save(str(raw)))
        _ffmpeg("-i", str(raw), "-ac", "1", "-ar", "24000", str(out_path))
    elif kind == "gemini":
        key = _gemini_key()
        if not key:
            raise RuntimeError("Vozes Gemini precisam de GEMINI_API_KEY no .env do SupoClip")
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": name}}}},
        }
        data, last_error = None, "nenhum modelo respondeu"
        for model in GEMINI_TTS_MODELS:
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key}, json=body, timeout=180,
            )
            if response.status_code != 200:
                last_error = f"{model}: HTTP {response.status_code}"
                continue
            try:
                data = base64.b64decode(response.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
                break
            except (KeyError, IndexError, ValueError):
                last_error = f"{model}: sem áudio"
        if data is None:
            raise RuntimeError(f"Gemini TTS falhou ({last_error})")
        raw.write_bytes(data)
        tempo = f",atempo={1 + speed / 100:.3f}" if speed else ""
        if data.startswith(b"RIFF"):
            _ffmpeg("-i", str(raw), "-af", f"aresample=24000{tempo}", "-ac", "1", str(out_path))
        else:
            _ffmpeg("-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw), "-af", f"anull{tempo}", str(out_path))
    elif kind == "vs":
        response = httpx.post(
            f"{get_config().voice_clone_url}/v1/audio/speech",
            json={"model": "tts-1", "voice": name, "input": text, "response_format": "wav", **(voice_settings or {})},
            timeout=1800,
        )
        if response.status_code != 200 or len(response.content) < 1000:
            raise RuntimeError(f"Sua voz (VoiceStudio) falhou: HTTP {response.status_code}")
        raw.write_bytes(response.content)
        tempo = f"atempo={1 + speed / 100:.3f}" if speed else "anull"
        # Cloned voices copy the reference recording's room noise; between
        # sentences it pumps in and out. Clean it before the video is built.
        _ffmpeg("-i", str(raw), "-af", f"{tempo},{CLONE_VOICE_CLEANUP}", "-ac", "1", "-ar", "24000", str(out_path))
    else:
        raise ValueError("Voz desconhecida")
    raw.unlink(missing_ok=True)
    return out_path


def _ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_captions(
    audio_path: Path,
    script: str,
    size: tuple[int, int],
    out_path: Path,
    words_per_line: int = 3,
    pronunciation: list[tuple[str, str]] | None = None,
    words: list[dict] | None = None,
) -> Path:
    """Big centered captions, current word in yellow, timed by faster-whisper."""
    if words is None:
        words = timed_script_words(audio_path, script, pronunciation)
    width, height = size
    font_size = int(width * 0.085)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Main,Montserrat,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{max(4, font_size // 12)},3,5,60,60,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    y = int(height * 0.62)
    for start in range(0, len(words), words_per_line):
        group = words[start:start + words_per_line]
        for index, word in enumerate(group):
            following = start + index + 1
            end = words[following]["start"] if following < len(words) else word["end"] + 0.25
            if index + 1 == len(group) and following < len(words):
                # Hold the last word until the next line starts, never past it.
                end = min(max(word["end"], words[following]["start"]), word["end"] + 0.6)
            text = " ".join(
                ("{\\c&H00E5FF&}" + w["word"].strip().upper() + "{\\c&HFFFFFF&}") if i == index else w["word"].strip().upper()
                for i, w in enumerate(group)
            )
            lines.append(f"Dialogue: 0,{_ass_time(word['start'])},{_ass_time(end)},Main,,0,0,0,,{{\\pos({width // 2},{y})}}{text}")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


TRANSITIONS = {"none", "fade", "fadeblack", "dissolve", "slideleft", "slideup", "zoomin", "circleopen", "wipeleft"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".quicktime"}


def render_video(
    images: list[Path],
    audio_path: Path,
    captions_path: Path | None,
    fmt: str,
    out_path: Path,
    music: Path | None = None,
    music_volume: float = 0.12,
    transition: str = "fade",
    effect: str = "zoom",
    banner: str | None = None,
    hook: str | None = None,
    look: str | None = None,
    starts: dict[str, float] | None = None,
    ends: dict[str, float] | None = None,
    outro: dict | None = None,
    scene_seconds: list[float] | None = None,
) -> Path:
    """Photos (slow zoom/pan) or video clips as background, joined by transitions,
    narration on top, captions burned in. Blocking.

    ``outro`` = {"style": "custom", "path": Path} appends the user's own outro video.

    Videos are first cut to the window the user chose (``starts``/``ends``,
    seconds). With ``scene_seconds`` (one paragraph per scene) each scene lasts
    while its paragraph is narrated; otherwise each piece gets screen time in
    proportion to its length, photos getting the average length.
    """
    width, height = FORMATS[fmt]
    duration = _probe_duration(audio_path) + 0.6
    count = len(images)
    fade = 0.7 if transition in TRANSITIONS - {"none"} and count > 1 else 0.0
    images = [_cut_window(m, (starts or {}).get(m.name, 0.0), (ends or {}).get(m.name)) for m in images]
    lengths = [_probe_duration(m) if m.suffix.lower() in VIDEO_SUFFIXES else None for m in images]
    known = [x for x in lengths if x]
    average = sum(known) / len(known) if known else 1.0
    weights = [x or average for x in lengths]
    # Transitions overlap neighbours, so the pieces add up to a little more.
    total = duration + fade * (count - 1)
    if scene_seconds and len(scene_seconds) == count:
        # Each scene overlaps the next by the transition, except the last one.
        scale = duration / sum(scene_seconds)
        durations = [s * scale + (fade if i < count - 1 else 0.0) for i, s in enumerate(scene_seconds)]
    else:
        durations = [total * w / sum(weights) for w in weights]
    # No piece may be shorter than its transition (it would be cut off).
    durations = [max(d, fade + 0.3) for d in durations]
    fps = 30
    cover = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"
    inputs, parts = [], []
    for index, media in enumerate(images):
        per_item = durations[index]
        frames = max(1, int(per_item * fps))
        if media.suffix.lower() in VIDEO_SUFFIXES:
            # A clip shorter than its time on screen holds its last frame
            # (the giant stays down) instead of starting over.
            inputs += ["-i", str(media)]
            # Slow the clip down (up to 2x) to fill its time before holding the last frame.
            slow = min(2.0, max(1.0, per_item / max(lengths[index] or per_item, 0.1)))
            parts.append(
                f"[{index}:v]{cover},setpts={slow:.3f}*PTS,fps={fps},tpad=stop_mode=clone:stop_duration={per_item:.3f},"
                f"trim=duration={per_item:.3f},setpts=PTS-STARTPTS,fps={fps},settb=1/{fps},setsar=1,format=yuv420p[v{index}]"
            )
            continue
        inputs += ["-loop", "1", "-t", f"{per_item:.3f}", "-i", str(media)]
        if effect == "static":
            motion = f"{cover},fps={fps}"
        else:
            if effect == "pan":
                zoom, x = "1.15", f"(iw-iw/zoom)*on/{frames}" if index % 2 == 0 else f"(iw-iw/zoom)*(1-on/{frames})"
            else:
                zoom = "min(zoom+0.0007,1.18)" if index % 2 == 0 else "if(eq(on,0),1.18,max(zoom-0.0007,1))"
                x = "iw/2-(iw/zoom/2)"
            motion = (
                f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,crop={width * 2}:{height * 2},"
                f"zoompan=z='{zoom}':x='{x}':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}"
            )
        parts.append(f"[{index}:v]{motion},trim=duration={per_item:.3f},setpts=PTS-STARTPTS,fps={fps},settb=1/{fps},setsar=1,format=yuv420p[v{index}]")
    if fade:
        last, offset = "v0", 0.0
        for index in range(1, count):
            offset += durations[index - 1] - fade
            parts.append(f"[{last}][v{index}]xfade=transition={transition}:duration={fade}:offset={offset:.3f}[x{index}]")
            last = f"x{index}"
        graph = ";".join(parts) + f";[{last}]format=yuv420p"
    else:
        graph = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(count)) + f"concat=n={count}:v=1:a=0,format=yuv420p"
    if banner:
        # Call-to-action strip over the top of the frame for the last seconds.
        banner_file = out_path.with_name("banner.txt")
        banner_file.write_text(banner, encoding="utf-8")
        textfile = str(banner_file).replace("\\", "/").replace(":", "\\:")
        font = str(FONT_DIR / "Poppins-ExtraBold.ttf").replace("\\", "/").replace(":", "\\:")
        show = f"gte(t,{max(0.0, duration - 4.5):.2f})"
        graph += (
            f",drawtext=fontfile='{font}':textfile='{textfile}':fontsize={int(width * 0.05)}:fontcolor=black"
            f":box=1:boxcolor=0xFFE500@0.95:boxborderw={int(width * 0.025)}:x=(w-text_w)/2:y=h*0.12:enable='{show}'"
        )
    if look:
        # Same colour looks as the clip tools ("Cor do vídeo"), on the whole background.
        from .api.routes.cover import COLOR_PRESETS

        if look in COLOR_PRESETS:
            graph += "," + COLOR_PRESETS[look][1]
    if hook:
        # Big hook title over the top third for the first seconds (stops the scroll).
        import textwrap

        font = str(FONT_DIR / "Anton-Regular.ttf").replace("\\", "/").replace(":", "\\:")
        lines = textwrap.wrap(hook.upper(), width=14 if fmt == "vertical" else 24, break_long_words=False)[:3]
        size = int(width * (0.11 if fmt == "vertical" else 0.06))
        top = int(height * 0.14)
        for index, line in enumerate(lines):
            line_file = out_path.with_name(f"hook_{index}.txt")
            line_file.write_text(line, encoding="utf-8")
            textfile = str(line_file).replace("\\", "/").replace(":", "\\:")
            color = "0xFFE500" if index == len(lines) - 1 else "white"
            graph += (
                f",drawtext=fontfile='{font}':textfile='{textfile}':fontsize={size}:fontcolor={color}"
                f":borderw={max(6, size // 12)}:bordercolor=black:x=(w-text_w)/2:y={top + index * int(size * 1.15)}"
                f":enable='lt(t,{HOOK_SECONDS})'"
            )
    if captions_path:
        ass = str(captions_path).replace("\\", "/").replace(":", "\\:")
        fonts = str(FONT_DIR).replace("\\", "/").replace(":", "\\:")
        graph += f",subtitles='{ass}':fontsdir='{fonts}'"
    graph += "[vout]"
    audio_index = len(images)
    inputs += ["-i", str(audio_path)]
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        graph += (
            f";[{audio_index + 1}:a]volume={music_volume:.2f}[m];"
            f"[{audio_index}:a]apad=whole_dur={duration:.3f}[n];"
            f"[n][m]amix=inputs=2:duration=first:normalize=0[aout]"
        )
    else:
        graph += f";[{audio_index}:a]apad=whole_dur={duration:.3f}[aout]"
    _ffmpeg(
        *inputs, "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
        "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path),
    )
    if outro and outro.get("style") == "custom" and outro.get("path"):
        _append_outro(out_path, Path(outro["path"]), width, height, Path(outro["voice"]) if outro.get("voice") else None)
    return out_path


def split_for_speech(script: str, max_chars: int = 280) -> list[str]:
    """Sentence groups of at most ~max_chars, so long scripts are spoken piece by piece."""
    import re

    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", " ".join(script.split())) if s.strip()]
    chunks, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks or [script.strip()]


def join_audio(parts: list[Path], out_path: Path, pause: float = 0.25) -> Path:
    """Concatenate spoken pieces with a short natural pause between them."""
    if len(parts) == 1:
        parts[0].replace(out_path)
        return out_path
    inputs, labels = [], []
    for index, part in enumerate(parts):
        inputs += ["-i", str(part)]
        labels.append(f"[{index}:a]aresample=24000,aformat=channel_layouts=mono,apad=pad_dur={pause}[a{index}]")
    graph = ";".join(labels) + ";" + "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]"
    _ffmpeg(*inputs, "-filter_complex", graph, "-map", "[out]", str(out_path))
    for part in parts:
        part.unlink(missing_ok=True)
    return out_path


pronunciation_system_prompt = """Você revisa roteiros que serão lidos por uma voz sintética em português do Brasil.
Aponte só as palavras que uma voz artificial costuma pronunciar errado: nomes próprios (pessoas, lugares),
nomes e palavras estrangeiras, siglas, abreviações e grafias incomuns.
Para cada uma, escreva como ela deve ser escrita para soar certo em português do Brasil
(ex.: Cohen -> Côen; STF -> ésse tê éfe; Getúlio -> Jetúlio; YouTube -> Iutúbi).
Não inclua palavras comuns do português que qualquer leitor fala certo. Não repita palavras.
NUNCA inclua números, anos, datas ou valores: a voz já lê números por extenso em português do Brasil
(1961 vira "mil novecentos e sessenta e um"); reescrever números só piora."""


class PronunciationHint(BaseModel):
    word: str = Field(description="A palavra exatamente como está no roteiro")
    spoken: str = Field(description="Como escrever para a voz falar certo")
    reason: str = Field(description="Motivo curto, ex.: nome estrangeiro, sigla")


class PronunciationReview(BaseModel):
    hints: list[PronunciationHint]


async def review_pronunciation(script: str, known: list[str]) -> list[dict]:
    """Ask the LLM which words a TTS voice is likely to mispronounce."""
    from .ai import _build_transcript_model, _get_missing_llm_key_error

    config = get_config()
    if error := _get_missing_llm_key_error(config.studio_llm, config):
        raise RuntimeError(error)
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=PronunciationReview, system_prompt=pronunciation_system_prompt)
    prompt = (f"Já corrigidas (ignore): {', '.join(known)}\n\n" if known else "") + f"Roteiro:\n{script.strip()[:8000]}"
    result = await agent.run(prompt)
    known_lower = {k.lower() for k in known}
    seen, hints = set(), []
    for hint in result.output.hints:
        word = hint.word.strip()
        if any(ch.isdigit() for ch in word):
            continue  # the voice service reads numbers itself
        if word and word.lower() not in known_lower and word.lower() not in seen and word.lower() in script.lower():
            seen.add(word.lower())
            hints.append({"word": word, "spoken": hint.spoken.strip(), "reason": hint.reason.strip()})
    return hints[:40]


post_text_system_prompt = """Você é especialista em YouTube Shorts e vídeos curtos no Brasil.
A partir do roteiro narrado, escreva o texto para publicar o vídeo, em português do Brasil:
- 3 opções de título com no máximo 70 caracteres, curiosos e fiéis ao conteúdo (sem mentir nem exagerar);
- uma descrição de 2 a 4 frases curtas que resume o vídeo e convida a se inscrever;
- de 5 a 8 hashtags relevantes, sem acentos e sem espaços, incluindo #shorts.
Não invente fatos que não estejam no roteiro."""


class PostText(BaseModel):
    titles: list[str] = Field(description="3 opções de título, até 70 caracteres")
    description: str = Field(description="Descrição de 2 a 4 frases")
    hashtags: list[str] = Field(description="5 a 8 hashtags começando com #")


async def write_post_text(script: str) -> dict:
    """Title options, description and hashtags for publishing a narrated video."""
    from .ai import _build_transcript_model, _get_missing_llm_key_error

    config = get_config()
    if error := _get_missing_llm_key_error(config.studio_llm, config):
        raise RuntimeError(error)
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=PostText, system_prompt=post_text_system_prompt)
    out = (await agent.run(f"Roteiro:\n{script.strip()[:8000]}")).output
    tags = [t if t.startswith("#") else f"#{t}" for t in (t.strip().replace(" ", "") for t in out.hashtags) if t]
    return {"titles": [t.strip()[:100] for t in out.titles if t.strip()][:3], "description": out.description.strip(), "hashtags": tags[:8]}


def _norm_word(word: str) -> str:
    import re
    import unicodedata

    plain = unicodedata.normalize("NFKD", word.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in plain if not unicodedata.combining(c)))


def align_script_words(script: str, heard: list[dict], pronunciation: list[tuple[str, str]]) -> list[dict]:
    """Give every script word a time from the transcript.

    Matching runs on the spoken text (script with respellings applied), so
    "Jetúlio" in the audio lines up with "Getúlio" in the script. Words the
    transcript heard differently share the time span of what was heard there;
    words it skipped are placed between their neighbours.
    """
    import difflib

    written = script.split()
    spoken = [apply_pronunciation(w, pronunciation) for w in written]
    a = [_norm_word(w) for w in spoken]
    b = [_norm_word(w["word"]) for w in heard]
    times: list[tuple[float, float] | None] = [None] * len(written)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
        elif op == "replace":
            start, end = heard[j1]["start"], heard[j2 - 1]["end"]
            step = (end - start) / (i2 - i1)
            for k in range(i2 - i1):
                times[i1 + k] = (start + k * step, start + (k + 1) * step)
    # Fill skipped words between known neighbours.
    for index, value in enumerate(times):
        if value is None:
            prev_end = next((times[k][1] for k in range(index - 1, -1, -1) if times[k]), 0.0)
            next_start = next((times[k][0] for k in range(index + 1, len(times)) if times[k]), prev_end + 0.3)
            times[index] = (prev_end, max(prev_end + 0.05, min(next_start, prev_end + 0.3)))
    return [{"word": w, "start": s, "end": e} for w, (s, e) in zip(written, times) if _norm_word(w)]


spelling_system_prompt = """Você é revisor de textos em português do Brasil.
Corrija apenas ortografia, acentuação, digitação e pontuação do roteiro.
Se o texto estiver em português de Portugal ("sabias", "teu", "obrigar-te", "conta-me"), adapte para o português do Brasil
("você sabia", "seu", "te obrigar", "me conta"), mantendo o mesmo sentido.
Não mude o estilo, a ordem, o sentido nem o tamanho do texto, e não acrescente nada.
Responda somente com o texto corrigido."""


async def fix_spelling(script: str) -> str:
    from .ai import _build_transcript_model, _get_missing_llm_key_error

    config = get_config()
    if error := _get_missing_llm_key_error(config.studio_llm, config):
        raise RuntimeError(error)
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=str, system_prompt=spelling_system_prompt)
    return (await agent.run(script.strip()[:12000])).output.strip()


ideas_system_prompt = """Você cria pautas para canais de vídeos curtos no Brasil.
Dado o assunto do canal, sugira temas de vídeo variados, específicos e com potencial de viralizar
(curiosidade, emoção, utilidade ou polêmica saudável). Evite temas genéricos e repetidos.
Para cada tema, escreva também o gancho da primeira frase do vídeo. Em português do Brasil."""


class Idea(BaseModel):
    theme: str = Field(description="Tema específico do vídeo, até 80 caracteres")
    hook: str = Field(description="Primeira frase do vídeo, que prende a atenção")


class IdeaList(BaseModel):
    ideas: list[Idea]


async def suggest_ideas(subject: str, count: int = 8, avoid: list[str] | None = None) -> list[dict]:
    from .ai import _build_transcript_model, _get_missing_llm_key_error

    config = get_config()
    if error := _get_missing_llm_key_error(config.studio_llm, config):
        raise RuntimeError(error)
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=IdeaList, system_prompt=ideas_system_prompt)
    prompt = f"Assunto do canal: {subject.strip()[:200]}\nSugira {count} temas diferentes."
    if avoid:
        prompt += "\nNão repita estes temas: " + "; ".join(a[:80] for a in avoid[:30])
    ideas = (await agent.run(prompt)).output.ideas
    return [{"theme": i.theme.strip(), "hook": i.hook.strip()} for i in ideas if i.theme.strip()][:count]


fact_check_system_prompt = """Você é checador de fatos de um canal brasileiro de vídeos curtos (leis, direitos, história, fé, curiosidades).
Separe o roteiro nas afirmações de fato e avalie cada uma para o público do BRASIL:
- "ok": correta como está;
- "impreciso": tem base, mas simplifica de um jeito que pode enganar;
- "falso": errada;
- "verificar": você não tem certeza.
Para cada uma, explique em uma frase, sugira uma redação correta quando não for "ok"
e indique a fonte que a sustenta (ex.: CDC art. 39, CLT art. 462, Lei 13.455/2017, Bíblia Isaías 40:31, livro ou órgão oficial).
Nunca invente número de lei ou artigo: se não souber a fonte exata, use "verificar".
Respeite o estilo do autor: narração poética, em primeira pessoa (inclusive como a voz de Deus), frases curtas e
omissões de detalhes são escolhas artísticas, NÃO erros. Uma frase que só deixa de mencionar algo (ex.: "O gigante caiu."
sem citar a funda) é "ok". Marque "impreciso" ou "falso" só quando a frase afirmar algo que contradiz a fonte.
Quando sugerir correção, mude o MÍNIMO possível e mantenha as palavras do autor; nunca acrescente cenas ou detalhes.
OBRIGATÓRIO: em "claim", copie o trecho do roteiro LETRA POR LETRA (mesma pontuação, sem resumir).
OBRIGATÓRIO: se o veredito for "impreciso" ou "falso", "correction" NUNCA pode ficar vazio: escreva o trecho
inteiro já corrigido, pronto para substituir o original no roteiro.
Avise também se o texto estiver em português de Portugal (ex.: "sabias", "teu", "obrigar-te")."""


class FactCheck(BaseModel):
    claim: str = Field(description="A afirmação, como está no roteiro")
    verdict: str = Field(description="ok, impreciso, falso ou verificar")
    explanation: str = Field(description="Uma frase explicando")
    correction: str = Field(description="Redação sugerida; vazio se estiver ok")
    source: str = Field(description="Lei, artigo, livro ou órgão que sustenta; vazio se não souber")


class FactReport(BaseModel):
    portugal_portuguese: bool = Field(description="Texto escrito em português de Portugal")
    checks: list[FactCheck]


async def fact_check(script: str) -> dict:
    from .ai import _build_transcript_model, _get_missing_llm_key_error

    config = get_config()
    if error := _get_missing_llm_key_error(config.studio_llm, config):
        raise RuntimeError(error)
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=FactReport, system_prompt=fact_check_system_prompt)
    report = (await agent.run(f"Roteiro:\n{script.strip()[:8000]}")).output
    verdicts = {"ok", "impreciso", "falso", "verificar"}
    return {
        "portugal_portuguese": report.portugal_portuguese,
        "checks": [
            {
                "claim": c.claim.strip(),
                "verdict": c.verdict.strip().lower() if c.verdict.strip().lower() in verdicts else "verificar",
                "explanation": c.explanation.strip(),
                "correction": c.correction.strip(),
                "source": c.source.strip(),
            }
            for c in report.checks if c.claim.strip()
        ][:20],
    }


# ---------------------------------------------------------------------------
# Automatic backgrounds (one image per few seconds) and on-screen hook.

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
WIKIMEDIA_UA = "SupoClipLocal/1.0 (https://github.com/FujiwaraChoki/supoclip; self-hosted video tool) python-httpx"
FREE_LICENSES = ("cc by", "cc0", "public domain", "pd", "cc-by")
SECONDS_PER_IMAGE = 4.0
HOOK_SECONDS = 2.5

backgrounds_system_prompt = """You pick stock photos for a narrated short video.
For each numbered part of the script, write ONE short English image search query (2-4 words) describing a concrete,
photographable scene or object that illustrates that part (e.g. "old radio", "courtroom gavel", "eagle flying").
Avoid abstract words, text, logos and specific living people. Never ask for weapons, soldiers, war, blood,
violence, nudity, flags or political/military symbols: platforms restrict those; prefer calm everyday objects,
places and nature. Keep the order and the same number of parts."""

hook_system_prompt = """Você escreve o texto de gancho que aparece GRANDE na tela nos 2 primeiros segundos de um vídeo curto.
Máximo de 6 palavras, em português do Brasil, que despertem curiosidade e sejam fiéis ao roteiro.
Sem aspas, sem emoji, sem hashtags. Responda só com o texto."""


class BackgroundQueries(BaseModel):
    queries: list[str]


def _script_parts(script: str, count: int) -> list[str]:
    words = script.split()
    size = max(1, -(-len(words) // count))
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)][:count]


async def plan_background_queries(script: str, count: int) -> list[str]:
    from .ai import _build_transcript_model

    config = get_config()
    parts = _script_parts(script, count)
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=BackgroundQueries, system_prompt=backgrounds_system_prompt)
    numbered = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(parts))
    queries = [q.strip() for q in (await agent.run(numbered)).output.queries if q.strip()]
    while len(queries) < len(parts):
        queries.append(queries[-1] if queries else "nature landscape")
    return queries[: len(parts)]


async def write_hook(script: str) -> str:
    from .ai import _build_transcript_model

    config = get_config()
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=str, system_prompt=hook_system_prompt)
    return (await agent.run(script.strip()[:3000])).output.strip().strip('"“”')[:60]


def _strip_html(value: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", value or "").strip()


def _search_wikimedia(query: str, vertical: bool) -> dict | None:
    response = httpx.get(
        WIKIMEDIA_API,
        params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f"filetype:bitmap {query}", "gsrlimit": 12,
            "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1080,
        },
        headers={"User-Agent": WIKIMEDIA_UA},
        timeout=20,
    )
    response.raise_for_status()
    pages = sorted((response.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    best, best_score = None, -1.0
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = (meta.get("LicenseShortName", {}).get("value") or "").strip()
        if not license_name.lower().startswith(FREE_LICENSES) or not info.get("thumburl"):
            continue
        width, height = info.get("thumbwidth") or 1, info.get("thumbheight") or 1
        if min(width, height) < 500:
            continue
        ratio = height / width
        score = (ratio if vertical else 1 / ratio) - page.get("index", 0) * 0.02
        if score > best_score:
            best_score = score
            best = {
                "url": info["thumburl"],
                "page": info.get("descriptionurl", ""),
                "title": page.get("title", "").removeprefix("File:").rsplit(".", 1)[0][:60],
                "license": license_name,
                "author": _strip_html(meta.get("Artist", {}).get("value", ""))[:80],
                "source": "Wikimedia Commons",
            }
    return best


def _search_pexels(query: str, vertical: bool) -> dict | None:
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return None
    response = httpx.get(
        "https://api.pexels.com/v1/search",
        params={"query": query, "per_page": 5, "orientation": "portrait" if vertical else "landscape"},
        headers={"Authorization": key},
        timeout=20,
    )
    response.raise_for_status()
    photos = response.json().get("photos") or []
    if not photos:
        return None
    photo = photos[0]
    return {
        "url": photo["src"]["large2x"], "page": photo.get("url", ""), "title": query,
        "license": "Pexels License", "author": photo.get("photographer", ""), "source": "Pexels",
    }


def fetch_backgrounds(queries: list[str], directory: Path, vertical: bool) -> tuple[list[Path], list[dict]]:
    """Download one free image per query (Pexels when configured, else Wikimedia Commons). Blocking."""
    paths, credits = [], []
    for index, query in enumerate(queries):
        found = None
        for search in (_search_pexels, _search_wikimedia):
            try:
                found = search(query, vertical)
            except Exception as exc:
                logger.info("Background search %s failed for %r: %s", search.__name__, query, exc)
            if found:
                break
        if not found:
            continue
        try:
            data = httpx.get(found["url"], headers={"User-Agent": WIKIMEDIA_UA}, timeout=60, follow_redirects=True).content
        except Exception as exc:
            logger.info("Background download failed for %r: %s", query, exc)
            continue
        path = directory / f"auto_{index:02d}.jpg"
        path.write_bytes(data)
        paths.append(path)
        credits.append(found)
    return paths, credits


def credits_text(credits: list[dict]) -> str:
    lines = []
    for c in credits:
        author = f" por {c['author']}" if c.get("author") else ""
        lines.append(f"{c['title']}{author} ({c['license']}, {c['source']})")
    return "Imagens: " + "; ".join(dict.fromkeys(lines))


analysis_system_prompt = """Você é um analista sênior de vídeos curtos (YouTube Shorts, TikTok, Reels) no Brasil.
Com os dados públicos do vídeo, diga com franqueza por que ele está (ou não) crescendo e o que mudar no PRÓXIMO vídeo.
Fatos atuais: YouTube Shorts aceitam até 3 minutos (desde 2024); 25 a 45 s costuma reter melhor, mas passar de 60 s não tira o vídeo do feed.
A transcrição vem da legenda automática e pode ter erros ou repetições da própria legenda: não conclua que o roteiro é repetitivo por isso.
Considere: gancho dos 2 primeiros segundos (pela fala inicial), título, duração, ritmo,
chamada para comentar, constância, comparação com a média do canal e engajamento (curtidas e comentários por visualização).
Seja concreto: em vez de "melhore o gancho", escreva o novo gancho. Não invente números que não estão nos dados;
retenção e de onde veio o público só existem no YouTube Studio, então indique onde olhar."""


class VideoAnalysis(BaseModel):
    score: int = Field(description="Nota de 0 a 10 do potencial do vídeo")
    verdict: str = Field(description="Diagnóstico em 1 ou 2 frases")
    strengths: list[str] = Field(description="O que funcionou (até 3)")
    problems: list[str] = Field(description="O que provavelmente travou o alcance (até 4)")
    next_steps: list[str] = Field(description="Ações concretas para o próximo vídeo (3 a 5)")
    new_titles: list[str] = Field(description="3 títulos melhores")
    new_hook: str = Field(description="Nova primeira frase, que prende nos 2 primeiros segundos")
    studio_tip: str = Field(description="O que conferir no YouTube Studio (retenção, origem do tráfego)")


async def analyze_posted_video(facts: dict) -> dict:
    import json as _json

    from .ai import _build_transcript_model

    config = get_config()
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=VideoAnalysis, system_prompt=analysis_system_prompt)
    data = {k: v for k, v in facts.items() if k not in ("thumbnail", "url", "id")}
    return (await agent.run("Dados do vídeo:\n" + _json.dumps(data, ensure_ascii=False))).output.model_dump()


# ---------------------------------------------------------------------------
# Background picker: suggest images per part of the script so the user chooses
# what gets published (free photos or AI-generated cinematic images).

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

ai_prompts_system_prompt = """You are the art director of a narrated short video. For each numbered part of the script,
write ONE English text-to-image prompt for a striking, cinematic, photorealistic scene that illustrates that part.
All prompts share one visual style: {style}. Add lighting, mood and camera details (e.g. "low angle, shallow depth of field").
No text, captions, logos or real living people's faces. Avoid gore, weapons pointed at people and nudity.
Keep the order and the same number of parts."""

STYLES = {
    "cinema": "cinematic film still, dramatic chiaroscuro lighting, rich contrast, subtle film grain",
    "historia": "vintage documentary photo look, sepia and muted tones, soft film grain, period-accurate details",
    "fe": "warm golden-hour light, soft glow, serene and hopeful, gentle haze, majestic nature",
    "noticia": "clean modern editorial photography, natural light, sharp and realistic",
    "suspense": "dark moody thriller look, cold blue shadows, fog, high contrast",
}


async def plan_ai_prompts(script: str, count: int, style: str) -> list[str]:
    from .ai import _build_transcript_model

    config = get_config()
    parts = _script_parts(script, count)
    prompt = ai_prompts_system_prompt.format(style=STYLES.get(style, STYLES["cinema"]))
    agent = Agent(model=_build_transcript_model(config, config.studio_llm), output_type=BackgroundQueries, system_prompt=prompt)
    numbered = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(parts))
    prompts = [q.strip() for q in (await agent.run(numbered)).output.queries if q.strip()]
    while len(prompts) < len(parts):
        prompts.append(prompts[-1] if prompts else "cinematic landscape at dusk")
    return prompts[: len(parts)]


_AI_IMAGE_LOCK = threading.Lock()
_ai_image_last = 0.0
AI_IMAGE_FREE_INTERVAL = 46.0  # anonymous Pollinations: 1 image / 45 s per IP


def generate_ai_image(prompt: str, out_path: Path, vertical: bool, seed: int) -> dict:
    """Text-to-image (Pollinations). Without POLLINATIONS_TOKEN the free tier
    allows one image every 45 s, so calls are spaced and retried. Blocking."""
    import re
    import time

    global _ai_image_last
    token = os.getenv("POLLINATIONS_TOKEN")
    width, height = (768, 1344) if vertical else (1344, 768)
    params = {"width": width, "height": height, "seed": seed, "nologo": "true"}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with _AI_IMAGE_LOCK:
        for attempt in range(4):
            if not token:
                time.sleep(max(0.0, AI_IMAGE_FREE_INTERVAL - (time.time() - _ai_image_last)))
            response = httpx.get(
                POLLINATIONS_URL + urllib.parse.quote(prompt[:900]),
                params=params, headers=headers, timeout=180, follow_redirects=True,
            )
            _ai_image_last = time.time()
            if response.status_code == 402 and attempt < 3:
                wait = re.search(r"Retry after (\d+)s", response.text)
                time.sleep(int(wait.group(1)) + 1 if wait else 15)
                continue
            break
    if response.status_code != 200 or not response.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(f"Gerador de imagens respondeu {response.status_code}")
    out_path.write_bytes(response.content)
    return {"title": "Imagem gerada por IA", "license": "gerada por IA", "author": "", "source": "Pollinations", "ai": True}


def search_free_options(query: str, vertical: bool, limit: int = 3) -> list[dict]:
    """Up to ``limit`` free images for a query (Pexels first when configured, then Wikimedia)."""
    options = []
    try:
        if found := _search_pexels(query, vertical):
            options.append(found)
    except Exception:
        pass
    try:
        response = httpx.get(
            WIKIMEDIA_API,
            params={
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                "gsrsearch": f"filetype:bitmap {query}", "gsrlimit": 15,
                "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1080,
            },
            headers={"User-Agent": WIKIMEDIA_UA}, timeout=20,
        )
        pages = sorted((response.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            license_name = (meta.get("LicenseShortName", {}).get("value") or "").strip()
            if not license_name.lower().startswith(FREE_LICENSES) or not info.get("thumburl"):
                continue
            if min(info.get("thumbwidth") or 0, info.get("thumbheight") or 0) < 500:
                continue
            options.append({
                "url": info["thumburl"], "page": info.get("descriptionurl", ""),
                "title": page.get("title", "").removeprefix("File:").rsplit(".", 1)[0][:60],
                "license": license_name, "author": _strip_html(meta.get("Artist", {}).get("value", ""))[:80],
                "source": "Wikimedia Commons",
            })
    except Exception as exc:
        logger.info("Wikimedia options failed for %r: %s", query, exc)
    return options[:limit]


def download_image(url: str, out_path: Path) -> Path:
    data = httpx.get(url, headers={"User-Agent": WIKIMEDIA_UA}, timeout=60, follow_redirects=True).content
    out_path.write_bytes(data)
    return out_path


def _cut_window(media: Path, start: float, end: float | None) -> Path:
    """The part of a video the user kept (start/end seconds) as its own file. Blocking."""
    if media.suffix.lower() not in VIDEO_SUFFIXES or (start <= 0 and not end):
        return media
    length = _probe_duration(media)
    # A start past the clip's end (typed by hand, or a clip replaced after "Editar")
    # would leave an empty video and fail the render: keep at least half a second.
    start = min(max(0.0, start), max(0.0, length - 0.5))
    if end and end <= start + 0.3:
        end = None
    out = media.with_name(f"{media.stem}_cut.mp4")
    window = ["-ss", f"{max(0.0, start):.2f}"] + (["-to", f"{end:.2f}"] if end and end > start else [])
    _ffmpeg("-i", str(media), *window, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out))
    return out


OUTRO_UNDER_VOICE = 0.15  # outro's own sound under the narrator's line


def _append_outro(main: Path, outro: Path, width: int, height: int, voice: Path | None = None) -> None:
    """Append the user's own outro clip (scaled to the video) after the main video. Blocking.

    With ``voice`` the narrator's line plays over the outro, its own sound kept
    low underneath; the outro holds its last frame if the line is longer.
    """
    has_audio = bool(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(outro)],
        capture_output=True, text=True,
    ).stdout.strip())
    joined = main.with_name("video_outro.mp4")
    clip_seconds = _probe_duration(outro)
    voice_seconds = _probe_duration(voice) + 0.4 if voice else 0.0
    outro_seconds = max(clip_seconds, voice_seconds)
    own_sound = (
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={outro_seconds:.3f}"
        if has_audio else f"anullsrc=r=48000:cl=stereo,atrim=0:{outro_seconds:.3f}"
    )
    if voice:
        outro_audio = (
            f"{own_sound},volume={OUTRO_UNDER_VOICE}[os];"
            f"[2:a]aresample=48000,aformat=channel_layouts=stereo,adelay=300|300,apad=whole_dur={outro_seconds:.3f}[ov_voice];"
            f"[os][ov_voice]amix=inputs=2:duration=first:normalize=0[oa]"
        )
    else:
        outro_audio = f"{own_sound}[oa]"
    cover = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps=30,format=yuv420p"
    hold = f",tpad=stop_mode=clone:stop_duration={outro_seconds:.3f},trim=duration={outro_seconds:.3f}"
    graph = (
        f"[0:v]fps=30,format=yuv420p,setsar=1[mv];[1:v]{cover}{hold}[ov];"
        f"[0:a]aresample=48000,aformat=channel_layouts=stereo[ma];{outro_audio};"
        f"[mv][ma][ov][oa]concat=n=2:v=1:a=1[v][a]"
    )
    _ffmpeg(
        "-i", str(main), "-i", str(outro), *(["-i", str(voice)] if voice else []),
        "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
        "-t", f"{_probe_duration(main) + outro_seconds:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(joined),
    )
    joined.replace(main)


def timed_script_words(audio_path: Path, script: str, pronunciation: list[tuple[str, str]] | None = None) -> list[dict]:
    """The script's own words with start/end seconds taken from the narration. Blocking.

    Captions always show the script's words; the transcript only gives timings.
    Otherwise respellings ("Jetúlio") and mishearings ("farsa" -> "força") end
    up burned into the video.
    """
    from .media.transcription import _transcribe_with_faster_whisper

    result = _transcribe_with_faster_whisper(audio_path, get_config().whisper_model or "small", "pt")
    heard = [w for s in result["segments"] for w in s["words"] if w["word"].strip()]
    return align_script_words(script, heard, pronunciation or []) if script.strip() else heard


def paragraph_scene_seconds(script: str, words: list[dict], total: float, count: int) -> list[float] | None:
    """Screen time per scene when the script has one paragraph per scene.

    Scene k starts when the narrator starts paragraph k, so what is said and
    what is shown stay together. None when paragraphs and scenes do not match.
    """
    import re

    paragraphs = [p for p in re.split(r"\n\s*\n", script.strip()) if p.strip()]
    if count < 2 or len(paragraphs) != count or not words:
        return None
    starts, index = [0.0], 0
    for paragraph in paragraphs[:-1]:
        index += len([w for w in paragraph.split() if _norm_word(w)])
        if index >= len(words):
            return None
        starts.append(float(words[index]["start"]))
    bounds = starts + [total]
    seconds = [bounds[k + 1] - bounds[k] for k in range(count)]
    return seconds if all(s > 1.0 for s in seconds) else None

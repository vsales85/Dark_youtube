"""Worker job for 'Vídeo do zero' renders (status in Redis ``studio:{id}``)."""

import logging
from typing import Any, Dict

from ..studio import (
    FORMATS,
    SECONDS_PER_IMAGE,
    _probe_duration,
    apply_pronunciation,
    build_captions,
    credits_text,
    fetch_backgrounds,
    join_audio,
    parse_pronunciation,
    paragraph_scene_seconds,
    parse_voice_settings,
    plan_background_queries,
    render_video,
    split_for_speech,
    synthesize,
    timed_script_words,
    write_hook,
    write_post_text,
)
from ..utils.async_helpers import run_in_thread

logger = logging.getLogger(__name__)

AI_IMAGE_NOTE = (
    "⚠️ Ao postar, se usar imagens realistas feitas por IA, marque \"conteúdo alterado ou sintético\" "
    "(YouTube) / \"conteúdo gerado por IA\" (TikTok, Instagram)."
)


async def studio_render_job(ctx, job_id: str, options: Dict[str, Any]) -> Dict[str, Any]:
    from ..api.routes.studio import load_status, save_status, studio_dir

    status = await load_status(job_id) or {}
    directory = studio_dir(job_id)
    credits: list[dict] = list(options.get("image_credits") or [])

    async def step(name: str, progress: int) -> None:
        status.update({"status": "rendering", "step": name, "progress": progress})
        await save_status(job_id, status)

    try:
        # Speak sentence groups one by one so the progress moves during the
        # slowest step (a cloned voice takes over a minute per sentence on CPU).
        pronunciation = parse_pronunciation(options.get("pronunciation"))
        cta = (options.get("cta_text") or "").strip()
        # The call to action is spoken (and captioned) at the end of the video.
        full_script = f"{options['script'].rstrip()} {cta}".strip() if cta else options["script"]
        # Long pauses (prayer tone) speak each sentence on its own, then add silence between them.
        pause = float(options.get("pause") or 0.25)
        chunks = split_for_speech(apply_pronunciation(full_script, pronunciation), 1 if pause >= 0.6 else 280)
        parts = []
        for index, chunk in enumerate(chunks):
            await step(f"Gerando a voz do narrador (trecho {index + 1} de {len(chunks)})", 5 + int(50 * index / len(chunks)))
            parts.append(await run_in_thread(
                synthesize, options["voice"], chunk, options.get("speed", 0), directory / f"voice_{index:03d}.wav",
                parse_voice_settings(options.get("voice_settings")),
            ))
        audio = await run_in_thread(join_audio, parts, directory / "voice.wav", pause)

        images = [directory / name for name in options.get("images") or []]
        if options.get("auto_background"):
            await step("Buscando imagens livres para cada trecho", 57)
            count = max(2, min(12, round(_probe_duration(audio) / SECONDS_PER_IMAGE)))
            queries = await plan_background_queries(options["script"], count)
            found, found_credits = await run_in_thread(fetch_backgrounds, queries, directory, options["format"] == "vertical")
            credits += found_credits
            # Your own images first, then the found ones.
            images = images + found
        if not images:
            raise RuntimeError("Nenhuma imagem de fundo: envie uma foto ou ligue o fundo automático.")

        hook = (options.get("hook_text") or "").strip()
        if options.get("hook") and not hook:
            try:
                hook = await write_hook(options["script"])
            except Exception as exc:
                logger.warning("Hook for %s failed: %s", job_id, exc)
        status["hook"] = hook or None

        await step("Sincronizando legendas e cenas", 64)
        words = await run_in_thread(timed_script_words, audio, full_script, pronunciation)
        # One paragraph per scene: each scene lasts while its paragraph is narrated.
        scene_seconds = paragraph_scene_seconds(full_script, words, _probe_duration(audio) + 0.6, len(images))
        captions = None
        if options.get("captions", True):
            captions = await run_in_thread(
                build_captions, audio, full_script, FORMATS[options["format"]], directory / "captions.ass", 3, pronunciation, words
            )
        outro = dict(options.get("outro") or {}) or None
        if outro and outro.get("audio") == "narrator" and outro.get("text"):
            # The narrator says the outro line with the same voice as the video.
            outro["voice"] = str(await run_in_thread(
                synthesize, options["voice"], apply_pronunciation(outro["text"], pronunciation),
                options.get("speed", 0), directory / "outro_voice.wav", parse_voice_settings(options.get("voice_settings")),
            ))
        await step("Montando o vídeo", 75)
        music = directory / options["music"] if options.get("music") else None
        await run_in_thread(
            render_video,
            images,
            audio,
            captions,
            options["format"],
            directory / "video.mp4",
            music,
            options.get("music_volume", 0.12),
            options.get("transition", "fade"),
            options.get("effect", "zoom"),
            cta or None,
            hook or None,
            options.get("look") or None,
            options.get("starts") or None,
            options.get("ends") or None,
            outro,
            scene_seconds,
        )
    except Exception as exc:
        logger.error("Studio render %s failed: %s", job_id, getattr(exc, "stderr", None) or exc, exc_info=True)
        status.update({"status": "error", "error": str(exc)[:300]})
        await save_status(job_id, status)
        return {"status": "error"}

    try:
        # Optional extra: a failed suggestion never fails the finished video.
        status["post"] = await write_post_text(options["script"])
        if options.get("sources"):
            # Citing the law or source in the description backs up the video.
            status["post"]["description"] += "\n\nFontes: " + "; ".join(options["sources"])
        free_credits = [c for c in credits if not c.get("ai")]
        if free_credits:
            # Creative Commons images require attribution.
            status["post"]["description"] += "\n\n" + credits_text(free_credits)
        if options.get("music_credit"):
            # CC BY music (Incompetech) requires this credit line.
            status["post"]["description"] += "\n\n" + options["music_credit"]
        if any(c.get("ai") for c in credits):
            status["post"]["description"] += "\n\nImagens ilustrativas geradas por IA."
        if options.get("cta_link"):
            status["post"]["description"] += f"\n\n🔗 {options['cta_link']}"
        status["post"]["note"] = AI_IMAGE_NOTE
    except Exception as exc:
        logger.warning("Post text for %s failed: %s", job_id, exc)
    status.update({"status": "done", "step": "Pronto", "progress": 100})
    await save_status(job_id, status)
    return {"status": "done"}

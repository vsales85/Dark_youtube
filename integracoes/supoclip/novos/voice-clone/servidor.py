"""Servidor de voz clonada do SupoClip (copiado do VTube) (Chatterbox Multilingual, licença MIT).

Imita a API que o VTube já usa (compatível com OpenAI, porta 3900):
  GET  /v1/audio/voices  -> uma voz por arquivo .wav em /vozes
  POST /v1/audio/speech  -> {"voice": "<nome do wav>", "input": "texto"} -> WAV

Só coloque em /vozes gravações suas ou de quem autorizou.
"""
import io
import json
import os
import re
import threading
from pathlib import Path

import torch
import torchaudio
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

PASTA_VOZES = Path("/vozes")
NOME_VALIDO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

app = FastAPI(title="VTube voz clonada")
_modelo = None
_trava = threading.Lock()


def modelo():
    global _modelo
    if _modelo is None:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        _modelo = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    return _modelo


def vozes():
    return sorted(p for p in PASTA_VOZES.glob("*.wav") if NOME_VALIDO.match(p.stem))


def por_extenso(n: str) -> str:
    from num2words import num2words

    try:
        return num2words(int(n), lang="pt_BR")
    except (ValueError, OverflowError, NotImplementedError):
        return n


def normalizar(texto: str) -> str:
    """Escreve números por extenso: o modelo enrola ao ler algarismos."""
    t = re.sub(r"(\d+):(\d+)(?:-(\d+))?",
               lambda m: f"{por_extenso(m[1])}, versículo {por_extenso(m[2])}"
               + (f" a {por_extenso(m[3])}" if m[3] else ""), texto)
    t = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", t)  # 1.000 -> 1000
    t = re.sub(r"R\$\s*(\d+)(?:,(\d{2}))?",
               lambda m: f"{por_extenso(m[1])} reais" + (f" e {por_extenso(m[2])} centavos" if m[2] and int(m[2]) else ""), t)
    t = re.sub(r"(\d+)\s*%", lambda m: f"{por_extenso(m[1])} por cento", t)
    t = re.sub(r"(\d+),(\d+)", lambda m: f"{por_extenso(m[1])} vírgula {por_extenso(m[2])}", t)
    t = re.sub(r"(\d+)\s*[ºª°]", lambda m: ordinal(m[1], m[0][-1]), t)
    return re.sub(r"\d+", lambda m: por_extenso(m[0]), t)


def ordinal(n: str, marca: str) -> str:
    from num2words import num2words

    try:
        texto = num2words(int(n), lang="pt_BR", to="ordinal")
    except (ValueError, OverflowError, NotImplementedError):
        return n
    return texto[:-1] + "a" if marca == "ª" and texto.endswith("o") else texto


def frases(texto: str, limite: int = 250):
    """Corta em frases curtas: textos longos de uma vez perdem qualidade."""
    partes, atual = [], ""
    for f in re.split(r"(?<=[.!?…;:])\s+", texto.strip()):
        if atual and len(atual) + len(f) + 1 > limite:
            partes.append(atual)
            atual = f
        else:
            atual = f"{atual} {f}".strip()
    if atual:
        partes.append(atual)
    return partes


# Ajustes do Chatterbox. cfg_weight mais baixo deixa o sotaque menos carregado
# e a fala mais calma; exaggeration controla a expressividade.
CFG_PADRAO = float(os.getenv("VOZ_CFG_WEIGHT", "0.5"))
EXAGERO_PADRAO = float(os.getenv("VOZ_EXAGGERATION", "0.5"))
TEMPERATURA_PADRAO = float(os.getenv("VOZ_TEMPERATURE", "0.8"))


class Pedido(BaseModel):
    voice: str
    input: str
    model: str | None = None
    response_format: str | None = "wav"
    cfg_weight: float | None = None
    exaggeration: float | None = None
    temperature: float | None = None


def ficha(p: Path) -> dict:
    """Nome e gênero gravados pelo VTube em <voz>.json (opcional)."""
    try:
        return json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@app.get("/v1/audio/voices")
def listar():
    saida = []
    for p in vozes():
        f = ficha(p)
        saida.append({"voice_id": p.stem, "name": f.get("nome") or p.stem, "gender": f.get("genero", ""), "language": "pt"})
    return {"data": saida}


@app.get("/saude")
def saude():
    return {"ok": True, "vozes": len(vozes()), "modelo_carregado": _modelo is not None}


@app.post("/v1/audio/speech")
def falar(p: Pedido):
    if not NOME_VALIDO.match(p.voice):
        raise HTTPException(400, "nome de voz inválido")
    ref = PASTA_VOZES / f"{p.voice}.wav"
    if not ref.is_file():
        raise HTTPException(404, f"voz '{p.voice}' não encontrada em /vozes")
    texto = normalizar(p.input.strip())
    if not texto:
        raise HTTPException(400, "texto vazio")
    with _trava:
        m = modelo()
        pedacos = []
        pausa = torch.zeros(1, int(m.sr * 0.25))
        for f in frases(texto):
            wav = m.generate(
                f,
                language_id="pt",
                audio_prompt_path=str(ref),
                cfg_weight=min(1.0, max(0.0, CFG_PADRAO if p.cfg_weight is None else p.cfg_weight)),
                exaggeration=min(2.0, max(0.25, EXAGERO_PADRAO if p.exaggeration is None else p.exaggeration)),
                temperature=min(1.5, max(0.1, TEMPERATURA_PADRAO if p.temperature is None else p.temperature)),
            )
            pedacos += [wav.cpu(), pausa]
        audio = torch.cat(pedacos[:-1], dim=1)
    buf = io.BytesIO()
    torchaudio.save(buf, audio, m.sr, format="wav")
    return Response(buf.getvalue(), media_type="audio/wav")

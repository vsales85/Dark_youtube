"""Caminhos do app num lugar so (para rodar em qualquer PC).

Ordem: variavel no .env  ->  D:\\modelos_imagem (PC original, se existir)  ->  pasta "dados" dentro do app.
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))


def _env(nome, padrao=None):
    if os.environ.get(nome):
        return os.environ[nome]
    try:
        with open(os.path.join(BASE, ".env"), encoding="utf-8") as f:
            for linha in f:
                if linha.strip().startswith(nome + "="):
                    return linha.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return padrao


_original = os.path.join("D:" + os.sep, "modelos_imagem")
MODELOS = _env("DARK_MODELOS") or (_original if os.path.isdir(_original) else os.path.join(BASE, "dados"))
MAPAS = os.path.join(MODELOS, "mapas")
HF_HOME = os.path.join(MODELOS, "hf")
ROSTO = os.path.join(MODELOS, "rosto", "yunet.onnx")
SUPOCLIP_ENV = _env("SUPOCLIP_ENV", os.path.join("D:" + os.sep, "SupoClip", ".env"))
DOCKER_EXE = _env("DOCKER_EXE", r"C:\Program Files\Docker\Docker\Docker Desktop.exe")
FONTE_IMPACT = _env("FONTE_IMPACT", r"C:\Windows\Fonts\impact.ttf")
os.makedirs(MODELOS, exist_ok=True)

"""Vozes de IA direto no app (sem depender de outro projeto).

- Gemini TTS (nuvem, chave GEMINI_API_KEY do .env): 30 vozes, ex. "gemini:Charon".
- Voz clonada (Chatterbox, licenca MIT) rodando no PC: servico da pasta voz_clone/ (Docker), ex. "clone:minha-voz".
Os dois devolvem WAV mono. Sem chave/servico, quem chama cai para as vozes gratis do Edge.
"""
import base64, os, struct, sys, time, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

MODELOS_TTS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-2.5-flash-preview-tts"]
VOZES_GEMINI = [("Charon", "Male"), ("Orus", "Male"), ("Fenrir", "Male"), ("Iapetus", "Male"), ("Algieba", "Male"),
                ("Sadaltager", "Male"), ("Puck", "Male"), ("Enceladus", "Male"), ("Umbriel", "Male"), ("Algenib", "Male"),
                ("Rasalgethi", "Male"), ("Alnilam", "Male"), ("Schedar", "Male"), ("Achird", "Male"), ("Zubenelgenubi", "Male"),
                ("Sadachbia", "Male"), ("Kore", "Female"), ("Aoede", "Female"), ("Leda", "Female"), ("Zephyr", "Female"),
                ("Callirrhoe", "Female"), ("Autonoe", "Female"), ("Despina", "Female"), ("Erinome", "Female"), ("Laomedeia", "Female"),
                ("Achernar", "Female"), ("Gacrux", "Female"), ("Pulcherrima", "Female"), ("Vindemiatrix", "Female"), ("Sulafat", "Female")]
VOZ_CLONE_URL = config._env("VOZ_CLONE_URL", "http://localhost:3900")


class CotaEsgotada(RuntimeError):
    pass


def _salvar_pcm(pcm, sr, arquivo):
    with wave.open(arquivo, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)


def gemini(texto, voz, arquivo, estilo=None):
    """Narra com uma voz do Gemini. estilo = instrucao opcional ("calmo e misterioso"). Grava WAV 24 kHz."""
    import requests
    chave = config._env("GEMINI_API_KEY")
    if not chave:
        raise RuntimeError("sem GEMINI_API_KEY no .env")
    # idioma FIXO: sem isso, frases curtas saem com sotaque espanhol (o modelo adivinha o idioma)
    instrucao = estilo or "Narre em portugues do Brasil, com sotaque brasileiro, tom de documentario"
    fala = f"{instrucao}: {texto}"
    corpo = {"contents": [{"parts": [{"text": fala}]}],
             "generationConfig": {"responseModalities": ["AUDIO"],
                                  "speechConfig": {"languageCode": "pt-BR",
                                                   "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz.split(":")[-1]}}}}}
    erro = ""
    for tentativa in range(2):
        for m in MODELOS_TTS:
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                  headers={"x-goog-api-key": chave}, json=corpo, timeout=180)
                if r.status_code == 429:  # cota do dia acabou: nao adianta tentar os outros modelos agora
                    raise CotaEsgotada("cota diaria de voz do Gemini esgotada (volta amanha) - usando a voz reserva")
                if r.status_code != 200:
                    erro = f"{m}: HTTP {r.status_code}"; continue
                parte = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                sr = 24000
                tipo = parte.get("mimeType", "")
                if "rate=" in tipo:
                    sr = int(tipo.split("rate=")[1].split(";")[0])
                _salvar_pcm(base64.b64decode(parte["data"]), sr, arquivo)
                try:
                    import custos  # registra o uso (estimativa)
                    custos.registrar(m, None, etapa="voz")
                except Exception:
                    pass
                return arquivo
            except CotaEsgotada:
                raise
            except Exception as e:
                erro = f"{m}: {str(e)[:80]}"
        time.sleep(4)
    raise RuntimeError(f"Gemini TTS falhou ({erro})")


def clonada(texto, voz_id, arquivo, expressao=None):
    """Narra com a voz clonada (servico local voz_clone em Docker)."""
    import requests
    r = requests.post(f"{VOZ_CLONE_URL}/v1/audio/speech", timeout=1800,
                      json={"voice": voz_id.split(":")[-1], "input": texto, **({"exaggeration": expressao} if expressao else {})})
    r.raise_for_status()
    open(arquivo, "wb").write(r.content)
    return arquivo


def vozes_clonadas():
    try:
        import requests
        return requests.get(f"{VOZ_CLONE_URL}/v1/audio/voices", timeout=3).json().get("data", [])
    except Exception:
        return []


def falar(texto, voz, arquivo):
    """Ponto unico: 'gemini:Nome' ou 'clone:id'/'vs:id'. Devolve o arquivo WAV (pode ser float; converta com ffmpeg)."""
    if voz.startswith("gemini:"):
        return gemini(texto, voz, arquivo)
    if voz.startswith(("clone:", "vs:")):
        return clonada(texto, voz, arquivo)
    raise ValueError("voz desconhecida: " + voz)

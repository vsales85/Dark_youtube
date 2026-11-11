"""Ponte Dark Studio -> SupoClip (servidor local em http://localhost:8000).

O Dark Studio continua sendo o app principal; o SupoClip vira so o "motor" de algumas funcoes
(Video do zero com a sua voz, vozes clonadas, pronuncia, fundos, musicas, em alta...).
Autenticacao: chave pessoal criada em SupoClip > Agentes e API, guardada em .env como SUPOCLIP_API_KEY.
Nada aqui mexe no gerador de imagens do Dark Studio.
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
URL = os.environ.get("SUPOCLIP_URL", "http://localhost:8000")


def _chave():
    if os.environ.get("SUPOCLIP_API_KEY"):
        return os.environ["SUPOCLIP_API_KEY"].strip()
    try:
        for linha in open(os.path.join(BASE, ".env"), encoding="utf-8"):
            if linha.strip().startswith("SUPOCLIP_API_KEY="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def configurado():
    return bool(_chave() or (_usuario() and _env_supoclip("BACKEND_AUTH_SECRET")))


def status():
    """{'ligado': servidor responde, 'chave': chave presente, 'ok': chave aceita}"""
    import requests
    s = {"ligado": False, "chave": configurado(), "ok": False}
    try:
        requests.get(f"{URL}/openapi.json", timeout=3)
        s["ligado"] = True
        if s["chave"]:
            r = requests.get(f"{URL}/tasks/studio/voices", headers=_cab(), timeout=8)
            s["ok"] = r.status_code == 200
            if not s["ok"]:
                s["erro"] = r.text[:200]
    except Exception as e:
        s["erro"] = str(e)[:200]
    return s


def _env_supoclip(nome):
    """Le um valor do .env do proprio SupoClip (pasta D:/SupoClip) - autorizado pelo usuario; nunca e copiado nem exibido."""
    try:
        for linha in open(__import__("config").SUPOCLIP_ENV, encoding="utf-8"):
            if linha.strip().startswith(nome + "="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def _usuario():
    if os.environ.get("SUPOCLIP_USER_ID"):
        return os.environ["SUPOCLIP_USER_ID"].strip()
    try:
        for linha in open(os.path.join(BASE, ".env"), encoding="utf-8"):
            if linha.strip().startswith("SUPOCLIP_USER_ID="):
                return linha.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def _cab():
    """Mesma identificacao que a tela do SupoClip usa (assinatura HMAC do usuario); ou chave sk_ se existir."""
    if _chave():
        return {"x-api-key": _chave()}
    import hmac, hashlib, time
    uid, seg, ts = _usuario(), _env_supoclip("BACKEND_AUTH_SECRET"), str(int(time.time()))
    if not uid or not seg:
        return {}
    return {"x-supoclip-user-id": uid, "x-supoclip-ts": ts,
            "x-supoclip-signature": hmac.new(seg.encode(), f"{uid}:{ts}".encode(), hashlib.sha256).hexdigest()}


# rotas liberadas (o usuario autorizou usar tudo) - ficam de fora so admin, chaves, cobranca e exclusao de conta
PERMITIDAS = ("/tasks", "/social", "/fonts", "/transitions", "/caption-templates", "/broll", "/upload", "/feedback", "/health")


def chamar(metodo, caminho, corpo=None, consulta=None, bruto=False, timeout=600):
    """Repassa uma chamada ao SupoClip com a chave. Devolve (status, tipo, bytes)."""
    import requests
    if not any(caminho.startswith(p) for p in PERMITIDAS):
        return 403, "application/json", b'{"detail":"rota nao liberada no Dark Studio"}'
    if not configurado():
        return 401, "application/json", b'{"detail":"Coloque SUPOCLIP_API_KEY no arquivo .env (crie a chave em SupoClip > Agentes e API)"}'
    r = requests.request(metodo, f"{URL}{caminho}", headers=_cab(), params=consulta,
                         data=corpo if bruto else None, json=None if bruto else corpo, timeout=timeout)
    return r.status_code, r.headers.get("content-type", "application/octet-stream"), r.content


def importar(job_id, destino_base):
    """Traz um video pronto do SupoClip para 'Para aprovar' do Dark Studio (video.mp4 + roteiro.json + miniatura)."""
    import json, re, datetime, subprocess
    st, _, b = chamar("GET", f"/tasks/studio/videos/{job_id}")
    if st != 200:
        raise RuntimeError(f"video nao encontrado no SupoClip ({st})")
    info = json.loads(b)
    if info.get("status") != "done":
        raise RuntimeError("o video ainda nao terminou no SupoClip")
    titulo = (info.get("hook") or info.get("title") or "Video com minha voz").strip()
    nome = re.sub(r"[^\w\- ]", "", titulo)[:40].strip().replace(" ", "_") or "video_voz"
    pasta = os.path.join(destino_base, f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{nome}")
    os.makedirs(pasta, exist_ok=True)
    st, _, video = chamar("GET", f"/tasks/studio/videos/{job_id}/file", timeout=900)
    if st != 200:
        raise RuntimeError(f"falha ao baixar o video ({st})")
    open(os.path.join(pasta, "video.mp4"), "wb").write(video)
    post = info.get("post") or {}
    vertical = info.get("format") != "horizontal"
    rot = {"titulo": (post.get("titles") or [titulo])[0] if isinstance(post.get("titles"), list) else titulo,
           "descricao": post.get("description") or "", "formato": "short" if vertical else "longo",
           "tela": "9:16" if vertical else "16:9", "tema_canal": "Vídeo com minha voz (SupoClip)",
           "cenas": [], "origem": {"supoclip_job": job_id}, "custo_usd": 0}
    try:  # duracao + miniatura a partir do video
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        out = subprocess.run([ff, "-i", "video.mp4"], cwd=pasta, capture_output=True, text=True).stderr
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
        if m:
            rot["duracao_s"] = round(int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]), 1)
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "1", "-i", "video.mp4", "-frames:v", "1", "miniatura.jpg"], cwd=pasta)
    except Exception:
        pass
    json.dump(rot, open(os.path.join(pasta, "roteiro.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return os.path.basename(pasta)

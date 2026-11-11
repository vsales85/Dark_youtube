"""Envio para o YouTube. Primeiro uso: python youtube.py (abre o navegador para autorizar)."""
import json, os, datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.path.join(BASE, "token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/youtube.force-ssl"]  # force-ssl: enviar a miniatura


def conectar():
    cred = Credentials.from_authorized_user_file(TOKEN, SCOPES) if os.path.exists(TOKEN) else None
    if cred and cred.expired and cred.refresh_token:
        cred.refresh(Request())
    elif not cred or not cred.valid:
        flow = InstalledAppFlow.from_client_secrets_file(os.path.join(BASE, "client_secret.json"), SCOPES)
        cred = flow.run_local_server(port=0, prompt="consent")
    open(TOKEN, "w").write(cred.to_json())
    return build("youtube", "v3", credentials=cred)


def enviar(pasta, publicar_em=None):
    """publicar_em: 'AAAA-MM-DDTHH:MM' (horario de Brasilia) -> sobe privado e o YouTube publica sozinho nessa hora."""
    rot = json.load(open(os.path.join(pasta, "roteiro.json"), encoding="utf-8"))
    pub = rot.get("publicacao") or {}
    titulo = (pub.get("titulo") or rot["titulo"])[:100]
    if rot.get("formato") == "short" and "#shorts" not in titulo.lower():
        titulo = (titulo + " #shorts")[:100]
    vis = pub.get("visibilidade") if pub.get("visibilidade") in ("public", "unlisted", "private") else "private"
    status = {"privacyStatus": "private" if publicar_em else vis, "selfDeclaredMadeForKids": bool(pub.get("para_criancas", False)),
              "containsSyntheticMedia": bool(pub.get("conteudo_ia", True))}
    if publicar_em:
        dt = datetime.datetime.fromisoformat(publicar_em).replace(tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
        if dt <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15):
            raise ValueError("Escolha um horario pelo menos 15 minutos no futuro.")
        status["publishAt"] = dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    corpo = {"snippet": {"title": titulo, "description": pub.get("descricao") or rot.get("descricao", ""),
                         "tags": pub.get("tags", []), "categoryId": pub.get("categoria", "24"),
                         "defaultLanguage": "pt-BR", "defaultAudioLanguage": "pt-BR"},
             "status": status}
    yt = conectar()
    r = yt.videos().insert(part="snippet,status", body=corpo,
                           media_body=MediaFileUpload(os.path.join(pasta, "video.mp4"), chunksize=8 << 20, resumable=True)).execute()
    mini = os.path.join(pasta, "miniatura.jpg")
    aviso_mini = ""
    if os.path.exists(mini):
        try:
            yt.thumbnails().set(videoId=r["id"], media_body=MediaFileUpload(mini)).execute()
        except Exception as e:
            aviso_mini = f" (miniatura nao enviada: {str(e)[:80]} - canais novos precisam verificar o telefone em youtube.com/verify)"
    url = f"https://youtu.be/{r['id']}"
    open(os.path.join(pasta, "youtube.txt"), "w").write(url)
    rot["youtube"] = {"url": url, "id": r["id"], "enviado_em": datetime.datetime.now().isoformat(timespec="seconds"),
                      "publicar_em": publicar_em, "status_api": r.get("status", {})}
    rot["agenda"] = {"publicar_em": publicar_em, "status": "agendado" if publicar_em else "enviado"}
    json.dump(rot, open(os.path.join(pasta, "roteiro.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return url + aviso_mini


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "enviar":  # usado pela fila do painel
        print("Enviando para o YouTube...", flush=True)
        print("Pronto!", enviar(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None), flush=True)
        sys.exit(0)
    yt = conectar()
    c = yt.channels().list(part="snippet", mine=True).execute()["items"][0]["snippet"]["title"]
    print("Conectado ao canal:", c)

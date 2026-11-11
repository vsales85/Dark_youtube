"""Preenche a pasta imagens/ de um video com fotos de acordo com cada cena (gratis, sem IA paga).
Fontes: Pixabay (se PIXABAY_API_KEY no .env) -> Openverse (sem chave, so licencas de uso comercial).
Uso: python imagens_auto.py <pasta_do_video>
Nao sobrescreve imagens que voce ja colocou.
"""
import json, os, sys, time, requests
from dotenv import load_dotenv

load_dotenv()
UA = {"User-Agent": "DarkStudio/1.0 (uso pessoal)"}
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm")


def pixabay(q, usados):
    k = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not k:
        return None
    r = requests.get("https://pixabay.com/api/", timeout=20, params={
        "key": k, "q": q, "image_type": "photo", "safesearch": "true", "per_page": 20}).json()
    for h in r.get("hits", []):
        if h["id"] not in usados:
            usados.add(h["id"])
            return h["largeImageURL"], f"Pixabay: {h['pageURL']} (por {h.get('user', '')})"
    return None


def openverse(q, usados):
    r = requests.get("https://api.openverse.org/v1/images/", headers=UA, timeout=25, params={
        "q": q, "license_type": "commercial,modification", "page_size": 20, "mature": "false",
        "aspect_ratio": "wide"}).json()
    for h in r.get("results", []):
        if h["id"] in usados or not h.get("url"):
            continue
        if (h.get("width") or 0) < 800:
            continue
        usados.add(h["id"])
        return h["url"], f"{h.get('title', '')} - {h.get('creator', '')} - {h.get('license', '').upper()} {h.get('license_version', '')} - {h.get('foreign_landing_url', '')}"
    return None


def buscar(q, usados):
    tentativas = [q, " ".join(q.split()[:2]), q.split()[0]]
    for termo in tentativas:
        for fonte in (pixabay, openverse):
            try:
                res = fonte(termo, usados)
                if res:
                    return res
            except Exception as e:
                print(f"   ! {fonte.__name__}: {str(e)[:60]}")
                if "429" in str(e) or "Too Many" in str(e):
                    time.sleep(20)  # limite da Openverse: espera e segue
    return None


def preencher(pasta):
    rot = json.load(open(os.path.join(pasta, "roteiro.json"), encoding="utf-8"))
    dest = os.path.join(pasta, "imagens")
    os.makedirs(dest, exist_ok=True)
    existentes = {os.path.splitext(f)[0].lower() for f in os.listdir(dest) if f.lower().endswith(EXTS)}
    creditos, usados, feitas = [], set(), 0
    for i, c in enumerate(rot["cenas"], 1):
        nome = f"cena{i:02d}"
        if nome in existentes:
            continue
        q = c.get("busca") or "dramatic scene"
        res = buscar(q, usados)
        if not res:
            print(f"   {nome}: nada encontrado para '{q}'")
            continue
        url, credito = res
        try:
            img = requests.get(url, headers=UA, timeout=40)
            img.raise_for_status()
            ext = ".png" if "png" in img.headers.get("Content-Type", "") else ".jpg"
            open(os.path.join(dest, nome + ext), "wb").write(img.content)
            creditos.append(f"{nome}: {credito}")
            feitas += 1
            print(f"   {nome}: ok ({q})")
        except Exception as e:
            print(f"   {nome}: falhou ao baixar ({str(e)[:50]})")
    if creditos:
        with open(os.path.join(dest, "CREDITOS.txt"), "a", encoding="utf-8") as fh:
            fh.write("\n".join(creditos) + "\n")
    print(f"Pronto: {feitas} imagens novas em {dest}")
    return feitas


if __name__ == "__main__":
    preencher(os.path.abspath(sys.argv[1]))

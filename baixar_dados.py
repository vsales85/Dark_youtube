"""Baixa os dados livres que o app usa (rode uma vez em cada PC novo).

  python baixar_dados.py            -> mapas + fronteiras + fontes + detector de rosto  (~400 MB, so processador)
  python baixar_dados.py --imagens  -> tambem o modelo de imagens RealVisXL (~7 GB, para os videos com imagens geradas)

Tudo e de uso livre: Natural Earth (dominio publico), Google Fonts (OFL), OpenCV Zoo (Apache/MIT),
RealVisXL V5 Lightning (licenca do autor no Hugging Face - confira antes de uso comercial).
"""
import os, sys, urllib.request, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

MAPAS = config.MAPAS
os.makedirs(os.path.join(MAPAS, "fontes"), exist_ok=True)
os.makedirs(os.path.dirname(config.ROSTO), exist_ok=True)


def baixar(url, destino):
    if os.path.exists(destino) and os.path.getsize(destino) > 1000:
        print("   ja existe:", os.path.basename(destino)); return
    print("   baixando", os.path.basename(destino), "...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "DarkStudio-instalador/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(destino + ".tmp", "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(destino + ".tmp", destino)


def mapa_escuro():
    """Natural Earth II (relevo) -> versao escura do canal em 4 tamanhos."""
    if all(os.path.exists(os.path.join(MAPAS, f"escuro_{n}.jpg")) for n in (1, 2, 4, 8)):
        print("   mapas escuros ja prontos"); return
    import numpy as np
    from PIL import Image, ImageEnhance
    Image.MAX_IMAGE_PIXELS = None
    z = os.path.join(MAPAS, "ne2.zip")
    baixar("https://naciscdn.org/naturalearth/10m/raster/NE2_HR_LC_SR_W_DR.zip", z)
    with zipfile.ZipFile(z) as zz:
        tif = next(n for n in zz.namelist() if n.lower().endswith(".tif"))
        zz.extract(tif, MAPAS)
    src = Image.open(os.path.join(MAPAS, tif)).convert("RGB")

    def grade(im):
        a = np.asarray(im).astype(np.float32) / 255
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        agua = np.clip((b - r - 0.08) * 6, 0, 1)[..., None]
        terra = np.clip(a * 0.62, 0, 1); terra = np.clip((terra - 0.5) * 1.35 + 0.5 - 0.08, 0, 1)
        luz = a.mean(2) - 0.5
        mar = np.stack([0.05 + 0.10 * (1 - b) + luz * 0.25, 0.22 + 0.25 * g + luz * 0.35, 0.30 + 0.28 * b + luz * 0.35], -1)
        out = terra * (1 - agua) + np.clip(mar, 0, 1) * agua
        return ImageEnhance.Color(Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))).enhance(1.15)

    print("   preparando o mapa escuro (alguns minutos)...", flush=True)
    W, H = src.size
    out = Image.new("RGB", (W, H))
    for i in range(4):
        y0, y1 = i * H // 4, (i + 1) * H // 4
        out.paste(grade(src.crop((0, y0, W, y1))), (0, y0))
    out.save(os.path.join(MAPAS, "escuro_1.jpg"), quality=90)
    for f in (2, 4, 8):
        out.resize((W // f, H // f), Image.LANCZOS).save(os.path.join(MAPAS, f"escuro_{f}.jpg"), quality=90)
    os.remove(os.path.join(MAPAS, tif)); os.remove(z)


def main():
    print("1/4 Fronteiras (Natural Earth)")
    base = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    baixar(base + "ne_10m_admin_1_states_provinces.geojson", os.path.join(MAPAS, "estados.geojson"))
    baixar(base + "ne_10m_admin_0_countries.geojson", os.path.join(MAPAS, "paises.geojson"))
    print("2/4 Fontes (Google Fonts, OFL)")
    g = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
    for url, nome in ((g + "anton/Anton-Regular.ttf", "Anton.ttf"), (g + "oswald/Oswald%5Bwght%5D.ttf", "Oswald.ttf"),
                      (g + "montserrat/Montserrat%5Bwght%5D.ttf", "Montserrat.ttf"),
                      (g + "ebgaramond/EBGaramond-Italic%5Bwght%5D.ttf", "Garamond-Italic.ttf")):
        baixar(url, os.path.join(MAPAS, "fontes", nome))
    print("3/4 Detector de rosto (OpenCV Zoo)")
    baixar("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx", config.ROSTO)
    print("4/4 Mapa-mundi em relevo (Natural Earth II, ~325 MB)")
    mapa_escuro()
    if "--imagens" in sys.argv:
        print("Extra: modelo de imagens RealVisXL V5 Lightning (~7 GB)")
        os.environ["HF_HOME"] = config.HF_HOME
        from huggingface_hub import hf_hub_download
        hf_hub_download("SG161222/RealVisXL_V5.0_Lightning", "RealVisXL_V5.0_Lightning_fp16.safetensors")
    print("\nPronto! Dados em:", config.MODELOS)


if __name__ == "__main__":
    main()

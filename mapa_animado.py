"""MAPA ANIMADO - motor de Shorts de historia/geografia com mapas (roda 100% no PC, sem placa de video).

Pipeline: roteiro (Gemini, JSON com cenas) -> narracao com tempo de cada palavra (Edge TTS)
          -> quadros desenhados com Skia (mapa escuro + estados com bandeira + fronteira se desenhando
             + ano + selo + caixas + documento + retrato + icones + legenda karaoke) -> FFmpeg (video + voz + trilha).
Dados livres em D:/modelos_imagem/mapas (Natural Earth II = dominio publico; fontes Google = OFL;
icones Twemoji = CC-BY 4.0 -> credito na descricao; retratos Wikimedia so de dominio publico).
"""
import asyncio, io, json, math, os, re, subprocess, sys, time, urllib.parse, urllib.request
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
DADOS = config.MAPAS
CACHE = os.path.join(DADOS, "cache")
os.makedirs(CACHE, exist_ok=True)
FONTE_FORTE = os.path.join(DADOS, "fontes", "Anton.ttf")
FONTE_ITALICA = os.path.join(DADOS, "fontes", "Garamond-Italic.ttf")
FONTE_TEXTO = os.path.join(DADOS, "fontes", "Montserrat.ttf")
AMARELO = (255, 210, 30)
UA = {"User-Agent": "DarkStudio/1.0 (uso pessoal; mapas educativos)"}


def log(m):
    print(f"   [mapa] {m}", flush=True)


# ------------------------------------------------------------------ mapa base (piramide de resolucoes)
from PIL import Image, ImageFilter
Image.MAX_IMAGE_PIXELS = None
_BASES = {}


def base(nivel):
    if nivel not in _BASES:
        _BASES[nivel] = Image.open(os.path.join(DADOS, f"escuro_{nivel}.jpg")).convert("RGB")
        _BASES[nivel].load()
    return _BASES[nivel]


GRAUS_MIN = 5.0  # menos que isso o relevo fica borrado (mapa base: 60 px por grau)


class Camera:
    def __init__(self, lon, lat, graus, W, H):
        self.lon, self.lat, self.graus, self.W, self.H = lon, lat, max(GRAUS_MIN * W / 1080, graus), W, H
        self.px = W / self.graus                       # pixels por grau de longitude
        self.py = self.px / max(0.2, math.cos(math.radians(lat)))  # "Mercator local": norte-sul esticado

    def xy(self, lon, lat):
        return (lon - self.lon) * self.px + self.W / 2, (self.lat - lat) * self.py + self.H / 2

    def fundo(self):
        gl, ga = self.W / self.px, self.H / self.py   # graus visiveis
        for nivel in (8, 4, 2, 1):                      # menor imagem que ainda tem resolucao suficiente
            b = base(nivel)
            if gl / 360 * b.width >= self.W * 0.9 or nivel == 1:
                break
        x0 = (self.lon - gl / 2 + 180) / 360 * b.width
        y0 = (90 - (self.lat + ga / 2)) / 180 * b.height
        x1, y1 = x0 + gl / 360 * b.width, y0 + ga / 180 * b.height
        return b.resize((self.W, self.H), Image.BILINEAR, box=(x0, y0, x1, y1))


# ------------------------------------------------------------------ fronteiras (Natural Earth)
_GEO = None


def _norm(s):
    from unidecode import unidecode
    return re.sub(r"[^a-z0-9]+", " ", unidecode(str(s or "")).lower()).strip()


def geo():
    global _GEO
    if _GEO is None:
        from shapely.geometry import shape
        _GEO = {}
        for arq, campos in (("paises.geojson", ("NAME_PT", "NAME", "ADMIN", "NAME_LONG", "NAME_EN")),
                            ("estados.geojson", ("name_pt", "name", "name_en", "woe_name", "gn_name"))):
            for f in json.load(open(os.path.join(DADOS, arq), encoding="utf-8"))["features"]:
                p = f["properties"]
                g = shape(f["geometry"]).simplify(0.01, preserve_topology=True)
                info = {"geom": g, "nome": p.get("NAME_PT") or p.get("name_pt") or p.get("NAME") or p.get("name"),
                        "en": p.get("NAME_EN") or p.get("name_en") or p.get("NAME") or p.get("name"),
                        "pais": p.get("admin") or p.get("ADMIN"), "tipo": "pais" if arq.startswith("paises") else "estado"}
                for c in campos:
                    k = _norm(p.get(c))
                    if k and (k not in _GEO or info["tipo"] == "pais"):
                        _GEO[k] = info
        for apelido, real in (("brasil", "brazil"), ("italia", "italy"), ("alemanha", "germany"), ("eua", "united states of america"),
                              ("estados unidos", "united states of america"), ("inglaterra", "united kingdom"), ("franca", "france")):
            if _norm(real) in _GEO and apelido not in _GEO:
                _GEO[apelido] = _GEO[_norm(real)]
    return _GEO


def regiao(nome):
    g = geo()
    k = _norm(nome)
    if k in g:
        return g[k]
    cands = [v for kk, v in g.items() if k and (kk.startswith(k) or k in kk)]
    return cands[0] if cands else None


def _aneis(geom):
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    return [list(p.exterior.coords) for p in polys if p.area > 0.002]


# ------------------------------------------------------------------ imagens externas (cache local)
def baixar(url, nome):
    f = os.path.join(CACHE, nome)
    if not os.path.exists(f):
        try:
            dados = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
            with open(f, "wb") as fh:
                fh.write(dados)
        except Exception as e:
            log(f"nao baixou {nome}: {str(e)[:60]}")
            return None
    return f


def _buscar_bandeira(texto):
    """Procura no Wikimedia Commons o arquivo de bandeira mais parecido com o texto."""
    try:
        q = urllib.parse.urlencode({"action": "query", "format": "json", "list": "search", "srnamespace": 6, "srlimit": 6,
                                    "srsearch": re.sub(r"\.svg$", "", texto) + " flag"})
        r = json.loads(urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers=UA), timeout=20).read())
        for it in r.get("query", {}).get("search", []):
            t = it["title"].replace("File:", "")
            if t.lower().startswith(("flag", "bandeira")) and t.lower().endswith(".svg"):
                return t
    except Exception:
        pass
    return None


def _abrir_bandeira(nome):
    import skia
    arq = baixar("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(nome) + "?width=900",
                 "flag_" + _norm(nome).replace(" ", "_")[:60] + ".png")
    if arq and os.path.getsize(arq) > 500:
        try:
            return skia.Image.open(arq)
        except Exception:
            os.remove(arq)
    return None


def bandeira(info, arquivo=None):
    """Bandeira do pais/estado (Wikimedia Commons). arquivo = bandeira HISTORICA (nome aproximado; e procurado)."""
    if arquivo:  # bandeira historica: nome exato, senao a mais parecida na busca
        for t in (arquivo, _buscar_bandeira(arquivo)):
            img = _abrir_bandeira(t) if t else None
            if img is not None:
                return img
    tent = []
    if info["tipo"] == "estado":
        tent += [f"Bandeira de {info['nome']}.svg", f"Flag of {info['en']} (state).svg", f"Bandeira do estado de {info['nome']}.svg"]
    tent += [f"Flag of {info['en']}.svg", f"Flag of the {info['en']}.svg"]
    for t in tent:
        img = _abrir_bandeira(t)
        if img is not None:
            return img
    achado = _buscar_bandeira(f"Flag of {info['en']}" + (" state" if info["tipo"] == "estado" else ""))  # ultimo recurso
    return _abrir_bandeira(achado) if achado else None


def retrato_commons(busca):
    """Primeira pintura/foto de DOMINIO PUBLICO no Wikimedia Commons para a busca."""
    import skia
    chave = "ret_" + _norm(busca).replace(" ", "_")[:50]
    pronto = [f for f in os.listdir(CACHE) if f.startswith(chave + ".")]
    if pronto:
        return skia.Image.open(os.path.join(CACHE, pronto[0]))
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                                "gsrsearch": busca + " filetype:bitmap", "gsrlimit": 10, "prop": "imageinfo",
                                "iiprop": "url|extmetadata", "iiurlwidth": 500})
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers=UA), timeout=30).read())
        for p in sorted(r.get("query", {}).get("pages", {}).values(), key=lambda x: x.get("index", 99)):
            ii = (p.get("imageinfo") or [{}])[0]
            lic = (ii.get("extmetadata", {}).get("LicenseShortName", {}) or {}).get("value", "").lower()
            if ("public domain" in lic or lic.startswith("pd") or "cc0" in lic) and ii.get("thumburl"):
                arq = baixar(ii["thumburl"], chave + ".jpg")
                if arq:
                    return skia.Image.open(arq)
    except Exception as e:
        log(f"retrato nao encontrado ({busca}): {str(e)[:60]}")
    return None


def icone(emoji):
    """Emoji Twemoji (CC-BY 4.0) renderizado do SVG."""
    import skia
    cod = "-".join(f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F)
    arq = baixar(f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/svg/{cod}.svg", f"emo_{cod}.svg")
    if not arq:
        return None
    try:
        dom = skia.SVGDOM.MakeFromStream(skia.Stream.MakeFromFile(arq))
        sup = skia.Surface(256, 256)
        dom.setContainerSize(skia.Size(256, 256))
        dom.render(sup.getCanvas())
        return sup.makeImageSnapshot()
    except Exception:
        return None


# ------------------------------------------------------------------ desenho (Skia)
def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _quando(k, n, dur):
    """Momento de entrada do elemento k de n, espalhado pela cena (algo novo a cada ~1-2s)."""
    if n <= 1:
        return 0.2
    return 0.2 + k * max(0.35, min(1.6, dur * 0.7 / n))


def _pop(t, dur=0.35):
    """Entrada com "mola" (escala 0 -> 1.08 -> 1)."""
    if t <= 0:
        return 0.0
    t = min(1.0, t / dur)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _tf(caminho, tam):
    import skia
    return skia.Font(skia.Typeface.MakeFromFile(caminho), tam)


def _caminho(cam, aneis):
    import skia
    p = skia.Path()
    for anel in aneis:
        pts = [cam.xy(x, y) for x, y in anel]
        p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        p.close()
    return p


def texto_contorno(c, txt, x, y, fonte, cor=(255, 255, 255), contorno=8, alinhar="centro", alfa=255, sombra=True):
    import skia
    larg = fonte.measureText(txt)
    if alinhar == "centro":
        x -= larg / 2
    blob = skia.TextBlob.MakeFromString(txt, fonte)
    if sombra:
        c.drawTextBlob(blob, x + 3, y + 5, skia.Paint(Color=skia.Color4f(0, 0, 0, 0.55 * alfa / 255), AntiAlias=True,
                                                      MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 5)))
    if contorno:
        c.drawTextBlob(blob, x, y, skia.Paint(Color=skia.ColorSetARGB(alfa, 0, 0, 0), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                              StrokeWidth=contorno, StrokeJoin=skia.Paint.kRound_Join))
    c.drawTextBlob(blob, x, y, skia.Paint(Color=skia.ColorSetARGB(alfa, *cor), AntiAlias=True))
    return larg


def caixa(c, x, y, w, h, raio=10, fundo=(14, 18, 22), alfa=235, borda=(200, 170, 90)):
    import skia
    r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), raio, raio)
    c.drawRRect(r, skia.Paint(Color=skia.ColorSetARGB(alfa, *fundo), AntiAlias=True))
    c.drawRRect(r, skia.Paint(Color=skia.ColorSetARGB(200, *borda), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=2.5))


def imagem_em(c, img, rect, alfa=1.0, circulo=False):
    import skia
    c.save()
    if circulo:
        c.clipRRect(skia.RRect.MakeOval(rect), doAntiAlias=True)
    iw, ih = img.width(), img.height()
    esc = max(rect.width() / iw, rect.height() / ih)  # "cobrir"
    w, h = iw * esc, ih * esc
    dst = skia.Rect.MakeXYWH(rect.centerX() - w / 2, rect.centerY() - h / 2, w, h)
    c.clipRect(rect, doAntiAlias=True)
    c.drawImageRect(img, dst, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=alfa))
    c.restore()


# ------------------------------------------------------------------ uma cena -> quadros
class Renderizador:
    def __init__(self, roteiro, W=1080, H=1920):
        self.r, self.W, self.H = roteiro, W, H
        self.f_leg = _tf(FONTE_FORTE, int(W * 0.088))
        self.f_ano = _tf(FONTE_ITALICA, int(W * 0.06))
        self.f_selo = _tf(FONTE_FORTE, int(W * 0.036))
        self.f_cx_t = _tf(FONTE_FORTE, int(W * 0.030))
        self.f_cx_v = _tf(FONTE_FORTE, int(W * 0.075))
        self.f_doc = _tf(FONTE_ITALICA, int(W * 0.040))
        self.f_rot = _tf(FONTE_ITALICA, int(W * 0.042))
        self.cache_img = {}

    def _flag_nome(self, nome, arquivo=None):
        if str(nome).lower().startswith("arquivo:"):  # bandeira historica no distintivo: "arquivo:Flag of the Soviet Union"
            alvo = str(nome)[8:].strip()
            def achar():
                for nome_ in (alvo if alvo.lower().endswith(".svg") else alvo + ".svg", alvo):
                    img = _abrir_bandeira(nome_)
                    if img is not None:
                        return img
                b_ = _buscar_bandeira(alvo)
                return _abrir_bandeira(b_) if b_ else None
            return self._img("hist_" + alvo, achar)
        info = regiao(nome)
        return self._img("flag_" + info["en"] + str(arquivo), lambda: bandeira(info, arquivo)) if info else None

    def _img(self, chave, fn):
        if chave not in self.cache_img:
            self.cache_img[chave] = fn()
        return self.cache_img[chave]

    def quadro(self, cena, t, dur, cam, destaques, palavras):
        import skia
        W, H = self.W, self.H
        fundo = cam.fundo()
        if cena.get("escuro"):
            fundo = Image.blend(fundo, Image.new("RGB", fundo.size, (2, 6, 10)), 0.55 * _ease(t / 0.6))
        sup = skia.Surface(W, H)
        c = sup.getCanvas()
        import objetos
        espaco = cena.get("cenario") == "espaco"
        if espaco:  # historias espaciais: ceu estrelado + astros (sem mapa)
            objetos.fundo_espaco(c, W, H, t)
            terra = self._img("terra_espaco", lambda: skia.Image.frombytes(Camera(-45, -5, 120, 512, 512).fundo().convert("RGBA").tobytes(), skia.ISize(512, 512), skia.kRGBA_8888_ColorType))
            for k, a in enumerate(cena.get("astros") or []):
                esc = min(1.0, _pop(t - 0.1 - k * 0.15, 0.35))
                if esc > 0:
                    objetos.astro(c, a.get("tipo", "lua"), W * float(a.get("x", 0.5)), H * float(a.get("y", 0.3)), W * float(a.get("tam", 0.2)) * esc, t, terra)
        else:
            c.drawImage(skia.Image.frombytes(fundo.convert("RGBA").tobytes(), skia.ISize(W, H), skia.kRGBA_8888_ColorType), 0, 0)

        # estados/paises destacados (bandeira recortada no formato) - persistem entre cenas
        for d in destaques:
            info = regiao(d.get("regiao"))
            if not info:
                continue
            p = _caminho(cam, _aneis(info["geom"]))
            a = d.get("_alfa", 1.0) if d.get("_velho") else _ease(t / 0.5)
            arq = d.get("bandeira_arquivo")
            flag = self._img("flag_" + info["en"] + str(arq), lambda: bandeira(info, arq)) if d.get("tipo", "bandeira") == "bandeira" else None
            if flag is not None:
                c.save(); c.clipPath(p, doAntiAlias=True)
                imagem_em(c, flag, p.getBounds(), alfa=0.88 * a)
                c.restore()
            else:
                cor = d.get("cor") or [200, 40, 50]
                c.drawPath(p, skia.Paint(Color=skia.ColorSetARGB(int(150 * a), *cor[:3]), AntiAlias=True))
            c.drawPath(p, skia.Paint(Color=skia.ColorSetARGB(int(210 * a), 240, 240, 235), AntiAlias=True,
                                     Style=skia.Paint.kStroke_Style, StrokeWidth=2))

        # fronteira se desenhando (brilho amarelo)
        for nome in cena.get("fronteiras") or []:
            info = regiao(nome)
            if not info:
                continue
            prog = _ease((t - 0.2) / max(0.8, min(2.2, dur * 0.6)))
            for anel in _aneis(info["geom"])[:3]:
                p = _caminho(cam, [anel])
                med = skia.PathMeasure(p, False)
                seg = skia.Path()
                med.getSegment(0, med.getLength() * prog, seg, True)
                c.drawPath(seg, skia.Paint(Color=skia.ColorSetARGB(170, 255, 220, 60), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                           StrokeWidth=14, StrokeCap=skia.Paint.kRound_Cap,
                                           MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 8)))
                c.drawPath(seg, skia.Paint(Color=skia.ColorSetARGB(255, 255, 236, 140), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                           StrokeWidth=4, StrokeCap=skia.Paint.kRound_Cap))

        # rota/linha (ex.: travessia do navio) com ponta animada
        rota = cena.get("rota")
        if rota and len(rota.get("pontos") or []) >= 2:
            pts = [cam.xy(lo, la) for lo, la in rota["pontos"]]
            p = skia.Path(); p.moveTo(*pts[0])
            for q in pts[1:]:
                p.lineTo(*q)
            med = skia.PathMeasure(p, False)
            seg = skia.Path(); prog = _ease((t - 0.2) / max(1.0, dur * 0.7))
            med.getSegment(0, med.getLength() * prog, seg, True)
            cor = rota.get("cor") or [230, 40, 40]
            c.drawPath(seg, skia.Paint(Color=skia.ColorSetARGB(150, *cor[:3]), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=12,
                                       MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 7)))
            c.drawPath(seg, skia.Paint(Color=skia.ColorSetARGB(255, *cor[:3]), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=5,
                                       PathEffect=skia.DashPathEffect.Make([22, 12], 0)))
            pos = med.getPosTan(med.getLength() * prog)
            if pos and rota.get("emoji"):
                ic = self._img("emo" + rota["emoji"], lambda: icone(rota["emoji"]))
                if ic:
                    s = W * 0.11
                    c.drawImageRect(ic, skia.Rect.MakeXYWH(pos[0].x() - s / 2, pos[0].y() - s / 2, s, s), skia.SamplingOptions(skia.FilterMode.kLinear))

        # pontos e rotulos no mapa
        for k, rt in enumerate(cena.get("rotulos") or []):
            if rt.get("lon") is None:
                continue
            x, y = cam.xy(rt["lon"], rt["lat"])
            a = _pop(t - _quando(k, len(cena.get("rotulos") or []), dur) - 0.1)
            if a <= 0:
                continue
            c.drawCircle(x, y, 9 * a, skia.Paint(Color=skia.ColorSetARGB(255, 230, 40, 40), AntiAlias=True))
            c.drawCircle(x, y, 9 * a, skia.Paint(Color=skia.ColorWHITE, AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=3))
            texto_contorno(c, rt.get("texto", ""), x, y - 22, self.f_rot, cor=(255, 245, 225), contorno=5, alfa=int(255 * min(1, a)))

        # icones sobre o mapa (pop)
        for k, ic in enumerate(cena.get("icones") or []):
            img = self._img("emo" + ic.get("emoji", ""), lambda: icone(ic.get("emoji", "")))
            if not img or ic.get("lon") is None:
                continue
            x, y = cam.xy(ic["lon"], ic["lat"])
            s = W * 0.13 * _pop(t - _quando(k + 1, len(cena.get("icones") or []) + 1, dur))
            if s > 1:
                c.drawImageRect(img, skia.Rect.MakeXYWH(x - s / 2, y - s / 2, s, s), skia.SamplingOptions(skia.FilterMode.kLinear))

        # retrato em moldura dourada
        ret = cena.get("retrato")
        if ret and ret.get("busca"):
            img = self._img("ret" + ret["busca"], lambda: retrato_commons(ret["busca"]))
            if img:
                a = _pop(t - 0.25)
                r = W * 0.17 * a
                cx, cy = W * 0.73, H * 0.30
                if r > 1:
                    c.drawCircle(cx, cy, r + 9, skia.Paint(Color=skia.ColorSetARGB(255, 214, 178, 92), AntiAlias=True,
                                                           ImageFilter=skia.ImageFilters.DropShadow(0, 6, 10, 10, skia.ColorSetARGB(160, 0, 0, 0))))
                    imagem_em(c, img, skia.Rect.MakeXYWH(cx - r, cy - r, 2 * r, 2 * r), circulo=True)
                    if ret.get("nome") and a > 0.9:
                        texto_contorno(c, ret["nome"], cx, cy + r + 52, self.f_rot, cor=(240, 210, 130), contorno=5)

        # caixa de numero ("~140 MIL KM2")
        cx_ = cena.get("caixa")
        if cx_ and (cx_.get("valor") or cx_.get("titulo")):
            a = _pop(t - 0.4)
            if a > 0:
                c.save(); c.translate(W / 2, H * 0.17); c.scale(a, a)
                wv = max(self.f_cx_v.measureText(str(cx_.get("valor", ""))), self.f_cx_t.measureText(str(cx_.get("titulo", "")))) + 70
                caixa(c, -wv / 2, -95, wv, 180)
                texto_contorno(c, str(cx_.get("titulo", "")).upper(), 0, -45, self.f_cx_t, cor=(214, 178, 92), contorno=0, sombra=False)
                texto_contorno(c, str(cx_.get("valor", "")).upper(), 0, 55, self.f_cx_v, contorno=0, sombra=False)
                c.restore()

        # trecho de documento com grifo amarelo
        doc = cena.get("documento")
        if doc and doc.get("texto"):
            a = _pop(t - 0.3)
            if a > 0:
                c.save(); c.translate(W / 2, H * 0.26); c.scale(a, a); c.rotate(-2)
                linhas, atual = [], ""
                for pal in str(doc["texto"]).split():
                    if self.f_doc.measureText(atual + " " + pal) > W * 0.70 and atual:
                        linhas.append(atual); atual = pal
                    else:
                        atual = (atual + " " + pal).strip()
                linhas.append(atual)
                h = 90 + len(linhas) * 54
                caixa(c, -W * 0.40, -h / 2, W * 0.80, h, raio=4, fundo=(238, 228, 200), alfa=250, borda=(150, 120, 70))
                if doc.get("titulo"):
                    texto_contorno(c, str(doc["titulo"]).upper(), -W * 0.36, -h / 2 + 42, self.f_cx_t, cor=(120, 90, 50), contorno=0, alinhar="esq", sombra=False)
                grifo = _norm(doc.get("grifo", ""))
                y = -h / 2 + 100
                prog_grifo = _ease((t - 1.0) / 0.8)
                for ln in linhas:
                    if grifo and grifo in _norm(ln) and prog_grifo > 0:
                        wl = self.f_doc.measureText(ln) * prog_grifo
                        c.drawRect(skia.Rect.MakeXYWH(-W * 0.36, y - 38, wl, 48), skia.Paint(Color=skia.ColorSetARGB(170, 255, 214, 40)))
                    texto_contorno(c, ln, -W * 0.36, y, self.f_doc, cor=(40, 30, 20), contorno=0, alinhar="esq", sombra=False)
                    y += 54
                c.restore()

        # ano (canto) e selo do tema (topo)
        if self.r.get("_ano_atual"):
            texto_contorno(c, str(self.r["_ano_atual"]), W * 0.06, H * 0.075, self.f_ano, cor=(232, 196, 110), contorno=4, alinhar="esq")
        selo = self.r.get("selo")
        if selo:
            ws = self.f_selo.measureText(selo.upper()) + 60
            caixa(c, W / 2 - ws / 2, H * 0.035, ws, 70, raio=8)
            texto_contorno(c, selo.upper(), W / 2, H * 0.035 + 50, self.f_selo, contorno=0, sombra=False)

        # bandeiras em mastros, tropas e fumaca de batalha sobre o mapa
        import avatares
        for k, bm in enumerate(cena.get("bandeiras_mastro") or []):
            if bm.get("lon") is None:
                continue
            x, y = cam.xy(bm["lon"], bm["lat"])
            a = min(1.0, _pop(t - 0.2 - k * 0.2, 0.3))
            if a > 0:
                avatares.bandeira_mastro(c, self._flag_nome(bm.get("regiao", ""), bm.get("bandeira_arquivo")), x, y, H * 0.12 * a, t)
        for k, tp in enumerate(cena.get("tropas") or []):
            if tp.get("lon") is None:
                continue
            x, y = cam.xy(tp["lon"], tp["lat"])
            if t - 0.2 - k * 0.2 > 0:
                avatares.tropa(c, tp.get("tipo", "soldado"), tp.get("qtd", 5), x, y, H * 0.075, t, semente=k * 11, flag_fn=self._flag_nome)
        import objetos
        for k, ob in enumerate(cena.get("veiculos") or []):
            if not isinstance(ob, dict):
                continue
            p_ = _ease((t - 0.2) / max(1.0, dur * 0.85))
            if ob.get("x") is not None:  # posicao na TELA (0-1), usada no espaco
                x, y = W * float(ob["x"]), H * float(ob.get("y", 0.6))
                if ob.get("ate"):
                    x, y = x + (W * ob["ate"][0] - x) * p_, y + (H * ob["ate"][1] - y) * p_
            elif ob.get("lon") is not None:
                lon, lat = ob["lon"], ob["lat"]
                if ob.get("ate"):  # atravessa o mapa durante a cena
                    lon, lat = lon + (ob["ate"][0] - lon) * p_, lat + (ob["ate"][1] - lat) * p_
                    if ob.get("olha") is None:
                        ob = {**ob, "olha": "esq" if ob["ate"][0] < ob["lon"] else "dir"}
                x, y = cam.xy(lon, lat)
            else:
                continue
            a = min(1.0, _pop(t - 0.2 - k * 0.2, 0.3))
            if a > 0:
                objetos.desenhar(c, ob, x, y, W * 0.24 * a * float(ob.get("tamanho", 1)), t)
        for fm in cena.get("fumaca") or []:
            if fm.get("lon") is not None and t > 0.3:
                x, y = cam.xy(fm["lon"], fm["lat"])
                avatares.fumaca(c, x, y, W * 0.22, t)

        # bonequinhos animados (estilo proprio do canal)
        import avatares
        pers = [p for p in (cena.get("personagens") or []) if isinstance(p, dict)][:4]
        posx = {"esq": 0.2, "centro": 0.5, "dir": 0.8}
        lados = ["esq", "dir", "centro", "esq"]
        for k, p in enumerate(pers):
            tk = t - _quando(k, len(pers), dur)
            if tk < 0:
                continue
            lado = p.get("lado") or lados[k]
            if p.get("lon") is not None and p.get("lat") is not None:
                x, y = cam.xy(p["lon"], p["lat"]); y += H * 0.02
            else:
                x, y = W * posx.get(lado, 0.5) + (k // 3) * W * 0.12, H * 0.905
            x += avatares.entrada(lado, tk, W)
            esc = min(1.0, _pop(tk, 0.3)) if lado == "centro" else 1.0
            if p.get("olha") is None:
                p = {**p, "olha": "esq" if x > W * 0.6 else "dir"}
            c.save(); c.translate(x, y); c.scale(esc, esc)
            avatares.desenhar(c, p, 0, 0, H * (0.22 if len(pers) < 3 else 0.18), tk, semente=sum(map(ord, str(p.get("nome") or p.get("tipo")))) % 97,
                              flag_fn=self._flag_nome)
            c.restore()
            if p.get("nome") and tk > 0.4:
                texto_contorno(c, p["nome"], x, y + H * 0.035, self.f_rot, cor=(255, 240, 200), contorno=5)

        # bandeira GIGANTE em tela cheia (cresce tremulando, segura e encolhe) - abre video / apresenta pais
        bt = cena.get("bandeira_tela")
        if bt:
            fi = self._flag_nome(bt if isinstance(bt, str) else bt.get("regiao", ""), None if isinstance(bt, str) else bt.get("bandeira_arquivo"))
            if fi is not None:
                fase = min(1.0, t / 0.45) if t < min(1.8, dur * 0.6) else max(0.0, 1 - (t - min(1.8, dur * 0.6)) / 0.4)
                e = _ease(fase)
                if e > 0:
                    fw, fh = W * (0.3 + 0.75 * e), W * (0.3 + 0.75 * e) * fi.height() / fi.width()
                    x0, y0 = W / 2 - fw / 2, H * 0.4 - fh / 2
                    fatias = 24
                    for k in range(fatias):
                        off = math.sin(t * 5 - k * 0.45) * fh * 0.025
                        c.drawImageRect(fi, skia.Rect.MakeXYWH(fi.width() * k / fatias, 0, fi.width() / fatias, fi.height()),
                                        skia.Rect.MakeXYWH(x0 + fw * k / fatias, y0 + off, fw / fatias + 1, fh), skia.SamplingOptions(skia.FilterMode.kLinear),
                                        skia.Paint(Alphaf=min(1.0, e * 1.3)))
                    c.drawRect(skia.Rect.MakeXYWH(x0, y0, fw, fh), skia.Paint(Color=skia.ColorSetARGB(int(220 * e), 38, 26, 20), AntiAlias=True,
                                                                             Style=skia.Paint.kStroke_Style, StrokeWidth=6))

        # legenda karaoke (1 a 3 palavras, palavra falada em amarelo)
        self._legenda(c, t, palavras)

        # vinheta
        c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=skia.GradientShader.MakeRadial(
            skia.Point(W / 2, H * 0.45), H * 0.75, [skia.ColorSetARGB(0, 0, 0, 0), skia.ColorSetARGB(150, 0, 0, 0)])))
        return sup.makeImageSnapshot()

    def _legenda(self, c, t, palavras):
        if not palavras:
            return
        # agrupa em blocos de ate 3 palavras / ~16 letras
        blocos, atual = [], []
        for w in palavras:
            if atual and (len(atual) >= 3 or sum(len(x["p"]) for x in atual) + len(w["p"]) > 16 or w["ini"] - atual[-1]["fim"] > 0.35):
                blocos.append(atual); atual = []
            atual.append(w)
        if atual:
            blocos.append(atual)
        bloco = next((b for b in blocos if b[0]["ini"] - 0.05 <= t <= b[-1]["fim"] + 0.15), None)
        if not bloco:
            bloco = next((b for b in reversed(blocos) if b[0]["ini"] <= t), None)
        if not bloco:
            return
        W, H = self.W, self.H
        f = self.f_leg
        esp = f.measureText(" ")
        larg = sum(f.measureText(w["p"].upper()) for w in bloco) + esp * (len(bloco) - 1)
        if larg > W * 0.86:  # quebra em 2 linhas
            meio = max(1, len(bloco) // 2)
            linhas = [bloco[:meio], bloco[meio:]]
        else:
            linhas = [bloco]
        y = H * 0.66
        for ln in linhas:
            lw = sum(f.measureText(w["p"].upper()) for w in ln) + esp * (len(ln) - 1)
            x = W / 2 - lw / 2
            for w in ln:
                cor = AMARELO if w["ini"] - 0.03 <= t <= w["fim"] + 0.05 else (255, 255, 255)
                x += texto_contorno(c, w["p"].upper(), x, y, f, cor=cor, contorno=12, alinhar="esq") + esp
            y += f.getSize() * 1.08


# ------------------------------------------------------------------ narracao com tempo de cada palavra
async def _falar(texto, voz, rate, pitch, mp3):
    import edge_tts
    com = edge_tts.Communicate(texto, voz, rate=f"{rate:+d}%", pitch=pitch, boundary="WordBoundary")
    pal = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                pal.append({"p": ch["text"], "ini": ch["offset"] / 1e7, "fim": (ch["offset"] + ch["duration"]) / 1e7})
    return pal


def narrar(texto, wav, chave_voz, ff):
    sys.path.insert(0, BASE)
    import gerar_video as g
    voz, pitch, rate = g.VOZES.get(chave_voz, g.VOZES["antonio_grave"])
    mp3 = wav + ".mp3"
    for _ in range(3):
        try:
            pal = asyncio.run(_falar(texto, voz, rate + 6, pitch, mp3))
            break
        except Exception as e:
            log(f"voz falhou ({str(e)[:50]}), tentando de novo"); time.sleep(3)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", mp3, "-af", "apad=pad_dur=0.25", "-ar", "24000", "-ac", "1", wav], check=True)
    os.remove(mp3)
    import wave
    with wave.open(wav) as w:
        dur = w.getnframes() / w.getframerate()
    return dur, pal


def _ligar_motor_vozes():
    """Garante o SupoClip (vozes do Gemini) no ar; tenta abrir o Docker Desktop se estiver desligado."""
    import supoclip
    if supoclip.status().get("ok"):
        return True
    exe = config.DOCKER_EXE
    if os.path.exists(exe):
        log("ligando o Docker (motor das vozes)...")
        subprocess.Popen([exe])
        for _ in range(48):
            time.sleep(5)
            if supoclip.status().get("ok"):
                return True
    return False


def _silencios(ff, wav):
    out = subprocess.run([ff, "-i", wav, "-af", "silencedetect=noise=-32dB:d=0.18", "-f", "null", "-"], capture_output=True, text=True).stderr
    ini = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    fim = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return [(a + b) / 2 for a, b in zip(ini, fim)]


def narrar_vozes_ia(cenas, pasta, voz, ff):
    """Narra com voz do Gemini/clonada (via SupoClip) em grupos de ate ~290 letras e corta por cena nas pausas.
    Devolve [(duracao, palavras)] por cena; tempo das palavras proporcional ao tamanho delas."""
    import wave, voz as vozes
    direto = voz.startswith("gemini:") or voz.startswith(("clone:", "vs:"))
    limite = 650 if voz.startswith("gemini:") else 290  # Gemini direto aceita trechos maiores (menos pedidos)
    grupos, atual = [], []
    for i, c in enumerate(cenas):
        if atual and sum(len(cenas[j]["fala"]) + 2 for j in atual) + len(c["fala"]) > limite:
            grupos.append(atual); atual = []
        atual.append(i)
    if atual:
        grupos.append(atual)
    res = [None] * len(cenas)
    for gi, grp in enumerate(grupos):
        texto = " ... ".join(cenas[j]["fala"].strip() for j in grp)  # pausa entre cenas
        audio = None
        if direto:  # voz direto no app (Gemini TTS pela sua chave / voz clonada local)
            try:
                tmp = os.path.join(pasta, f"grupo{gi}_bruto.wav")
                vozes.falar(texto, voz, tmp)
                audio = open(tmp, "rb").read(); os.remove(tmp)
            except Exception as e:
                log(f"voz direta falhou ({str(e)[:70]}) - tentando pelo SupoClip")
        if audio is None:
            import supoclip
            st, _, audio = supoclip.chamar("POST", "/tasks/studio/sample", {"voice": voz, "text": texto[:290]}, timeout=300)
            if st != 200:
                raise RuntimeError(f"voz {voz} falhou ({st}): {audio[:120]!r}")
        bruto = os.path.join(pasta, f"grupo{gi}.wav")
        open(bruto + ".src", "wb").write(audio)
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", bruto + ".src", "-ar", "24000", "-ac", "1", bruto], check=True)
        os.remove(bruto + ".src")
        with wave.open(bruto) as w:
            total, sr, frames = w.getnframes() / w.getframerate(), w.getframerate(), w.readframes(w.getnframes())
        # cortes: posicao proporcional ao texto, "grudada" na pausa mais proxima
        tam = [len(cenas[j]["fala"]) for j in grp]
        sil = _silencios(ff, bruto)
        cortes, acum = [0.0], 0
        for k in tam[:-1]:
            acum += k
            alvo = total * acum / sum(tam)
            validos = [x for x in sil if cortes[-1] + 0.5 < x < total - 0.4]  # pausa real, depois do corte anterior
            perto = min(validos, key=lambda x: abs(x - alvo)) if validos else alvo
            cortes.append(perto if abs(perto - alvo) < 1.8 else max(alvo, cortes[-1] + 0.5))
        cortes.append(total)
        for n, j in enumerate(grp):
            a, b = cortes[n], cortes[n + 1]
            arq = os.path.join(pasta, f"voz{j}.wav")
            with wave.open(arq, "wb") as out:
                out.setnchannels(1); out.setsampwidth(2); out.setframerate(sr)
                out.writeframes(frames[int(a * sr) * 2:int(b * sr) * 2])
            d = b - a
            ps = cenas[j]["fala"].split()
            peso = [len(p) + 2 for p in ps]
            t, pal = 0.12, []
            for p, w_ in zip(ps, peso):
                dt = (d - 0.3) * w_ / sum(peso)
                pal.append({"p": p, "ini": t, "fim": t + dt}); t += dt
            res[j] = (d, pal)
        os.remove(bruto)
    return res


# ------------------------------------------------------------------ roteiro (Gemini) -> JSON de cenas
PROMPT = """Voce e roteirista de um canal brasileiro de SHORTS de historia com MAPAS ANIMADOS.
Canal: "{canal}". Tom: narrador que conta a historia com energia e clareza, frases MUITO curtas, ritmo rapido.
TEMA: {tema}
Regras:
- {seg} segundos (~{pal} palavras). Comece com uma PERGUNTA ou fato chocante (gancho em 3s). Termine com uma frase de impacto.
- Se passar de 3 minutos: estrutura de documentario curto - gancho, contexto, 3 a 5 viradas com mini-ganchos a cada ~40s,
  climax e conclusao; peca ao publico para comentar no final.
- FATOS CORRETOS. Se houver versoes diferentes, diga "segundo os relatos" - nunca invente datas, numeros ou citacoes.
- RITMO DE SHORT (retencao): divida em {nc} a {nc2} cenas de UMA frase curta cada (~3 a 4 segundos falados).
  TODA cena traz algo visual NOVO (camera em outro lugar, personagem entrando, icone, caixa, bandeira, rota...).
  No meio do video, coloque uma VIRADA ("so que...", "mas ninguem esperava...") para segurar quem ia sair.
- FINAL COMPLETO (obrigatorio): as 2 ultimas cenas FECHAM a historia - a conclusao/resposta clara e uma frase de impacto,
  terminando com uma pergunta ao publico para os comentarios. NUNCA termine com frase incompleta, dois-pontos ou reticencias.
- Cada "fala" tem NO MAXIMO 12 palavras (cenas curtas = retencao alta).
- Mapa: camera com lon/lat REAIS do centro e "graus" = largura visivel em graus de longitude
  (continente ~60, pais ~16, estado/regiao ~8; NUNCA menos que 6 - para uma cidade use 7 e marque com "rotulos").
- TODA cena precisa de pelo menos 1 elemento visual NOVO alem do mapa (destaque, fronteira, rota, rotulo, icone,
  caixa, documento ou retrato). Varie: nao repita o mesmo tipo em cenas seguidas. Use icones (emoji) generosamente:
  soldado 🪖, explosao 💥, bandeira, navio 🚢, aviao ✈️, cruz ✝️, carta ✉️, X ❌, interrogacao ❓, fogo 🔥.
- "destaques": regioes (paises ou estados, nome em portugues) a pintar com a bandeira ("bandeira") ou cor ("cor": [r,g,b]).
  Para epocas antigas use a bandeira DA EPOCA: "bandeira_arquivo": nome EXATO do arquivo no Wikimedia Commons
  (ex. "Flag of Empire of Brazil (1870–1889).svg", "Flag of Portugal (1830).svg", "Flag of Germany (1935–1945).svg" NAO - prefira
  a de 1867-1918 ou nenhuma). Se nao tiver certeza do nome do arquivo, nao use (fica a bandeira atual).
  Os destaques continuam nas cenas seguintes; para mudar, mande a lista nova completa. [] limpa.
- "fronteiras": regioes cuja borda deve ser desenhada brilhando nesta cena.
- "rota": linha animada (ex. viagem) {{"pontos": [[lon,lat],...], "emoji": "🚢"}} (opcional).
- "rotulos": [{{"texto": "Montese", "lon": 10.94, "lat": 44.27}}] (opcional). "icones": [{{"emoji": "💣", "lon": .., "lat": ..}}] (opcional).
- "caixa": {{"titulo": "...", "valor": "25 MIL"}} para numeros (opcional). "documento": {{"titulo": "...", "texto": "citacao curta REAL", "grifo": "trecho"}} (opcional). SO use "documento" para uma frase
  que voce tem CERTEZA que existe em fonte historica (decreto, carta, inscricao). Nunca invente falas de soldados ou lemas.
- "retrato": {{"nome": "Nome", "busca": "termo para achar pintura/foto antiga no Wikimedia Commons"}} (opcional).
- "personagens": bonequinhos animados que aparecem na cena (0 a 3; use em MUITAS cenas, sao a alma do video):
  [{{"tipo": "{tipos}", "nome": "Geraldo",
     "pose": "parado|aponta|bracos_cima|comemora|triste|anda", "expressao": "normal|preocupado|bravo|feliz", "lado": "esq|centro|dir",
     "pele": "clara|morena|parda|negra (fiel a pessoa historica)"}}]
  Mesmo personagem = mesmo tipo e nome em todas as cenas. Pose e expressao combinam com a fala.
  Personagem TIPICO do lugar quando fizer sentido (gaucho no RS, cangaceiro no sertao, cowboy no Texas, samurai no Japao...).
  "insignia": "Japão" coloca a bandeira (de qualquer pais/estado) no braco do personagem - use em soldados e atletas.
  Para bandeira DA EPOCA no braco use "insignia": "arquivo:Flag of the Soviet Union" (URSS), "arquivo:Flag of the Empire of Japan" etc.
  Militares brasileiros ATUAIS: exercito_br, marinha_br, fuzileiro_naval, aeronautica_br, piloto_fab, general, policia_militar.
  Lideres da 2a Guerra: lider_alemao (Hitler), lider_sovietico (Stalin), lider_britanico (Churchill), lider_italiano (Mussolini),
  lider_americano (Roosevelt), lider_japones (Hirohito) - SEMPRE com "nome", tom critico e factual, NUNCA glorificar; nao existem simbolos nazistas.
  Povos e culturas (respeito, sem estereotipo): indigena (Brasil), nativo_americano, chefe_nativo, guerreiro_africano, rainha_africana,
  rei_africano, inca, asteca, inuit, mongol, samurai...
  Estrangeiros (ja vem com a bandeira certa no braco): soldado_argentino, soldado_paraguaio, soldado_uruguaio, marine_eua, marinha_eua,
  soldado_uniao/soldado_confederado (Guerra Civil dos EUA), alemao_ww1, japones_ww2, italiano_ww2, britanico_ww2, frances_ww2,
  chines_soldado, soldado_russo, sovietico, conquistador (Espanha), holandes_1630 (Brasil holandes), otomano, revolucionario_mexicano.
  Para PERSONIFICAR um pais/estado (ex. "Bahia x Sergipe", "Brasil x Alemanha") use tipo "nacao" com "roupa": "bandeira:<nome>".
  Poses tambem: "assustado". Expressoes tambem: "assustado".
- "tropas": [{{"tipo": "qualquer soldado/guerreiro da lista de tipos", "qtd": 6, "lon": .., "lat": ..}}] grupos de soldados no mapa (opcional).
- "fumaca": [{{"lon": .., "lat": ..}}] nuvem de batalha animada (opcional). "bandeiras_mastro": [{{"regiao": "Brasil", "lon": .., "lat": ..}}] (opcional; aceita "bandeira_arquivo").
- CENARIO DE ESPACO (historias espaciais, corrida espacial, astronomia): "cenario": "espaco" troca o mapa por ceu estrelado;
  "astros": [{{"tipo": "sol|lua|terra|marte|jupiter|saturno", "x": 0.5, "y": 0.3, "tam": 0.2}}] (x,y = posicao na tela 0-1, tam = raio/largura);
  nos veiculos use "x","y" (tela 0-1) e "ate": [x, y] no lugar de lon/lat. Personagens funcionam igual.
- "veiculos": [{{"tipo": "{objetos}", "lon": .., "lat": .., "ate": [lon, lat]}}]
  veiculos/criaturas animados no mapa; "ate" faz atravessar durante a cena (opcional). Dragao SO em lendas/mitos.
- "bandeira_tela": "Brasil" (ou {{"regiao": "Brasil", "bandeira_arquivo": "..."}}) bandeira GIGANTE tremulando em tela cheia por ~2s:
  use na 1a cena ao apresentar o pais/tema ou em viradas fortes (no maximo 2 vezes por video).
- "ano": ano mostrado no canto (opcional). "escuro": true em momentos dramaticos.
- "selo": 2 a 4 palavras do tema (ex: "BRASIL x ALEMANHA").
Responda SOMENTE JSON:
{{"titulo": "pergunta curta e curiosa, max 70 caracteres", "descricao": "3 linhas + 5 hashtags", "selo": "",
  "thumb": {{"texto": "3 a 5 palavras", "destaque": "1 palavra"}},
  "fontes": ["fontes historicas consultadas"],
  "cenas": [{{"fala": "", "ano": 1944, "camera": {{"lon": 0, "lat": 0, "graus": 15}}, "destaques": [{{"regiao": "", "tipo": "bandeira"}}],
             "fronteiras": [], "rota": null, "rotulos": [], "icones": [], "caixa": null, "documento": null, "retrato": null, "personagens": [], "tropas": [], "fumaca": [], "bandeiras_mastro": [], "veiculos": [], "bandeira_tela": null, "cenario": "mapa", "astros": [], "escuro": false}}]}}"""


def roteiro(cfg):
    sys.path.insert(0, BASE)
    import gerar_video as g
    seg = int(cfg.get("duracao") or 60)
    import avatares, objetos
    return g.pedir_json(PROMPT.format(tipos="|".join(avatares.FIGURINOS), objetos="|".join(objetos.DESENHOS), canal=cfg.get("canal") or "Bravura Esquecida", tema=cfg.get("tema") or "um episodio pouco conhecido da historia do Brasil",
                                      seg=seg, pal=int(seg * 2.6), nc=max(8, seg // 4), nc2=max(12, seg // 3)), "roteiro_mapa")


def com_personagens(rot):
    """Acrescenta bonequinhos a um roteiro JA PRONTO, sem mudar falas, mapa ou ordem (1 chamada do Gemini)."""
    sys.path.insert(0, BASE)
    import gerar_video as g
    falas = [{"cena": i, "fala": c.get("fala", "")} for i, c in enumerate(rot["cenas"])]
    import avatares
    tipos = "|".join(avatares.FIGURINOS)
    r = g.pedir_json(f"""Este e o roteiro de um Short de historia com mapa animado: "{rot['titulo']}".
Cenas: {json.dumps(falas, ensure_ascii=False)}
Para CADA cena, diga quais bonequinhos animados aparecem (0 a 3), sem mudar nada do texto.
tipos: {tipos};
poses: parado|aponta|bracos_cima|comemora|triste|anda; expressoes: normal|preocupado|bravo|feliz; lado: esq|centro|dir;
pele: clara|morena|parda|negra (fiel a pessoa historica). Mesmo personagem = mesmo tipo, nome e pele em todas as cenas.
Use personagens na maioria das cenas; pose e expressao combinando com a fala.
Responda SOMENTE JSON: {{"cenas": [{{"cena": 0, "personagens": [{{"tipo": "", "nome": "", "pose": "", "expressao": "", "lado": "", "pele": ""}}]}}]}}""", "personagens_mapa")
    for item in r.get("cenas", []):
        i = item.get("cena")
        if isinstance(i, int) and 0 <= i < len(rot["cenas"]):
            rot["cenas"][i]["personagens"] = item.get("personagens") or []
    return rot


def _som(tipo, sr=24000):
    """Efeitos sonoros sinteticos (livres): whoosh = ruido filtrado com varredura; pop = bolha curta."""
    if tipo == "whoosh":
        n = int(sr * 0.45); t = np.arange(n) / sr
        ruido = np.random.default_rng(3).standard_normal(n)
        env = np.sin(np.pi * t / t[-1]) ** 2
        # filtro passa-banda que sobe (varredura) aproximado por media movel variavel
        out = np.zeros(n); acc = 0.0
        for i in range(n):
            a = 0.02 + 0.25 * (i / n)
            acc += a * (ruido[i] - acc); out[i] = acc
        return (out / (np.abs(out).max() + 1e-6)) * env * 0.55
    n = int(sr * 0.12); t = np.arange(n) / sr
    f = 900 - 500 * t / t[-1]
    return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 38) * 0.6


def _mixar_efeitos(wav_narracao, eventos):
    """Soma whoosh/pop na narracao (volume baixo, nunca encobre a voz)."""
    import wave
    with wave.open(wav_narracao) as w:
        sr, nch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        voz = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if nch != 1 or sw != 2:
        return
    sons = {k: _som(k, sr) for k in ("whoosh", "pop")}
    pista = np.zeros_like(voz)
    for tipo, quando in eventos:
        i = int(max(0.0, quando - (0.18 if tipo == "whoosh" else 0)) * sr)
        s_ = sons[tipo][: max(0, len(pista) - i)]
        pista[i:i + len(s_)] += s_ * (0.22 if tipo == "whoosh" else 0.16)
    mix = np.clip(voz + pista, -1, 1)
    with wave.open(wav_narracao, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ montagem completa
def gerar(cfg, rot=None, pasta=None):
    sys.path.insert(0, BASE)
    import gerar_video as g, datetime
    ff = g.FFMPEG
    vertical = (cfg.get("tela") or "9:16") != "16:9"
    W, H = (1080, 1920) if vertical else (1920, 1080)
    print("1/4 Roteiro do mapa...", flush=True)
    rot = rot or roteiro(cfg)
    nome = re.sub(r"[^\w\- ]", "", rot["titulo"])[:40].strip().replace(" ", "_")
    pasta = pasta or os.path.join(BASE, "Para_Aprovar", f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{nome}")
    os.makedirs(os.path.join(pasta, "imagens"), exist_ok=True)
    cenas = rot["cenas"]
    print(f"   {rot['titulo']} | {len(cenas)} cenas", flush=True)

    print("2/4 Narracao...", flush=True)
    voz = cfg.get("voz") or "gemini:Charon"
    duracoes, falas = [], []
    pronto = None
    if ":" in voz:  # voz do Gemini (direto pela chave) ou clonada (servico local)
        try:
            if voz.startswith(("clone:", "vs:")):
                import voz as vozes
                if not vozes.vozes_clonadas():
                    _ligar_motor_vozes()
            pronto = narrar_vozes_ia(cenas, pasta, voz, ff)
        except Exception as e:
            log(f"voz {voz} indisponivel ({str(e)[:80]}) - usando Antonio"); voz = "antonio_grave"
    for i, c in enumerate(cenas):
        if pronto:
            d, pal = pronto[i]; duracoes.append(d); falas.append(pal); continue
        d, pal = narrar(c["fala"], os.path.join(pasta, f"voz{i}.wav"), voz, ff)
        if not pal:  # sem tempo por palavra: distribui igualmente
            ps = c["fala"].split(); pal = [{"p": p, "ini": d * k / len(ps), "fim": d * (k + 1) / len(ps)} for k, p in enumerate(ps)]
        duracoes.append(d); falas.append(pal)
    import wave
    with wave.open(os.path.join(pasta, "narracao.wav"), "wb") as out:
        for i in range(len(cenas)):
            with wave.open(os.path.join(pasta, f"voz{i}.wav")) as w:
                if i == 0: out.setparams(w.getparams())
                out.writeframes(w.readframes(w.getnframes()))
    total = sum(duracoes)

    print("3/4 Desenhando o mapa...", flush=True)
    rd = Renderizador(rot, W, H)
    fps = 30
    proc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(fps),
                             "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", str(max(1, (os.cpu_count() or 2) - 1)),
                             "-pix_fmt", "yuv420p", "mapa.mp4"],
                            cwd=pasta, stdin=subprocess.PIPE)
    cam_ant, destaques = None, []
    eventos = []
    t0 = time.time()
    for i, (c, d, pal) in enumerate(zip(cenas, duracoes, falas)):
        cm = c.get("camera") or {}
        alvo = (float(cm.get("lon", cam_ant[0] if cam_ant else -50)), float(cm.get("lat", cam_ant[1] if cam_ant else -14)),
                float(cm.get("graus", cam_ant[2] if cam_ant else 40)))
        ini = cam_ant or (alvo[0], alvo[1], alvo[2] * 1.6)
        if c.get("ano"):
            rot["_ano_atual"] = c["ano"]
        if c.get("destaques") is not None:
            novos = [dict(x) for x in c["destaques"] if isinstance(x, dict)]
            velhos = {(_norm(x.get("regiao")), x.get("tipo")) for x in destaques}
            for x in novos:
                x["_velho"] = (_norm(x.get("regiao")), x.get("tipo")) in velhos
            destaques = novos
        n = max(1, int(round(d * fps)))
        inicio_cena = sum(duracoes[:i])
        eventos.append(("whoosh", inicio_cena))
        npers = len([p for p in (c.get("personagens") or []) if isinstance(p, dict)][:4])
        for k in range(npers):
            eventos.append(("pop", inicio_cena + _quando(k, npers, d)))
        for chave in ("caixa", "documento", "retrato", "bandeira_tela"):
            if c.get(chave):
                eventos.append(("pop", inicio_cena + 0.4))
        for k in range(n):
            t = k / fps
            e = _ease(t / min(1.0, d * 0.5))
            zoom_lento = 1 - 0.04 * (t / d)
            if d > 2.4:  # "punch-in": zoom rapido no meio da cena (sensacao de corte)
                zoom_lento *= 1 - 0.07 * _ease((t - d * 0.5) / 0.22)
            cam = Camera(ini[0] + (alvo[0] - ini[0]) * e, ini[1] + (alvo[1] - ini[1]) * e,
                         (ini[2] + (alvo[2] - ini[2]) * e) * zoom_lento, W, H)
            img = rd.quadro(c, t, d, cam, destaques, pal)
            proc.stdin.write(img.tobytes())
        for x in destaques:
            x["_velho"] = True
        cam_ant = (alvo[0], alvo[1], alvo[2] * (1 - 0.04))
        if i == len(cenas) // 3:  # quadro para a miniatura
            img.save(os.path.join(pasta, "imagens", "thumb.png"))
        print(f"   cena {i + 1}/{len(cenas)} ok ({time.time() - t0:.0f}s)", flush=True)
        print(f"PROGRESSO {i + 1}/{len(cenas)} animando", flush=True)
    proc.stdin.close(); proc.wait()

    print("4/4 Montagem final (voz + efeitos + trilha)...", flush=True)
    try:
        _mixar_efeitos(os.path.join(pasta, "narracao.wav"), eventos)
    except Exception as e:
        log(f"efeitos sonoros pulados: {str(e)[:80]}")
    musica, vol = g.faixa_musica() if cfg.get("musica", True) else (None, 0)
    if musica:
        filtro = (f"[2:a]volume={vol},afade=t=in:d=2,afade=t=out:st={max(0, total - 3):.2f}:d=3[m];"
                  f"[m][1:a]sidechaincompress=threshold=0.04:ratio=6:release=400[md];[1:a][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        args = ["-i", "mapa.mp4", "-i", "narracao.wav", *musica, "-t", f"{total:.2f}", "-filter_complex", filtro, "-map", "0:v", "-map", "[a]"]
    else:
        args = ["-i", "mapa.mp4", "-i", "narracao.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-map", "0:v", "-map", "1:a", "-shortest"]
    subprocess.run([ff, "-y", "-loglevel", "error", *args, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "video.mp4"], cwd=pasta, check=True)
    for f in os.listdir(pasta):
        if f.startswith("voz") or f in ("mapa.mp4", "narracao.wav"):
            os.remove(os.path.join(pasta, f))

    creditos = "\n\nMapas: Natural Earth (dominio publico). Icones: Twemoji (CC-BY 4.0). Retratos: Wikimedia Commons (dominio publico)."
    if rot.get("fontes"):
        creditos += "\nFontes: " + "; ".join(rot["fontes"][:6])
    rot.update({"formato": "short" if vertical else "longo", "tela": "9:16" if vertical else "16:9", "tema_canal": cfg.get("canal") or "Mapas e história",
                "duracoes": [round(x, 2) for x in duracoes], "duracao_s": round(total, 1), "config": cfg, "tipo": "mapa",
                "descricao": (rot.get("descricao") or "") + creditos, "custo_usd": 0,
                "gerado_em": datetime.datetime.now().isoformat(timespec="seconds")})
    for c in cenas:
        c.setdefault("narracao", c.get("fala", ""))
    rot.pop("_ano_atual", None)
    json.dump(rot, open(os.path.join(pasta, "roteiro.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    try:
        g.miniatura(rot, pasta, W, H)
    except Exception as e:
        log(f"miniatura falhou: {e}")
    print(f"\nPronto! {os.path.abspath(pasta)}\\video.mp4 ({total:.0f}s)", flush=True)
    return pasta


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--config":
        gerar(json.load(open(a[1], encoding="utf-8")))

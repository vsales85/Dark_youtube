"""Gera capa (2560x1440) e icone (800x800) do canal "O Que a Historia Escondeu" com os recursos do proprio app."""
import math, os, sys
import skia
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapa_animado as m, avatares

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marca_canal")
os.makedirs(SAIDA, exist_ok=True)
OURO, OSSO, TINTA = (226, 186, 92), (240, 232, 214), (38, 26, 20)


def fundo_mapa(W, H, lon, lat, graus):
    cam = m.Camera(lon, lat, graus, W, H)
    img = cam.fundo().convert("RGBA")
    return skia.Image.frombytes(img.tobytes(), skia.ISize(W, H), skia.kRGBA_8888_ColorType), cam


def salvar(sup, nome):
    a = sup.makeImageSnapshot().toarray()
    Image.fromarray(a[..., [2, 1, 0]]).save(os.path.join(SAIDA, nome), quality=95)


def grade(c, cam, W, H, passo=10):
    p = skia.Paint(Color=skia.ColorSetARGB(38, 226, 186, 92), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=1.5)
    for lon in range(-180, 181, passo):
        x, _ = cam.xy(lon, 0); c.drawLine(x, 0, x, H, p)
    for lat in range(-80, 81, passo):
        _, y = cam.xy(0, lat); c.drawLine(0, y, W, y, p)


def buraco_fechadura(c, cx, cy, s, cor):
    p = skia.Path()
    p.addCircle(cx, cy - s * 0.18, s * 0.26)
    t = skia.Path(); t.moveTo(cx - s * 0.13, cy - s * 0.05); t.lineTo(cx + s * 0.13, cy - s * 0.05)
    t.lineTo(cx + s * 0.22, cy + s * 0.48); t.lineTo(cx - s * 0.22, cy + s * 0.48); t.close()
    p = skia.Op(p, t, skia.PathOp.kUnion_PathOp)
    c.drawPath(p, skia.Paint(Color=skia.ColorSetRGB(*cor), AntiAlias=True))


def capa():
    W, H = 2560, 1440
    sup = skia.Surface(W, H); c = sup.getCanvas()
    img, cam = fundo_mapa(W, H, 15, 18, 150)
    c.drawImage(img, 0, 0)
    grade(c, cam, W, H, 15)
    # rotas pontilhadas vermelhas (viagens/guerras) entre lugares historicos
    rotas = [[(-43, -22), (-20, 5), (5, 38), (12, 42)], [(12, 42), (28, 37), (31, 30)], [(-4, 12), (10, 16), (31, 30)], [(116, 40), (70, 45), (35, 38)]]
    for r in rotas:
        p = skia.Path(); x, y = cam.xy(*r[0]); p.moveTo(x, y)
        for lo, la in r[1:]:
            x, y = cam.xy(lo, la); p.lineTo(x, y)
        c.drawPath(p, skia.Paint(Color=skia.ColorSetARGB(200, 220, 50, 50), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=5,
                                 PathEffect=skia.DashPathEffect.Make([18, 12], 0)))
        for lo, la in (r[0], r[-1]):
            x, y = cam.xy(lo, la); c.drawCircle(x, y, 10, skia.Paint(Color=skia.ColorSetRGB(220, 50, 50), AntiAlias=True))
            c.drawCircle(x, y, 10, skia.Paint(Color=skia.ColorWHITE, AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=3))
    # escurece o centro para o texto + vinheta
    c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=skia.GradientShader.MakeRadial(
        skia.Point(W / 2, H / 2), W * 0.42, [skia.ColorSetARGB(200, 4, 10, 14), skia.ColorSetARGB(40, 4, 10, 14)])))
    c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=skia.GradientShader.MakeRadial(
        skia.Point(W / 2, H / 2), W * 0.75, [skia.ColorSetARGB(0, 0, 0, 0), skia.ColorSetARGB(170, 0, 0, 0)])))
    # area segura (celular): 1546 x 423 no centro -> todo o texto aqui dentro
    f1, f2 = m._tf(m.FONTE_FORTE, 118), m._tf(m.FONTE_FORTE, 196)
    f3 = m._tf(m.FONTE_ITALICA, 50)
    m.texto_contorno(c, "O QUE A HISTÓRIA", W / 2, H / 2 - 70, f1, cor=OSSO, contorno=10)
    m.texto_contorno(c, "ESCONDEU", W / 2, H / 2 + 120, f2, cor=OURO, contorno=12)
    m.texto_contorno(c, "Impérios perdidos  ·  Guerras  ·  Mistérios  ·  Curiosidades", W / 2, H / 2 + 190, f3, cor=OSSO, contorno=4)
    # linhas douradas decorativas
    pl = skia.Paint(Color=skia.ColorSetRGB(*OURO), AntiAlias=True, StrokeWidth=4)
    for lado in (-1, 1):
        x0 = W / 2 + lado * 360
        c.drawLine(x0, H / 2 - 175, x0 + lado * 260, H / 2 - 175, pl)
        c.drawCircle(x0 + lado * 275, H / 2 - 175, 7, skia.Paint(Color=skia.ColorSetRGB(*OURO), AntiAlias=True))
    buraco_fechadura(c, W / 2, H / 2 - 230, 70, OURO)
    # bonecos nas laterais (aparecem no computador/TV)
    avatares.desenhar(c, {"tipo": "pracinha", "pose": "aponta", "expressao": "bravo", "pele": "morena"}, W / 2 - 980, H / 2 + 330, 470, 0.5, semente=4)
    avatares.desenhar(c, {"tipo": "imperador", "pose": "assustado", "olha": "esq"}, W / 2 + 980, H / 2 + 330, 470, 0.5, semente=2)
    salvar(sup, "capa_2560x1440.jpg")


def icone():
    S = 800
    sup = skia.Surface(S, S); c = sup.getCanvas()
    c.clear(skia.ColorSetRGB(8, 18, 24))
    img, cam = fundo_mapa(S, S, -40, -5, 70)
    circ = skia.Path(); circ.addCircle(S / 2, S / 2, S * 0.47)
    c.save(); c.clipPath(circ, doAntiAlias=True); c.drawImage(img, 0, 0)
    c.drawRect(skia.Rect.MakeWH(S, S), skia.Paint(Shader=skia.GradientShader.MakeRadial(
        skia.Point(S / 2, S / 2), S * 0.5, [skia.ColorSetARGB(120, 4, 10, 14), skia.ColorSetARGB(230, 4, 10, 14)])))
    grade(c, cam, S, S, 10)
    c.restore()
    for r_, w_ in ((0.47, 16), (0.43, 5)):
        c.drawCircle(S / 2, S / 2, S * r_, skia.Paint(Color=skia.ColorSetRGB(*OURO), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=w_))
    # simbolo: fechadura dourada (o que foi "escondido") com um alfinete vermelho de mapa no centro
    buraco_fechadura(c, S / 2, S / 2 + 10, 330, OURO)
    c.drawCircle(S / 2, S / 2 - 50, 34, skia.Paint(Color=skia.ColorSetRGB(210, 44, 44), AntiAlias=True))
    c.drawCircle(S / 2, S / 2 - 50, 34, skia.Paint(Color=skia.ColorSetRGB(*TINTA), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=6))
    c.drawCircle(S / 2 - 10, S / 2 - 60, 9, skia.Paint(Color=skia.ColorSetARGB(200, 255, 255, 255), AntiAlias=True))
    salvar(sup, "icone_800x800.png")


if __name__ == "__main__":
    capa(); icone(); print("ok", SAIDA)

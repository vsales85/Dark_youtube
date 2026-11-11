"""Veiculos, criaturas e objetos animados no estilo do canal (contorno marrom, sombra suave, cores chapadas).

objeto = {"tipo": "tanque", "lon": 11, "lat": 44, "ate": [11.5, 44.3] (opcional: atravessa durante a cena), "olha": "esq|dir"}
Tipos: tanque, aviao, navio_guerra, caravela, canhao, cavalo, dragao, trem
"""
import math
import skia
from avatares import TINTA, _cor, _fill, _linha, _forma, _rrect_path


def _roda(c, x, y, r, t, lw, cor=(60, 56, 52)):
    c.drawCircle(x, y, r, _fill(cor)); c.drawCircle(x, y, r, _linha(lw))
    for k in range(3):
        a = t * 8 + k * math.pi / 3
        c.drawLine(x - math.cos(a) * r * 0.7, y - math.sin(a) * r * 0.7, x + math.cos(a) * r * 0.7, y + math.sin(a) * r * 0.7, _linha(lw * 0.6))


def _fumaca(c, x, y, s, t, n=4):
    for k in range(n):
        f = (t * 0.8 + k / n) % 1.0
        c.drawCircle(x - f * s * 0.6, y - f * s * 1.2, s * (0.15 + 0.25 * f), _fill((236, 234, 228), int(220 * (1 - f))))


def tanque(c, s, t, lw):
    corpo = (98, 108, 66)
    # esteira
    est = _rrect_path(-s * 0.55, -s * 0.22, s * 1.1, s * 0.24, s * 0.12)
    _forma(c, est, (70, 66, 60), lw, sombra=False)
    for k in range(6):
        _roda(c, -s * 0.42 + k * s * 0.17, -s * 0.1, s * 0.06, t, lw * 0.6, (110, 106, 98))
    # casco e torre
    casco = skia.Path(); casco.moveTo(-s * 0.5, -s * 0.22); casco.lineTo(-s * 0.4, -s * 0.42); casco.lineTo(s * 0.45, -s * 0.42); casco.lineTo(s * 0.55, -s * 0.22); casco.close()
    _forma(c, casco, corpo, lw)
    recuo = max(0.0, 1 - ((t * 0.7) % 1.0) * 6) * s * 0.06       # tranco do disparo
    cano = _rrect_path(s * 0.05 - recuo, -s * 0.6, s * 0.62, s * 0.07, s * 0.03)
    _forma(c, cano, corpo, lw, sombra=False)
    torre = skia.Path(); torre.addArc(skia.Rect.MakeXYWH(-s * 0.28, -s * 0.72, s * 0.56, s * 0.6), 180, 180); torre.close()
    _forma(c, torre, corpo, lw)
    c.drawCircle(-s * 0.05, -s * 0.52, s * 0.05, _fill((226, 186, 70)))
    f = (t * 0.7) % 1.0
    if f < 0.35:  # clarao + fumaca na boca do canhao
        bx = s * 0.7 - recuo
        c.drawCircle(bx, -s * 0.565, s * 0.08 * (1 - f / 0.35) + s * 0.02, _fill((255, 214, 60)))
        c.drawCircle(bx + f * s * 0.5, -s * 0.6 - f * s * 0.2, s * 0.12 * (0.5 + f), _fill((238, 236, 230), int(230 * (1 - f / 0.35))))


def aviao(c, s, t, lw):
    cor = (176, 64, 52)
    asa = _rrect_path(-s * 0.12, -s * 0.5, s * 0.26, s * 0.75, s * 0.08)  # asa (vista de lado: faixa vertical)
    _forma(c, _rrect_path(-s * 0.45, -s * 0.34, s * 0.9, s * 0.2, s * 0.1), cor, lw)  # fuselagem
    _forma(c, _rrect_path(-s * 0.18, -s * 0.46, s * 0.36, s * 0.07, s * 0.035), (220, 220, 214), lw, sombra=False)  # asa superior
    _forma(c, _rrect_path(-s * 0.2, -s * 0.2, s * 0.4, s * 0.07, s * 0.035), (220, 220, 214), lw, sombra=False)    # asa inferior
    cauda = skia.Path(); cauda.moveTo(-s * 0.42, -s * 0.3); cauda.lineTo(-s * 0.55, -s * 0.5); cauda.lineTo(-s * 0.35, -s * 0.33); cauda.close()
    _forma(c, cauda, cor, lw, sombra=False)
    c.drawCircle(s * 0.0, -s * 0.36, s * 0.06, _fill((140, 200, 230)))
    # helice girando (elipse que muda de largura)
    hw = abs(math.sin(t * 40)) * s * 0.05 + s * 0.01
    c.drawOval(skia.Rect.MakeXYWH(s * 0.47 - hw, -s * 0.46, hw * 2, s * 0.26), _fill((60, 56, 52), 200))
    c.drawCircle(s * 0.47, -s * 0.33, s * 0.035, _fill((60, 56, 52)))


def _ondas(c, s, t, lw):
    for k in range(5):
        x = -s * 0.7 + k * s * 0.35 + math.sin(t * 2 + k) * s * 0.03
        p = skia.Path(); p.moveTo(x - s * 0.15, s * 0.02); p.quadTo(x, -s * 0.06, x + s * 0.15, s * 0.02)
        c.drawPath(p, _linha(lw * 0.8, _cor((236, 244, 250))))


def navio_guerra(c, s, t, lw):
    ang = math.sin(t * 1.6) * 3
    c.save(); c.rotate(ang)
    casco = skia.Path(); casco.moveTo(-s * 0.65, -s * 0.18); casco.lineTo(s * 0.72, -s * 0.18); casco.lineTo(s * 0.5, s * 0.02); casco.lineTo(-s * 0.55, s * 0.02); casco.close()
    _forma(c, casco, (110, 116, 124), lw)
    _forma(c, _rrect_path(-s * 0.25, -s * 0.42, s * 0.5, s * 0.25, s * 0.03), (128, 134, 142), lw)
    _forma(c, _rrect_path(-s * 0.05, -s * 0.62, s * 0.12, s * 0.22, s * 0.02), (90, 94, 100), lw, sombra=False)
    for dx in (-s * 0.45, s * 0.35):
        _forma(c, _rrect_path(dx, -s * 0.3, s * 0.25, s * 0.05, s * 0.02), (90, 94, 100), lw * 0.7, sombra=False)
    _fumaca(c, s * 0.01, -s * 0.66, s * 0.5, t)
    c.restore(); _ondas(c, s, t, lw)


def caravela(c, s, t, lw):
    ang = math.sin(t * 1.4) * 4
    c.save(); c.rotate(ang)
    casco = skia.Path(); casco.moveTo(-s * 0.6, -s * 0.28); casco.lineTo(s * 0.62, -s * 0.22); casco.quadTo(s * 0.4, s * 0.04, -s * 0.45, s * 0.02); casco.close()
    _forma(c, casco, (132, 88, 52), lw)
    c.drawLine(-s * 0.05, -s * 0.25, -s * 0.05, -s * 1.05, _linha(lw * 1.4))
    c.drawLine(s * 0.35, -s * 0.23, s * 0.35, -s * 0.8, _linha(lw * 1.2))
    infla = math.sin(t * 2.2) * s * 0.03
    for mx, h_ in ((-s * 0.05, s * 0.6), (s * 0.35, s * 0.42)):
        vela = skia.Path(); vela.moveTo(mx - s * 0.2, -s * 0.3 - h_); vela.quadTo(mx + s * 0.12 + infla, -s * 0.3 - h_ / 2, mx - s * 0.2, -s * 0.32)
        vela.lineTo(mx + s * 0.2, -s * 0.32); vela.quadTo(mx + s * 0.4 + infla, -s * 0.3 - h_ / 2, mx + s * 0.2, -s * 0.3 - h_); vela.close()
        _forma(c, vela, (244, 238, 220), lw, sombra=False)
        c.drawLine(mx, -s * 0.36 - h_ * 0.7, mx, -s * 0.36 - h_ * 0.3, _linha(lw * 2, _cor((196, 36, 40))))  # cruz vermelha na vela
        c.drawLine(mx - s * 0.08, -s * 0.36 - h_ * 0.5, mx + s * 0.08, -s * 0.36 - h_ * 0.5, _linha(lw * 2, _cor((196, 36, 40))))
    c.restore(); _ondas(c, s, t, lw)


def canhao(c, s, t, lw):
    recuo = max(0.0, 1 - ((t * 0.6) % 1.0) * 5) * s * 0.08
    c.save(); c.translate(-recuo, 0); c.rotate(-14)
    _forma(c, _rrect_path(-s * 0.3, -s * 0.36, s * 0.75, s * 0.17, s * 0.08), (54, 54, 58), lw)
    c.restore()
    _roda(c, -s * 0.05 - recuo, -s * 0.12, s * 0.15, 0, lw, (132, 92, 54))
    f = (t * 0.6) % 1.0
    if f < 0.3:
        _fumaca(c, s * 0.5, -s * 0.5, s * 0.6, f * 3, n=5)


def cavalo(c, s, t, lw):
    """Cavalo no estilo do canal: corpo arredondado, cabeca grande, olho expressivo, crina e rabo animados."""
    galope = math.sin(t * 9)
    cor, escuro = (150, 98, 58), (92, 58, 34)
    c.save(); c.translate(0, -abs(galope) * s * 0.035)
    # pernas (4), com casco escuro
    for k, fase in enumerate((galope, -galope, -galope, galope)):
        px = -s * 0.26 + (k % 2) * s * 0.1 + (k // 2) * s * 0.36
        perna = _rrect_path(px - s * 0.045, -s * 0.32, s * 0.09, s * 0.3, s * 0.045)
        c.save(); c.rotate(fase * 14, px, -s * 0.3)
        _forma(c, perna, cor if k % 2 else escuro, lw, sombra=False)
        _forma(c, _rrect_path(px - s * 0.05, -s * 0.06, s * 0.1, s * 0.06, s * 0.02), (52, 40, 32), lw * 0.7, sombra=False)
        c.restore()
    # rabo
    rabo = skia.Path(); rabo.moveTo(-s * 0.36, -s * 0.48)
    rabo.cubicTo(-s * 0.55, -s * 0.5 + galope * s * 0.04, -s * 0.6, -s * 0.3, -s * 0.5, -s * 0.22)
    c.drawPath(rabo, _linha(s * 0.09 + lw * 2)); c.drawPath(rabo, _linha(s * 0.09, _cor(escuro)))
    # corpo
    corpo = skia.Path(); corpo.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-s * 0.4, -s * 0.6, s * 0.78, s * 0.34), s * 0.17, s * 0.17))
    _forma(c, corpo, cor, lw)
    # sela
    _forma(c, _rrect_path(-s * 0.12, -s * 0.63, s * 0.26, s * 0.12, s * 0.05), (150, 40, 40), lw * 0.8, sombra=False)
    # pescoco + cabeca grande
    pesc = skia.Path(); pesc.moveTo(s * 0.2, -s * 0.55); pesc.lineTo(s * 0.32, -s * 0.88); pesc.lineTo(s * 0.5, -s * 0.82); pesc.lineTo(s * 0.38, -s * 0.45); pesc.close()
    _forma(c, pesc, cor, lw)
    cab = skia.Path(); cab.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(s * 0.26, -s * 1.02, s * 0.42, s * 0.28), s * 0.13, s * 0.13))
    _forma(c, cab, cor, lw)
    focinho = skia.Path(); focinho.addOval(skia.Rect.MakeXYWH(s * 0.5, -s * 0.9, s * 0.22, s * 0.17)); _forma(c, focinho, (196, 150, 112), lw, sombra=False)
    c.drawCircle(s * 0.63, -s * 0.83, s * 0.017, _fill((40, 28, 22)))
    orelha = skia.Path(); orelha.moveTo(s * 0.32, -s * 1.0); orelha.lineTo(s * 0.3, -s * 1.12); orelha.lineTo(s * 0.4, -s * 1.02); orelha.close()
    _forma(c, orelha, cor, lw * 0.8, sombra=False)
    # olho grande do estilo do canal
    c.drawOval(skia.Rect.MakeXYWH(s * 0.38, -s * 0.97, s * 0.11, s * 0.13), _fill((255, 255, 255)))
    c.drawOval(skia.Rect.MakeXYWH(s * 0.38, -s * 0.97, s * 0.11, s * 0.13), _linha(lw * 0.8))
    c.drawCircle(s * 0.45, -s * 0.9, s * 0.032, _fill((28, 22, 18))); c.drawCircle(s * 0.44, -s * 0.91, s * 0.011, _fill((255, 255, 255)))
    # crina em mechas
    for k in range(4):
        m = skia.Path(); bx, by = s * (0.3 - k * 0.025), -s * (0.98 - k * 0.12)
        m.moveTo(bx, by); m.quadTo(bx - s * 0.12, by + s * 0.02 + galope * s * 0.02, bx - s * 0.1, by + s * 0.12); m.lineTo(bx + s * 0.02, by + s * 0.08); m.close()
        _forma(c, m, escuro, lw * 0.7, sombra=False)
    c.restore()

def dragao(c, s, t, lw):
    """Dragao fofo-assustador no estilo do canal: cabecao com olhos grandes, barriga clara, espinhos, asas que batem e fogo."""
    cor, escuro, barriga = (70, 150, 96), (44, 110, 70), (236, 210, 140)
    bate = math.sin(t * 6)
    c.save(); c.translate(0, -s * 0.42 + math.sin(t * 2.4) * s * 0.05)
    # asa de tras
    asa = skia.Path(); asa.moveTo(-s * 0.05, -s * 0.2)
    asa.cubicTo(-s * 0.2, -s * 0.55 - bate * s * 0.18, -s * 0.5, -s * 0.6 - bate * s * 0.22, -s * 0.55, -s * 0.35 - bate * s * 0.2)
    asa.quadTo(-s * 0.35, -s * 0.32, -s * 0.15, -s * 0.05); asa.close()
    _forma(c, asa, escuro, lw, sombra=False)
    # rabo com ponta
    rabo = skia.Path(); rabo.moveTo(-s * 0.25, s * 0.02); rabo.cubicTo(-s * 0.5, s * 0.1, -s * 0.62, -s * 0.05, -s * 0.66, -s * 0.18 + bate * s * 0.03)
    c.drawPath(rabo, _linha(s * 0.1 + lw * 2)); c.drawPath(rabo, _linha(s * 0.1, _cor(cor)))
    ponta = skia.Path(); px, py = -s * 0.66, -s * 0.18 + bate * s * 0.03
    ponta.moveTo(px - s * 0.08, py); ponta.lineTo(px, py - s * 0.12); ponta.lineTo(px + s * 0.06, py + s * 0.02); ponta.close()
    _forma(c, ponta, escuro, lw * 0.7, sombra=False)
    # corpo redondo + barriga
    corpo = skia.Path(); corpo.addOval(skia.Rect.MakeXYWH(-s * 0.32, -s * 0.28, s * 0.58, s * 0.42)); _forma(c, corpo, cor, lw)
    c.drawOval(skia.Rect.MakeXYWH(-s * 0.12, -s * 0.18, s * 0.3, s * 0.3), _fill(barriga))
    for k in range(3):
        c.drawLine(-s * 0.08 + k * 0.0, -s * 0.12 + k * s * 0.08, s * 0.14, -s * 0.12 + k * s * 0.08, _linha(lw * 0.5, _cor((200, 170, 100))))
    # patas
    for dx in (-s * 0.15, s * 0.08):
        _forma(c, _rrect_path(dx, s * 0.06, s * 0.12, s * 0.12, s * 0.05), cor, lw * 0.8, sombra=False)
    # espinhos nas costas
    for k in range(4):
        e = skia.Path(); ex = -s * 0.22 + k * s * 0.12; ey = -s * 0.27 + abs(k - 1.5) * s * 0.025
        e.moveTo(ex - s * 0.05, ey + s * 0.03); e.lineTo(ex, ey - s * 0.08); e.lineTo(ex + s * 0.05, ey + s * 0.03); e.close()
        _forma(c, e, barriga, lw * 0.6, sombra=False)
    # cabecao
    cab = skia.Path(); cab.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(s * 0.12, -s * 0.66, s * 0.44, s * 0.38), s * 0.18, s * 0.18))
    _forma(c, cab, cor, lw)
    foc = skia.Path(); foc.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(s * 0.4, -s * 0.48, s * 0.26, s * 0.18), s * 0.08, s * 0.08))
    _forma(c, foc, cor, lw, sombra=False)
    c.drawCircle(s * 0.6, -s * 0.43, s * 0.018, _fill((30, 40, 30)))
    for dx in (0.18, 0.32):  # chifres
        ch = skia.Path(); ch.moveTo(s * dx, -s * 0.62); ch.quadTo(s * (dx - 0.06), -s * 0.8, s * (dx - 0.1), -s * 0.82); ch.lineTo(s * (dx + 0.05), -s * 0.64); ch.close()
        _forma(c, ch, barriga, lw * 0.7, sombra=False)
    # olho grande com palpebra brava (estilo do canal)
    ox, oy = s * 0.33, -s * 0.52
    c.drawOval(skia.Rect.MakeXYWH(ox - s * 0.07, oy - s * 0.08, s * 0.14, s * 0.16), _fill((255, 250, 220)))
    c.drawOval(skia.Rect.MakeXYWH(ox - s * 0.07, oy - s * 0.08, s * 0.14, s * 0.16), _linha(lw * 0.8))
    c.drawCircle(ox + s * 0.02, oy + s * 0.01, s * 0.035, _fill((30, 22, 18)))
    c.drawLine(ox - s * 0.08, oy - s * 0.1, ox + s * 0.08, oy - s * 0.05, _linha(lw * 1.2))
    # asa da frente
    asa2 = skia.Path(); asa2.moveTo(s * 0.0, -s * 0.18)
    asa2.cubicTo(-s * 0.05, -s * 0.6 - bate * s * 0.22, -s * 0.3, -s * 0.72 - bate * s * 0.25, -s * 0.36, -s * 0.5 - bate * s * 0.22)
    asa2.quadTo(-s * 0.2, -s * 0.42, -s * 0.06, -s * 0.06); asa2.close()
    _forma(c, asa2, (96, 176, 120), lw)
    for k in range(2):
        nerv = skia.Path(); nerv.moveTo(-s * 0.02, -s * 0.16); nerv.lineTo(-s * (0.14 + k * 0.12), -s * (0.55 + k * 0.06) - bate * s * 0.22)
        c.drawPath(nerv, _linha(lw * 0.6, _cor(escuro)))
    # fogo em bolas (amarelo -> laranja -> fumaca)
    if (t * 0.5) % 1.0 < 0.5:
        for k in range(8):
            f = ((t * 2.6) + k / 8) % 1.0
            cor_f = (255, 236, 120) if f < 0.3 else (255, 150, 40) if f < 0.65 else (200, 70, 30)
            fx, fy = s * 0.68 + f * s * 0.6, -s * 0.4 + math.sin(k * 2 + t * 9) * s * 0.04 + f * s * 0.05
            c.drawCircle(fx, fy, s * (0.04 + 0.09 * f), _fill(cor_f, int(245 * (1 - f * 0.7))))
    c.restore()

def trem(c, s, t, lw):
    for k, x in enumerate((-s * 0.55, -s * 0.15)):
        _forma(c, _rrect_path(x, -s * 0.4, s * 0.36, s * 0.26, s * 0.03), (150, 46, 40) if k else (132, 92, 54), lw)
    _forma(c, _rrect_path(s * 0.25, -s * 0.38, s * 0.42, s * 0.24, s * 0.1), (40, 40, 44), lw)
    _forma(c, _rrect_path(s * 0.25, -s * 0.6, s * 0.2, s * 0.26, s * 0.03), (40, 40, 44), lw)
    _forma(c, _rrect_path(s * 0.52, -s * 0.56, s * 0.08, s * 0.18, s * 0.02), (40, 40, 44), lw * 0.7, sombra=False)
    for x in (-s * 0.45, -s * 0.28, -s * 0.05, s * 0.12, s * 0.35, s * 0.55):
        _roda(c, x, -s * 0.1, s * 0.07, t, lw * 0.7)
    _fumaca(c, s * 0.56, -s * 0.6, s * 0.5, t)


def foguete(c, s, t, lw):
    """Foguete decolando: tremor, chama piscando e rastro de fumaca."""
    sobe = (t * 0.25) % 1.0 * s * 0.0  # (deslocamento real e feito por "ate"/posicao)
    tre = math.sin(t * 50) * s * 0.006
    c.save(); c.translate(tre, -sobe)
    for k in range(6):  # fumaca
        f = (t * 1.2 + k / 6) % 1.0
        c.drawCircle(math.sin(k * 3 + t) * s * 0.12 * f, s * 0.05 + f * s * 0.5, s * (0.08 + 0.18 * f), _fill((236, 234, 228), int(220 * (1 - f))))
    fl = 0.8 + 0.25 * abs(math.sin(t * 30))
    chama = skia.Path(); chama.moveTo(-s * 0.08, -s * 0.1); chama.quadTo(0, s * 0.25 * fl, s * 0.08, -s * 0.1); chama.close()
    c.drawPath(chama, _fill((255, 150, 40))); ch2 = skia.Path(); ch2.moveTo(-s * 0.04, -s * 0.1); ch2.quadTo(0, s * 0.12 * fl, s * 0.04, -s * 0.1); ch2.close()
    c.drawPath(ch2, _fill((255, 236, 120)))
    corpo = skia.Path(); corpo.moveTo(0, -s * 0.85); corpo.cubicTo(s * 0.16, -s * 0.7, s * 0.14, -s * 0.3, s * 0.11, -s * 0.12)
    corpo.lineTo(-s * 0.11, -s * 0.12); corpo.cubicTo(-s * 0.14, -s * 0.3, -s * 0.16, -s * 0.7, 0, -s * 0.85); corpo.close()
    _forma(c, corpo, (236, 236, 240), lw)
    ponta = skia.Path(); ponta.moveTo(0, -s * 0.85); ponta.cubicTo(s * 0.1, -s * 0.78, s * 0.12, -s * 0.66, s * 0.13, -s * 0.62)
    ponta.lineTo(-s * 0.13, -s * 0.62); ponta.cubicTo(-s * 0.12, -s * 0.66, -s * 0.1, -s * 0.78, 0, -s * 0.85); ponta.close()
    _forma(c, ponta, (200, 40, 44), lw, sombra=False)
    c.drawCircle(0, -s * 0.45, s * 0.055, _fill((120, 190, 230))); c.drawCircle(0, -s * 0.45, s * 0.055, _linha(lw * 0.8))
    for lado in (-1, 1):
        aleta = skia.Path(); aleta.moveTo(lado * s * 0.11, -s * 0.32); aleta.lineTo(lado * s * 0.24, -s * 0.06); aleta.lineTo(lado * s * 0.1, -s * 0.12); aleta.close()
        _forma(c, aleta, (200, 40, 44), lw, sombra=False)
    c.restore()


def satelite(c, s, t, lw):
    c.save(); c.rotate(math.sin(t * 0.8) * 10)
    for lado in (-1, 1):
        pn = _rrect_path(lado * s * 0.42 - s * 0.15, -s * 0.08, s * 0.3, s * 0.16, s * 0.02)
        _forma(c, pn, (50, 80, 150), lw, sombra=False)
        for k in range(3):
            c.drawLine(lado * s * 0.42 - s * 0.15 + k * s * 0.1, -s * 0.08, lado * s * 0.42 - s * 0.15 + k * s * 0.1, s * 0.08, _linha(lw * 0.4, _cor((140, 170, 220))))
        c.drawLine(lado * s * 0.12, 0, lado * s * 0.27, 0, _linha(lw))
    _forma(c, _rrect_path(-s * 0.12, -s * 0.12, s * 0.24, s * 0.24, s * 0.03), (226, 186, 70), lw)
    c.drawLine(0, -s * 0.12, s * 0.08, -s * 0.28, _linha(lw * 0.8)); c.drawCircle(s * 0.08, -s * 0.28, s * 0.03, _fill((220, 220, 220)))
    c.restore()


# ------------------------------------------------------------------ cenario de ESPACO
def _estrelas(c, W, H, t, n=160):
    import random
    rnd = random.Random(7)
    for k in range(n):
        x, y, r = rnd.random() * W, rnd.random() * H, rnd.random() * 2.2 + 0.6
        a = int(140 + 115 * (0.5 + 0.5 * math.sin(t * (1 + rnd.random() * 3) + k)))
        c.drawCircle(x, y, r, _fill((255, 255, 240), a))


def astro(c, tipo, x, y, R, t, textura_terra=None):
    """Sol, Lua, Terra, Marte, Jupiter, Saturno - circulos chapados com contorno do canal."""
    lw = max(2.0, R * 0.03)
    if tipo == "sol":
        for k in range(12):  # raios pulsando
            a = k * math.pi / 6 + t * 0.2; L = R * (1.35 + 0.08 * math.sin(t * 3 + k))
            raio = skia.Path(); raio.moveTo(x + math.cos(a - 0.12) * R, y + math.sin(a - 0.12) * R); raio.lineTo(x + math.cos(a) * L, y + math.sin(a) * L)
            raio.lineTo(x + math.cos(a + 0.12) * R, y + math.sin(a + 0.12) * R); raio.close()
            c.drawPath(raio, _fill((255, 196, 50)))
        c.drawCircle(x, y, R * 1.25, _fill((255, 214, 80), 50))
        cor = (255, 206, 60)
    else:
        cor = {"lua": (200, 200, 196), "terra": (60, 120, 180), "marte": (196, 88, 52), "jupiter": (214, 172, 120), "saturno": (226, 196, 130)}.get(tipo, (200, 200, 200))
    if tipo == "saturno":
        anel = skia.Path(); anel.addOval(skia.Rect.MakeXYWH(x - R * 1.9, y - R * 0.45, R * 3.8, R * 0.9))
        c.drawPath(anel, skia.Paint(Color=_cor((200, 170, 110)), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=R * 0.22))
    p = skia.Path(); p.addCircle(x, y, R)
    if tipo == "terra" and textura_terra is not None:
        c.save(); c.clipPath(p, doAntiAlias=True)
        c.drawImageRect(textura_terra, skia.Rect.MakeXYWH(x - R, y - R, 2 * R, 2 * R), skia.SamplingOptions(skia.FilterMode.kLinear))
        c.restore(); c.drawPath(p, _linha(lw))
    else:
        _forma(c, p, cor, lw)
    c.save(); c.clipPath(p, doAntiAlias=True)
    if tipo == "lua":
        for (dx, dy, rr) in ((-0.3, -0.25, 0.22), (0.35, 0.1, 0.16), (-0.1, 0.4, 0.13), (0.2, -0.45, 0.1)):
            c.drawCircle(x + dx * R, y + dy * R, rr * R, _fill((160, 160, 156))); c.drawCircle(x + dx * R, y + dy * R, rr * R, _linha(lw * 0.5))
    elif tipo == "jupiter":
        for k in range(-3, 4):
            c.drawRect(skia.Rect.MakeXYWH(x - R, y + k * R * 0.26 - R * 0.06, 2 * R, R * 0.1), _fill((176, 120, 80), 160))
        c.drawOval(skia.Rect.MakeXYWH(x + R * 0.15, y + R * 0.2, R * 0.35, R * 0.2), _fill((200, 90, 60)))
    elif tipo == "marte":
        c.drawCircle(x - R * 0.3, y - R * 0.2, R * 0.25, _fill((160, 64, 40))); c.drawOval(skia.Rect.MakeXYWH(x - R * 0.4, y - R * 1.0, R * 0.8, R * 0.25), _fill((240, 240, 240)))
    # sombra (lado noturno)
    c.drawCircle(x + R * 0.45, y + R * 0.25, R * 1.05, _fill((0, 0, 20), 70 if tipo != "sol" else 0))
    c.restore()
    if tipo == "saturno":  # parte da frente do anel
        frente = skia.Path(); frente.addArc(skia.Rect.MakeXYWH(x - R * 1.9, y - R * 0.45, R * 3.8, R * 0.9), 0, 180)
        c.drawPath(frente, skia.Paint(Color=_cor((200, 170, 110)), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=R * 0.22))


def fundo_espaco(c, W, H, t):
    c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=skia.GradientShader.MakeLinear(
        [skia.Point(0, 0), skia.Point(0, H)], [skia.ColorSetRGB(6, 8, 26), skia.ColorSetRGB(20, 14, 40)])))
    c.drawCircle(W * 0.7, H * 0.35, W * 0.6, _fill((90, 40, 140), 26))   # nebulosa suave
    c.drawCircle(W * 0.2, H * 0.7, W * 0.5, _fill((30, 90, 140), 22))
    _estrelas(c, W, H, t)


# ------------------------------------------------------------------ construcoes, natureza, objetos, animais
def _bandeirinha(c, x, y, s, t, cor=(200, 40, 40)):
    c.drawLine(x, y, x, y - s * 0.25, _linha(max(2, s * 0.012)))
    b = skia.Path(); b.moveTo(x, y - s * 0.25); b.lineTo(x + s * 0.14, y - s * 0.21 + math.sin(t * 5) * s * 0.01); b.lineTo(x, y - s * 0.17); b.close()
    c.drawPath(b, _fill(cor))


def castelo(c, s, t, lw):
    pedra = (168, 160, 148)
    for dx in (-s * 0.45, s * 0.25):
        _forma(c, _rrect_path(dx, -s * 0.8, s * 0.2, s * 0.8, s * 0.02), pedra, lw)
        tel = skia.Path(); tel.moveTo(dx - s * 0.03, -s * 0.8); tel.lineTo(dx + s * 0.1, -s * 1.02); tel.lineTo(dx + s * 0.23, -s * 0.8); tel.close()
        _forma(c, tel, (150, 50, 50), lw, sombra=False)
    _forma(c, _rrect_path(-s * 0.28, -s * 0.6, s * 0.56, s * 0.6, s * 0.02), pedra, lw)
    for k in range(5):
        c.drawRect(skia.Rect.MakeXYWH(-s * 0.28 + k * s * 0.12, -s * 0.66, s * 0.07, s * 0.07), _fill(pedra))
    porta = skia.Path(); porta.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-s * 0.08, -s * 0.24, s * 0.16, s * 0.24), s * 0.08, s * 0.08))
    _forma(c, porta, (90, 60, 40), lw, sombra=False)
    _bandeirinha(c, -s * 0.35, -s * 1.02, s, t); _bandeirinha(c, s * 0.35, -s * 1.02, s, t + 1)


def piramide(c, s, t, lw):
    p = skia.Path(); p.moveTo(-s * 0.6, 0); p.lineTo(0, -s * 0.7); p.lineTo(s * 0.6, 0); p.close(); _forma(c, p, (220, 186, 120), lw)
    for k in range(1, 6):
        y = -s * 0.7 * k / 6; w = s * 0.6 * (1 - k / 6)
        c.drawLine(-w, y, w, y, _linha(lw * 0.4, _cor((176, 140, 84))))
    lado = skia.Path(); lado.moveTo(0, -s * 0.7); lado.lineTo(s * 0.6, 0); lado.lineTo(s * 0.1, 0); lado.close()
    c.drawPath(lado, _fill((0, 0, 0), 40))


def igreja(c, s, t, lw):
    _forma(c, _rrect_path(-s * 0.35, -s * 0.45, s * 0.5, s * 0.45, s * 0.02), (240, 236, 224), lw)
    tel = skia.Path(); tel.moveTo(-s * 0.4, -s * 0.45); tel.lineTo(-s * 0.1, -s * 0.65); tel.lineTo(s * 0.2, -s * 0.45); tel.close(); _forma(c, tel, (170, 70, 50), lw, sombra=False)
    _forma(c, _rrect_path(s * 0.15, -s * 0.85, s * 0.2, s * 0.85, s * 0.02), (240, 236, 224), lw)
    tor = skia.Path(); tor.moveTo(s * 0.12, -s * 0.85); tor.lineTo(s * 0.25, -s * 1.02); tor.lineTo(s * 0.38, -s * 0.85); tor.close(); _forma(c, tor, (170, 70, 50), lw, sombra=False)
    c.drawLine(s * 0.25, -s * 1.02, s * 0.25, -s * 1.16, _linha(lw)); c.drawLine(s * 0.2, -s * 1.1, s * 0.3, -s * 1.1, _linha(lw))
    porta = skia.Path(); porta.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-s * 0.15, -s * 0.22, s * 0.12, s * 0.22), s * 0.06, s * 0.06)); _forma(c, porta, (110, 70, 40), lw * 0.8, sombra=False)
    c.drawCircle(s * 0.25, -s * 0.62, s * 0.05, _fill((90, 160, 210))); c.drawCircle(s * 0.25, -s * 0.62, s * 0.05, _linha(lw * 0.7))


def casa(c, s, t, lw):
    _forma(c, _rrect_path(-s * 0.32, -s * 0.4, s * 0.64, s * 0.4, s * 0.02), (236, 210, 160), lw)
    tel = skia.Path(); tel.moveTo(-s * 0.4, -s * 0.4); tel.lineTo(0, -s * 0.68); tel.lineTo(s * 0.4, -s * 0.4); tel.close(); _forma(c, tel, (176, 70, 50), lw)
    _forma(c, _rrect_path(s * 0.15, -s * 0.66, s * 0.09, s * 0.16, s * 0.01), (120, 70, 50), lw * 0.7, sombra=False)
    for k in range(3):
        f = (t * 0.6 + k / 3) % 1.0
        c.drawCircle(s * 0.2 + f * s * 0.1, -s * 0.7 - f * s * 0.3, s * (0.03 + 0.06 * f), _fill((230, 228, 224), int(200 * (1 - f))))
    _forma(c, _rrect_path(-s * 0.06, -s * 0.2, s * 0.12, s * 0.2, s * 0.01), (110, 70, 40), lw * 0.7, sombra=False)
    _forma(c, _rrect_path(-s * 0.25, -s * 0.3, s * 0.12, s * 0.1, s * 0.01), (120, 190, 220), lw * 0.7, sombra=False)


def palmeira(c, s, t, lw):
    tr = skia.Path(); tr.moveTo(-s * 0.03, 0); tr.quadTo(s * 0.05, -s * 0.4, s * 0.0, -s * 0.8); tr.lineTo(s * 0.06, -s * 0.8); tr.quadTo(s * 0.11, -s * 0.4, s * 0.04, 0); tr.close()
    _forma(c, tr, (140, 100, 60), lw)
    for k in range(6):
        a = math.pi + k * math.pi / 5 + math.sin(t * 2 + k) * 0.05
        f = skia.Path(); x0, y0 = s * 0.03, -s * 0.8
        f.moveTo(x0, y0); f.quadTo(x0 + math.cos(a) * s * 0.25, y0 + math.sin(a) * s * 0.25 - s * 0.1, x0 + math.cos(a) * s * 0.42, y0 + math.sin(a) * s * 0.3 + s * 0.12)
        c.drawPath(f, _linha(s * 0.07 + lw * 2)); c.drawPath(f, _linha(s * 0.07, _cor((60, 150, 80))))


def arvore(c, s, t, lw):
    _forma(c, _rrect_path(-s * 0.05, -s * 0.35, s * 0.1, s * 0.35, s * 0.03), (120, 84, 50), lw)
    bal = math.sin(t * 1.5) * s * 0.01
    for (dx, dy, r_) in ((-0.15, -0.5, 0.2), (0.15, -0.5, 0.2), (0, -0.68, 0.24)):
        b = skia.Path(); b.addCircle(dx * s + bal, dy * s, r_ * s); _forma(c, b, (70, 140, 70), lw)


def vulcao(c, s, t, lw):
    m = skia.Path(); m.moveTo(-s * 0.6, 0); m.lineTo(-s * 0.12, -s * 0.6); m.lineTo(s * 0.12, -s * 0.6); m.lineTo(s * 0.6, 0); m.close(); _forma(c, m, (110, 84, 70), lw)
    lava = skia.Path(); lava.moveTo(-s * 0.1, -s * 0.6); lava.lineTo(-s * 0.2, -s * 0.35); lava.lineTo(-s * 0.08, -s * 0.4); lava.lineTo(s * 0.0, -s * 0.2); lava.lineTo(s * 0.1, -s * 0.6); lava.close()
    c.drawPath(lava, _fill((240, 110, 30)))
    for k in range(6):
        f = (t * 0.9 + k / 6) % 1.0
        c.drawCircle(math.sin(k * 2) * s * 0.15 * f, -s * 0.65 - f * s * 0.6, s * (0.06 + 0.12 * f), _fill((90, 86, 84), int(220 * (1 - f))))
    for k in range(3):
        f = (t * 1.6 + k / 3) % 1.0
        c.drawCircle(math.sin(k * 3) * s * 0.2 * f, -s * 0.6 - math.sin(f * math.pi) * s * 0.3, s * 0.03, _fill((255, 160, 40)))


def fogueira(c, s, t, lw):
    for a in (-0.5, 0.5):
        c.save(); c.rotate(math.degrees(a)); _forma(c, _rrect_path(-s * 0.25, -s * 0.05, s * 0.5, s * 0.08, s * 0.04), (120, 80, 46), lw, sombra=False); c.restore()
    for k, (cor, esc) in enumerate((((240, 100, 30), 1.0), ((255, 180, 40), 0.7), ((255, 236, 140), 0.4))):
        fl = 1 + 0.12 * math.sin(t * 14 + k)
        ch = skia.Path(); h_ = s * 0.55 * esc * fl; w_ = s * 0.22 * esc
        ch.moveTo(-w_, -s * 0.03); ch.quadTo(-w_ * 0.8, -h_ * 0.6, 0, -h_); ch.quadTo(w_ * 0.8, -h_ * 0.6, w_, -s * 0.03); ch.close()
        c.drawPath(ch, _fill(cor))


def tesouro(c, s, t, lw):
    _forma(c, _rrect_path(-s * 0.3, -s * 0.3, s * 0.6, s * 0.3, s * 0.03), (140, 90, 46), lw)
    tampa = skia.Path(); tampa.addArc(skia.Rect.MakeXYWH(-s * 0.3, -s * 0.48, s * 0.6, s * 0.36), 180, 180); tampa.close(); _forma(c, tampa, (150, 98, 50), lw)
    for k in range(5):
        c.drawCircle(-s * 0.18 + k * s * 0.09, -s * 0.33 - (k % 2) * s * 0.03, s * 0.05, _fill((240, 200, 60))); c.drawCircle(-s * 0.18 + k * s * 0.09, -s * 0.33 - (k % 2) * s * 0.03, s * 0.05, _linha(lw * 0.5))
    c.drawRect(skia.Rect.MakeXYWH(-s * 0.04, -s * 0.24, s * 0.08, s * 0.1), _fill((226, 186, 70)))
    if math.sin(t * 4) > 0.6:
        c.drawCircle(s * 0.15, -s * 0.45, s * 0.04, _fill((255, 255, 255), 220))


def pergaminho(c, s, t, lw):
    abre = min(1.0, t / 0.6)
    w = s * 0.5 * abre + s * 0.05
    _forma(c, _rrect_path(-w, -s * 0.5, w * 2, s * 0.5, s * 0.02), (240, 228, 196), lw)
    for k in range(4):
        if abre > 0.6:
            c.drawLine(-w * 0.7, -s * (0.4 - k * 0.09), w * 0.7, -s * (0.4 - k * 0.09), _linha(lw * 0.4, _cor((120, 100, 70))))
    for x in (-w, w):
        _forma(c, _rrect_path(x - s * 0.04, -s * 0.55, s * 0.08, s * 0.6, s * 0.04), (200, 176, 130), lw, sombra=False)


def lapide(c, s, t, lw):
    l = skia.Path(); l.addArc(skia.Rect.MakeXYWH(-s * 0.2, -s * 0.5, s * 0.4, s * 0.4), 180, 180)
    l.lineTo(s * 0.2, 0); l.lineTo(-s * 0.2, 0); l.close()
    _forma(c, l, (150, 150, 154), lw)
    c.drawRect(skia.Rect.MakeXYWH(-s * 0.025, -s * 0.42, s * 0.05, s * 0.22), _fill((90, 90, 96)))
    c.drawRect(skia.Rect.MakeXYWH(-s * 0.09, -s * 0.36, s * 0.18, s * 0.05), _fill((90, 90, 96)))
    c.drawOval(skia.Rect.MakeXYWH(-s * 0.3, -s * 0.03, s * 0.6, s * 0.08), _fill((70, 120, 60)))


def bomba(c, s, t, lw):
    b = skia.Path(); b.addCircle(0, -s * 0.22, s * 0.2); _forma(c, b, (40, 40, 44), lw)
    _forma(c, _rrect_path(-s * 0.06, -s * 0.47, s * 0.12, s * 0.08, s * 0.02), (90, 90, 96), lw * 0.7, sombra=False)
    pav = skia.Path(); pav.moveTo(0, -s * 0.47); pav.quadTo(s * 0.08, -s * 0.6, s * 0.15, -s * 0.58); c.drawPath(pav, _linha(lw, _cor((150, 110, 70))))
    if math.sin(t * 20) > -0.3:
        c.drawCircle(s * 0.16, -s * 0.6, s * 0.04 + abs(math.sin(t * 25)) * s * 0.02, _fill((255, 200, 40)))
    c.drawCircle(-s * 0.08, -s * 0.3, s * 0.04, _fill((255, 255, 255), 120))


def zeppelin(c, s, t, lw):
    c.save(); c.translate(0, math.sin(t * 1.2) * s * 0.02)
    corpo = skia.Path(); corpo.addOval(skia.Rect.MakeXYWH(-s * 0.6, -s * 0.5, s * 1.2, s * 0.32)); _forma(c, corpo, (200, 200, 204), lw)
    for k in range(-3, 4):
        c.drawLine(k * s * 0.13, -s * 0.48, k * s * 0.13, -s * 0.2, _linha(lw * 0.4, _cor((160, 160, 166))))
    for dy in (-1, 1):
        al = skia.Path(); al.moveTo(-s * 0.5, -s * 0.34); al.lineTo(-s * 0.68, -s * 0.34 + dy * s * 0.14); al.lineTo(-s * 0.58, -s * 0.34); al.close()
        _forma(c, al, (170, 40, 40), lw * 0.7, sombra=False)
    _forma(c, _rrect_path(-s * 0.12, -s * 0.2, s * 0.24, s * 0.08, s * 0.03), (120, 90, 60), lw, sombra=False)
    c.restore()


def submarino(c, s, t, lw):
    c.save(); c.translate(0, math.sin(t * 1.3) * s * 0.02)
    corpo = skia.Path(); corpo.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-s * 0.6, -s * 0.28, s * 1.2, s * 0.24), s * 0.12, s * 0.12)); _forma(c, corpo, (70, 80, 90), lw)
    _forma(c, _rrect_path(-s * 0.1, -s * 0.44, s * 0.22, s * 0.18, s * 0.04), (80, 90, 100), lw)
    c.drawLine(s * 0.04, -s * 0.44, s * 0.04, -s * 0.56, _linha(lw)); c.drawLine(s * 0.04, -s * 0.56, s * 0.12, -s * 0.56, _linha(lw))
    for k in range(3):
        c.drawCircle(-s * 0.35 + k * s * 0.18, -s * 0.16, s * 0.035, _fill((150, 200, 220))); c.drawCircle(-s * 0.35 + k * s * 0.18, -s * 0.16, s * 0.035, _linha(lw * 0.6))
    hw = abs(math.sin(t * 20)) * s * 0.06 + s * 0.01
    c.drawOval(skia.Rect.MakeXYWH(-s * 0.66, -s * 0.16 - hw, s * 0.05, hw * 2), _fill((60, 60, 64)))
    c.restore(); _ondas(c, s, t, lw)


def helicoptero(c, s, t, lw):
    c.save(); c.translate(0, math.sin(t * 2) * s * 0.02)
    corpo = skia.Path(); corpo.addOval(skia.Rect.MakeXYWH(-s * 0.25, -s * 0.42, s * 0.5, s * 0.3)); _forma(c, corpo, (90, 110, 70), lw)
    c.drawCircle(s * 0.12, -s * 0.3, s * 0.08, _fill((150, 200, 230)))
    cauda = _rrect_path(-s * 0.6, -s * 0.33, s * 0.38, s * 0.06, s * 0.03); _forma(c, cauda, (90, 110, 70), lw, sombra=False)
    c.drawLine(-s * 0.2, -s * 0.1, s * 0.2, -s * 0.1, _linha(lw)); c.drawLine(-s * 0.1, -s * 0.12, -s * 0.1, -s * 0.06, _linha(lw))
    hw = abs(math.cos(t * 30)) * s * 0.55 + s * 0.05
    c.drawRect(skia.Rect.MakeXYWH(-hw, -s * 0.48, hw * 2, s * 0.025), _fill((40, 40, 44)))
    c.drawLine(0, -s * 0.48, 0, -s * 0.42, _linha(lw))
    c.restore()


def balao(c, s, t, lw):
    c.save(); c.translate(math.sin(t * 0.8) * s * 0.03, math.sin(t * 1.1) * s * 0.03)
    b = skia.Path(); b.moveTo(0, -s * 0.3); b.cubicTo(-s * 0.45, -s * 0.5, -s * 0.4, -s * 1.05, 0, -s * 1.05); b.cubicTo(s * 0.4, -s * 1.05, s * 0.45, -s * 0.5, 0, -s * 0.3); b.close()
    c.save(); c.clipPath(b, doAntiAlias=True)
    for k in range(-3, 4):
        c.drawRect(skia.Rect.MakeXYWH(k * s * 0.13 - s * 0.065, -s * 1.1, s * 0.13, s * 0.8), _fill((214, 60, 50) if k % 2 else (240, 196, 60)))
    c.restore(); c.drawPath(b, _linha(lw))
    for dx in (-0.08, 0.08):
        c.drawLine(dx * s, -s * 0.32, dx * s, -s * 0.18, _linha(lw * 0.6))
    _forma(c, _rrect_path(-s * 0.1, -s * 0.18, s * 0.2, s * 0.12, s * 0.02), (150, 104, 60), lw, sombra=False)
    c.restore()


def elefante(c, s, t, lw):
    passo = math.sin(t * 6)
    cor = (150, 150, 158)
    for k, fase in enumerate((passo, -passo, -passo, passo)):
        px = -s * 0.28 + k * s * 0.17
        _forma(c, _rrect_path(px - s * 0.06, -s * 0.28 + abs(fase) * s * 0.02, s * 0.12, s * 0.28, s * 0.04), cor, lw, sombra=False)
    corpo = skia.Path(); corpo.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-s * 0.4, -s * 0.66, s * 0.72, s * 0.42), s * 0.2, s * 0.2)); _forma(c, corpo, cor, lw)
    cab = skia.Path(); cab.addCircle(s * 0.38, -s * 0.6, s * 0.17); _forma(c, cab, cor, lw)
    orelha = skia.Path(); orelha.addOval(skia.Rect.MakeXYWH(s * 0.16, -s * 0.74, s * 0.2, s * 0.26)); _forma(c, orelha, (170, 160, 170), lw)
    tromba = skia.Path(); tromba.moveTo(s * 0.5, -s * 0.55); tromba.quadTo(s * 0.62, -s * 0.35 + passo * s * 0.02, s * 0.55, -s * 0.2)
    c.drawPath(tromba, _linha(s * 0.07 + lw * 2)); c.drawPath(tromba, _linha(s * 0.07, _cor(cor)))
    c.drawOval(skia.Rect.MakeXYWH(s * 0.36, -s * 0.7, s * 0.07, s * 0.09), _fill((255, 255, 255))); c.drawCircle(s * 0.4, -s * 0.65, s * 0.02, _fill((28, 22, 18)))


def camelo(c, s, t, lw):
    passo = math.sin(t * 7)
    cor = (206, 160, 100)
    for k, fase in enumerate((passo, -passo, -passo, passo)):
        px = -s * 0.25 + k * s * 0.15
        c.drawLine(px, -s * 0.42, px + fase * s * 0.05, 0, _linha(s * 0.05 + lw * 2)); c.drawLine(px, -s * 0.42, px + fase * s * 0.05, 0, _linha(s * 0.05, _cor(cor)))
    corpo = skia.Path(); corpo.addOval(skia.Rect.MakeXYWH(-s * 0.35, -s * 0.62, s * 0.62, s * 0.26)); _forma(c, corpo, cor, lw)
    for dx in (-0.15, 0.08):
        cor_ = skia.Path(); cor_.addCircle(dx * s, -s * 0.6, s * 0.11); _forma(c, cor_, cor, lw, sombra=False)
    pesc = skia.Path(); pesc.moveTo(s * 0.22, -s * 0.5); pesc.quadTo(s * 0.42, -s * 0.55, s * 0.4, -s * 0.85)
    c.drawPath(pesc, _linha(s * 0.08 + lw * 2)); c.drawPath(pesc, _linha(s * 0.08, _cor(cor)))
    cab = skia.Path(); cab.addOval(skia.Rect.MakeXYWH(s * 0.34, -s * 0.94, s * 0.22, s * 0.12)); _forma(c, cab, cor, lw)
    c.drawOval(skia.Rect.MakeXYWH(s * 0.4, -s * 0.94, s * 0.06, s * 0.07), _fill((255, 255, 255))); c.drawCircle(s * 0.43, -s * 0.9, s * 0.017, _fill((28, 22, 18)))


DESENHOS = {"castelo": castelo, "piramide": piramide, "igreja": igreja, "casa": casa, "palmeira": palmeira, "arvore": arvore,
            "vulcao": vulcao, "fogueira": fogueira, "tesouro": tesouro, "pergaminho": pergaminho, "lapide": lapide, "bomba": bomba,
            "zeppelin": zeppelin, "submarino": submarino, "helicoptero": helicoptero, "balao": balao, "elefante": elefante, "camelo": camelo, "foguete": foguete, "satelite": satelite, "tanque": tanque, "aviao": aviao, "navio_guerra": navio_guerra, "caravela": caravela,
            "canhao": canhao, "cavalo": cavalo, "dragao": dragao, "trem": trem}


def desenhar(c, obj, x, y, tam, t):
    fn = DESENHOS.get(obj.get("tipo"))
    if not fn:
        return
    lw = max(2.0, tam * 0.022)
    c.save(); c.translate(x, y)
    if obj.get("olha") == "esq":
        c.scale(-1, 1)
    c.drawOval(skia.Rect.MakeXYWH(-tam * 0.5, -tam * 0.02, tam, tam * 0.06), _fill((0, 0, 0), 70)) if obj.get("tipo") not in ("aviao", "dragao") else None
    fn(c, tam, t, lw)
    c.restore()

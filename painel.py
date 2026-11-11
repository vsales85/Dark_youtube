"""Dark Studio - painel local. Rode: python painel.py -> http://localhost:8765"""
import json, os, re, shutil, subprocess, sys, threading, time, uuid, webbrowser, datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
PASTAS = {k: os.path.join(BASE, k) for k in ("Para_Aprovar", "Aprovados", "Rejeitados")}
for p in PASTAS.values():
    os.makedirs(p, exist_ok=True)
HTML_ARQ = os.path.join(BASE, "painel.html")
JOBS_DIR = os.path.join(BASE, "fila")
os.makedirs(JOBS_DIR, exist_ok=True)
FILA_ARQ = os.path.join(JOBS_DIR, "fila.json")
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}  # log ao vivo
EXT_VIS = (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm")


# ------------------------------------------------------------------ fila de tarefas
class Fila:
    """Uma tarefa por vez (nao sobrecarrega o PC), com cancelamento, timeout, log e recuperacao apos queda."""

    def __init__(self):
        self.lock = threading.Lock()
        self.jobs = json.load(open(FILA_ARQ, encoding="utf-8")) if os.path.exists(FILA_ARQ) else []
        for j in self.jobs:
            if j["status"] in ("rodando", "na_fila"):
                j["status"] = "interrompido" if j["status"] == "rodando" else "na_fila"
        self.proc, self.atual = None, None
        self.salvar()
        threading.Thread(target=self.loop, daemon=True).start()

    def salvar(self):
        json.dump(self.jobs[-200:], open(FILA_ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def add(self, tipo, titulo, args, timeout_min=90):
        j = {"id": uuid.uuid4().hex[:8], "tipo": tipo, "titulo": titulo, "args": args, "status": "na_fila",
             "criado": datetime.datetime.now().isoformat(timespec="seconds"), "timeout_min": timeout_min, "ultima": ""}
        with self.lock:
            self.jobs.append(j); self.salvar()
        return j

    def cancelar(self, jid):
        with self.lock:
            for j in self.jobs:
                if j["id"] == jid and j["status"] == "na_fila":
                    j["status"] = "cancelado"
                if j["id"] == jid and j["status"] == "rodando" and self.proc:
                    j["status"] = "cancelado"
                    subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True)
            self.salvar()

    def repetir(self, jid):
        for j in list(self.jobs):
            if j["id"] == jid:
                return self.add(j["tipo"], j["titulo"], j["args"], j["timeout_min"])

    def loop(self):
        while True:
            prox = next((j for j in self.jobs if j["status"] == "na_fila"), None)
            if not prox:
                time.sleep(1); continue
            self.rodar(prox)

    def rodar(self, j):
        log = os.path.join(JOBS_DIR, f"{j['id']}.log")
        with self.lock:
            j["status"], j["inicio"] = "rodando", datetime.datetime.now().isoformat(timespec="seconds"); self.salvar()
        with open(log, "w", encoding="utf-8") as fh:
            self.proc = subprocess.Popen([sys.executable, *j["args"]], cwd=BASE, stdout=fh, stderr=subprocess.STDOUT, env=ENV)
            t0 = time.time()
            while self.proc.poll() is None:
                time.sleep(1)
                j["ultima"] = ultima_linha(log)
                j["fase"], j["pct"] = progresso(log, j["tipo"])
                if time.time() - t0 > j["timeout_min"] * 60:
                    subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True)
                    j["status"] = "erro"; j["ultima"] = f"Tempo limite de {j['timeout_min']} min atingido"
        with self.lock:
            if j["status"] == "rodando":
                j["status"] = "ok" if self.proc.returncode == 0 else "erro"
            j["ultima"] = ultima_linha(log) if j["status"] != "erro" or not j["ultima"].startswith("Tempo") else j["ultima"]
            j["fim"] = datetime.datetime.now().isoformat(timespec="seconds")
            if j["status"] == "ok":
                j["fase"], j["pct"] = "Concluído", 100
            self.proc = None; self.salvar()


def progresso(log, tipo):
    """Traduz o log tecnico numa fase amigavel + porcentagem para a barra do painel."""
    try:
        txt = open(log, encoding="utf-8", errors="replace").read()
    except Exception:
        return "Iniciando…", 2
    ultimo = lambda rx: (re.findall(rx, txt) or [None])[-1]
    if tipo == "upload":
        return ("Enviando para o YouTube…", 50) if "Pronto!" not in txt else ("Enviado", 100)
    if tipo == "imagens":
        m = re.findall(r"cena(\d+):", txt)
        return f"Buscando fotos · cena {m[-1] if m else 1}", min(95, 5 + 3 * len(m))
    fase, pct = "Iniciando…", 2
    if "1/4 Roteiro" in txt:
        fase, pct = "Escrevendo o roteiro com IA…", 5
        b = ultimo(r"bloco (\d+)/(\d+)")
        if b: fase, pct = f"Escrevendo o roteiro · bloco {b[0]} de {b[1]}", 5 + 12 * int(b[0]) / int(b[1])
    if "2/4 Narra" in txt:
        fase, pct = "Gravando a narração…", 20
    if "3/4 Imagens" in txt:
        fase, pct = "Preparando imagens…", 25
    if "gerando" in txt and "no seu PC" in txt:
        fase, pct = "Carregando o gerador de imagens na placa…", 27
    g = ultimo(r"imagem (\d+)/(\d+) em")
    if g and "animando" not in txt:
        fase, pct = f"Gerando imagens no seu PC · {g[0]} de {g[1]}", 28 + 47 * int(g[0]) / int(g[1])
    a = ultimo(r"PROGRESSO (\d+)/(\d+) animando")
    if a:
        fase, pct = f"Animando cenas · {a[0]} de {a[1]}", 76 + 16 * int(a[0]) / int(a[1])
    if "4/4 Montagem" in txt:
        fase, pct = "Montagem final: legendas e trilha…", 94
    if "Pronto!" in txt:
        fase, pct = "Concluído", 100
    return fase, round(pct)


def ultima_linha(log):
    try:
        linhas = [l.strip() for l in open(log, encoding="utf-8", errors="replace") if l.strip()]
        return linhas[-1][:220] if linhas else ""
    except Exception:
        return ""


FILA = None


# ------------------------------------------------------------------ helpers
def pasta_video(aba, nome):
    raiz = PASTAS.get(aba)
    if not raiz:
        raise ValueError("aba invalida")
    d = os.path.join(raiz, os.path.basename(nome))
    if not os.path.isdir(d):
        raise ValueError("video nao encontrado")
    return d


def ler_rot(d):
    return json.load(open(os.path.join(d, "roteiro.json"), encoding="utf-8"))


def salvar_rot(d, rot):
    json.dump(rot, open(os.path.join(d, "roteiro.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def visuais(d):
    out = {}
    pi = os.path.join(d, "imagens")
    if os.path.isdir(pi):
        for f in sorted(os.listdir(pi)):
            m = re.match(r"cena0*(\d+)\.", f.lower())
            if m and f.lower().endswith(EXT_VIS):
                out[int(m.group(1))] = f
    return out


def ordenar(nomes):
    grupos = {}
    for n in nomes:
        m = re.match(r"^(\d{8}_\d{4,6})_(.*)_P(\d\d)(_\d+)?$", n)
        g = m.group(2) if m else n
        grupos.setdefault(g, []).append((int(m.group(3)) if m else 0, n))
    ordem = sorted(grupos.values(), key=lambda v: min(x[1][:15] for x in v), reverse=True)
    return [n for v in ordem for _, n in sorted(v)]


def item_video(aba, n):
    d = os.path.join(PASTAS[aba], n)
    try:
        r = ler_rot(d)
    except Exception:
        return None
    yt = os.path.join(d, "youtube.txt")
    tem_video = os.path.isfile(os.path.join(d, "video.mp4"))
    return {"pasta": n, "titulo": r.get("titulo", n), "descricao": r.get("descricao", ""),
            "serie": r.get("serie", ""), "parte": r.get("parte"), "total": r.get("total"),
            "tema": r.get("tema_canal", ""), "formato": r.get("formato", ""), "tela": r.get("tela", ""),
            "duracao": r.get("duracao_s"), "custo_usd": r.get("custo_usd"), "cenas": len(r.get("cenas", [])),
            "sem_visual": len(r.get("sem_visual", [])), "status": "pronto" if tem_video else "incompleto",
            "miniatura": os.path.exists(os.path.join(d, "miniatura.jpg")),
            "youtube": open(yt).read().strip() if os.path.exists(yt) else ""}


def servir_arquivo(h, f, ctype):
    tam = os.path.getsize(f); ini, fim = 0, tam - 1
    rng = h.headers.get("Range")
    if rng:
        a, _, b = rng.replace("bytes=", "").partition("-")
        ini = int(a or 0); fim = int(b) if b else tam - 1
    h.send_response(206 if rng else 200)
    h.send_header("Content-Type", ctype); h.send_header("Accept-Ranges", "bytes")
    h.send_header("Cache-Control", "no-cache")
    h.send_header("Content-Length", str(fim - ini + 1))
    if rng: h.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
    h.end_headers()
    with open(f, "rb") as fh:
        fh.seek(ini); falta = fim - ini + 1
        try:
            while falta > 0:
                c = fh.read(min(65536, falta)); h.wfile.write(c); falta -= len(c)
        except (ConnectionError, OSError):
            pass


TIPOS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
         ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}


# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        try:
            return self.get()
        except Exception as e:
            return self.send(200, {"erro": str(e)[:300]})

    def do_POST(self):
        try:
            return self.post()
        except Exception as e:
            return self.send(200, {"erro": str(e)[:300]})

    def ponte(self, metodo):
        """/api/sc/<rota do SupoClip> -> repassa ao servidor do SupoClip com a chave (so rotas liberadas)."""
        import supoclip
        u = urlparse(self.path)
        caminho = "/" + u.path[len("/api/sc/"):]
        tam = int(self.headers.get("Content-Length", 0) or 0)
        corpo = self.rfile.read(tam) if tam else None
        st, tipo, conteudo = supoclip.chamar(metodo, caminho, corpo, {k: v[0] for k, v in parse_qs(u.query).items()}, bruto=True)
        return self.send(st, conteudo, tipo)

    def do_PUT(self):
        try:
            return self.ponte("PUT") if self.path.startswith("/api/sc/") else self.send(404, "nao encontrado", "text/plain")
        except Exception as e:
            return self.send(502, {"erro": str(e)[:300]})

    def do_DELETE(self):
        try:
            return self.ponte("DELETE") if self.path.startswith("/api/sc/") else self.send(404, "nao encontrado", "text/plain")
        except Exception as e:
            return self.send(502, {"erro": str(e)[:300]})

    def get(self):
        u = urlparse(self.path); path = unquote(u.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if path.startswith("/api/sc/"):
            return self.ponte("GET")
        if path == "/api/supoclip/status":
            import supoclip
            return self.send(200, supoclip.status())
        if path == "/":
            return self.send(200, open(HTML_ARQ, encoding="utf-8").read(), "text/html; charset=utf-8")
        if path == "/api/videos":
            aba = q.get("aba", "Para_Aprovar")
            return self.send(200, [i for n in ordenar(os.listdir(PASTAS[aba])) if (i := item_video(aba, n))])
        if path == "/api/fila":
            return self.send(200, FILA.jobs[-40:][::-1])
        if path == "/api/log":
            f = os.path.join(JOBS_DIR, os.path.basename(q["id"]) + ".log")
            return self.send(200, open(f, encoding="utf-8", errors="replace").read()[-6000:] if os.path.exists(f) else "", "text/plain; charset=utf-8")
        if path == "/api/editor":
            d = pasta_video(q["aba"], q["pasta"]); r = ler_rot(d); vis = visuais(d)
            return self.send(200, {"rot": r, "visuais": {str(k): v for k, v in vis.items()}})
        if path == "/api/prompts":  # compatibilidade
            d = pasta_video(q["aba"], q["pasta"]); r = ler_rot(d)
            return self.send(200, {"formato": r.get("tela", ""), "imagens": list(visuais(d).values()),
                                   "cenas": [{"n": i + 1, "narracao": c["narracao"], "prompt": c.get("imagem", "")} for i, c in enumerate(r["cenas"])]})
        if path == "/api/temas":
            sys.path.insert(0, BASE)
            import gerar_video as g
            return self.send(200, {"temas": {k: v["nome"] for k, v in g.TEMAS_CANAL.items()},
                                   "estilos": {k: v["estilo"] for k, v in g.TEMAS_CANAL.items()},
                                   "vozes": list(g.VOZES), "tabela_cenas": g.TABELA_CENAS_PADRAO})
        if path == "/api/agenda":
            itens = []
            for aba in ("Aprovados", "Para_Aprovar"):
                for n in os.listdir(PASTAS[aba]):
                    try:
                        r = ler_rot(os.path.join(PASTAS[aba], n))
                    except Exception:
                        continue
                    ag, yt = r.get("agenda") or {}, r.get("youtube") or {}
                    if ag.get("publicar_em") or yt.get("url"):
                        itens.append({"aba": aba, "pasta": n, "titulo": (r.get("publicacao") or {}).get("titulo") or r.get("titulo"),
                                      "publicar_em": ag.get("publicar_em") or yt.get("publicar_em"), "url": yt.get("url", ""),
                                      "enviado": bool(yt.get("url")), "formato": r.get("formato"), "duracao": r.get("duracao_s")})
            return self.send(200, sorted(itens, key=lambda x: x["publicar_em"] or "9999"))
        if path == "/api/custos":
            import custos
            return self.send(200, custos.resumo())
        if path == "/api/projetos":
            raiz = os.path.join(BASE, "Projetos"); itens = []
            for n in sorted(os.listdir(raiz)) if os.path.isdir(raiz) else []:
                bib = os.path.join(raiz, n, "biblia.json")
                if os.path.exists(bib):
                    b = json.load(open(bib, encoding="utf-8"))
                    caps = len([f for f in os.listdir(os.path.join(raiz, n)) if re.match(r"cap\d+\.json", f)])
                    cfg = json.load(open(os.path.join(raiz, n, "config.json"), encoding="utf-8"))
                    itens.append({"id": n, "titulo": b.get("titulo_serie", n), "logline": b.get("logline", ""),
                                  "caps": caps, "total": cfg.get("capitulos"), "genero": cfg.get("genero"),
                                  "duracao": cfg.get("duracao_s"), "formato": cfg.get("formato")})
            return self.send(200, itens)
        if path == "/api/projeto":
            d = os.path.join(BASE, "Projetos", os.path.basename(q["id"]))
            caps = [json.load(open(os.path.join(d, f), encoding="utf-8")) for f in sorted(os.listdir(d)) if re.match(r"cap\d+\.json", f)]
            return self.send(200, {"biblia": json.load(open(os.path.join(d, "biblia.json"), encoding="utf-8")), "capitulos": caps})
        if path == "/api/vozes_clonadas":
            sys.path.insert(0, BASE)
            import gerar_video as g
            return self.send(200, {"vozes": g.vozes_clonadas()})
        if path.startswith("/amostra_voz/"):  # previa gratis da voz (Edge TTS), guardada em amostras/
            sys.path.insert(0, BASE)
            import gerar_video as g
            k = unquote(os.path.basename(path))
            if k not in g.VOZES and not (k.startswith("clone:") and any(v["voice_id"] == k[6:] for v in g.vozes_clonadas())):
                return self.send(404, "voz desconhecida", "text/plain")
            f = os.path.join(BASE, "amostras", f"voz_{k.replace(':', '_')}.wav")
            if not os.path.isfile(f):
                os.makedirs(os.path.dirname(f), exist_ok=True)
                g.CFG.update({"voz": k, "vozes_personagens": False, "velocidade": 0, "modo": "longo"})
                g.gerar_voz("Naquela noite, a escola estava vazia. Mas alguém... ainda estava lá dentro.", f, "narrador")
            return servir_arquivo(self, f, "audio/wav")
        if path.startswith("/video/") or path.startswith("/thumb/") or path.startswith("/img/"):
            partes = path.split("/")
            d = pasta_video(partes[2], partes[3])
            if partes[1] == "video":
                f = os.path.join(d, "video.mp4")
            elif partes[1] == "thumb":
                f = os.path.join(d, "miniatura.jpg")
            else:
                f = os.path.join(d, "imagens", os.path.basename(partes[4]))
            if not os.path.isfile(f):
                return self.send(404, "nao encontrado", "text/plain")
            return servir_arquivo(self, f, TIPOS.get(os.path.splitext(f)[1].lower(), "application/octet-stream"))
        self.send(404, "nao encontrado", "text/plain")

    def post(self):
        if self.path.startswith("/api/sc/"):
            return self.ponte("POST")
        u = urlparse(self.path); path = u.path; q = {k: v[0] for k, v in parse_qs(u.query).items()}
        tam = int(self.headers.get("Content-Length", 0))
        if path == "/api/editor/upload":  # corpo = bytes do arquivo
            d = pasta_video(q["aba"], q["pasta"]); n = int(q["cena"])
            ext = os.path.splitext(q.get("nome", "x.png"))[1].lower()
            if ext not in EXT_VIS:
                return self.send(200, {"erro": "formato nao aceito"})
            corpo = self.rfile.read(tam)
            trocar_visual(d, n, ext, corpo)
            return self.send(200, {"ok": True})
        dados = json.loads(self.rfile.read(tam) or "{}")
        if path == "/api/mover":
            de, para = PASTAS.get(dados["de"]), PASTAS.get(dados["para"])
            nome = os.path.basename(dados["pasta"])
            if not (de and para and os.path.isdir(os.path.join(de, nome))):
                return self.send(200, {"erro": "Video nao encontrado"})
            destino, k = os.path.join(para, nome), 2
            while os.path.exists(destino):
                destino, k = os.path.join(para, f"{nome}_{k}"), k + 1
            try:
                os.rename(os.path.join(de, nome), destino)
            except OSError:
                return self.send(200, {"erro": "O Windows bloqueou: feche a pasta do video no Explorer e pause o video no navegador, depois tente de novo."})
            return self.send(200, {})
        if path == "/api/excluir":  # exclusao definitiva: so a partir de Rejeitados
            if dados.get("aba") != "Rejeitados":
                return self.send(200, {"erro": "So e possivel excluir definitivamente videos da aba Rejeitados."})
            d = pasta_video("Rejeitados", dados["pasta"])
            try:
                shutil.rmtree(d)
            except OSError:
                return self.send(200, {"erro": "O Windows bloqueou: feche a pasta do video no Explorer e pause o video, depois tente de novo."})
            return self.send(200, {"ok": True})
        if path == "/api/youtube":  # envia pela fila (upload pode demorar); publicar_em opcional = agendado
            d = pasta_video("Aprovados", dados["pasta"]); r = ler_rot(d)
            quando = (dados.get("publicar_em") or "").strip()
            r["agenda"] = {"publicar_em": quando or None, "status": "enviando"}; salvar_rot(d, r)
            FILA.add("upload", f"{'Agendar' if quando else 'Enviar'} no YouTube: {r.get('titulo','')[:50]}",
                     ["youtube.py", "enviar", d, quando], 120)
            return self.send(200, {"ok": True})
        if path == "/api/sc_importar":  # video pronto do SupoClip -> Para aprovar
            import supoclip
            return self.send(200, {"pasta": supoclip.importar(dados["id"], PASTAS["Para_Aprovar"])})
        if path == "/api/sugerir_temas":  # so quando o usuario clica (usa 1 chamada da cota gratis)
            sys.path.insert(0, BASE)
            import seo
            feitos = [os.path.basename(x)[16:].replace("_", " ") for k in PASTAS.values() for x in os.listdir(k)][:40]
            return self.send(200, {"sugestoes": seo.sugerir_temas(dados.get("tema_canal", ""), dados.get("nome", ""), feitos)})
        if path == "/api/publicacao/preparar":  # IA escreve titulo/descricao/tags (usa cota gratis do Gemini)
            d = pasta_video(dados["aba"], dados["pasta"]); r = ler_rot(d)
            sys.path.insert(0, BASE)
            import seo
            r["publicacao"] = {**(r.get("publicacao") or {}), **seo.gerar(r)}; salvar_rot(d, r)  # seo.gerar tambem grava r["thumb"]["opcoes"]
            return self.send(200, r["publicacao"])
        if path == "/api/miniatura":  # redesenha a miniatura com outro texto (rapido, sem IA)
            d = pasta_video(dados["aba"], dados["pasta"]); r = ler_rot(d)
            th = r.get("thumb") or {}
            th.update({"texto": dados.get("texto") or th.get("texto"), "destaque": dados.get("destaque") or th.get("destaque"),
                       "selo": dados.get("selo", th.get("selo", ""))})
            r["thumb"] = th; salvar_rot(d, r)
            sys.path.insert(0, BASE)
            import gerar_video as g
            W, H = (1080, 1920) if r.get("tela") == "9:16" else (1920, 1080)
            g.miniatura(r, d, W, H)
            return self.send(200, {"ok": True})
        if path == "/api/publicacao/salvar":
            d = pasta_video(dados["aba"], dados["pasta"]); r = ler_rot(d)
            pub = r.get("publicacao") or {}
            pub.update({k: dados[k] for k in ("titulo", "descricao", "tags", "para_criancas", "conteudo_ia", "visibilidade") if k in dados})
            r["publicacao"] = pub
            if "publicar_em" in dados:
                r["agenda"] = {**(r.get("agenda") or {}), "publicar_em": dados["publicar_em"] or None}
            salvar_rot(d, r)
            return self.send(200, {"ok": True})
        if path == "/api/abrir_imagens":
            d = os.path.join(pasta_video(dados["aba"], dados["pasta"]), "imagens")
            os.makedirs(d, exist_ok=True)
            os.startfile(d)
            return self.send(200, {})
        if path == "/api/auto_imagens":
            d = pasta_video(dados["aba"], dados["pasta"])
            FILA.add("imagens", f"Buscar imagens: {os.path.basename(d)[:40]}", ["imagens_auto.py", d], 30)
            return self.send(200, {})
        if path == "/api/remontar":
            d = pasta_video(dados["aba"], dados["pasta"])
            if dados.get("imagens_ia"):  # troca as imagens por imagens geradas no PC a partir da historia
                n = len(ler_rot(d).get("cenas", []))
                FILA.add("imagens_ia", f"Imagens da história (PC): {ler_rot(d).get('titulo', '')[:45]}",
                         ["gerar_video.py", "--refazer", d, "--imagens-ia"], max(90, n * 6 + 30))
                return self.send(200, {})
            FILA.add("remontar", f"Remontar: {ler_rot(d).get('titulo', '')[:50]}", ["gerar_video.py", "--refazer", d], 90)
            return self.send(200, {})
        if path == "/api/regenerar":
            d = pasta_video(dados["aba"], dados["pasta"]); r = ler_rot(d)
            cfg = dict(r.get("config") or {"modo": r.get("formato", "longo")})
            cfg["titulo"] = ""  # nova historia
            return self.send(200, enfileirar(cfg, 1))
        if path == "/api/gerar":
            return self.send(200, enfileirar(dados.get("config", {}), max(1, min(5, int(dados.get("qtd", 1))))))
        if path == "/api/fila/cancelar":
            FILA.cancelar(dados["id"]); return self.send(200, {})
        if path == "/api/fila/repetir":
            FILA.repetir(dados["id"]); return self.send(200, {})
        if path == "/api/fila/limpar":
            with FILA.lock:
                FILA.jobs = [j for j in FILA.jobs if j["status"] in ("na_fila", "rodando")]; FILA.salvar()
            return self.send(200, {})
        if path == "/api/editor/salvar":
            d = pasta_video(dados["aba"], dados["pasta"]); r = ler_rot(d)
            if dados.get("titulo"): r["titulo"] = dados["titulo"]
            if "descricao" in dados: r["descricao"] = dados["descricao"]
            for i, c in enumerate(dados.get("cenas", [])):
                if i < len(r["cenas"]):
                    r["cenas"][i].update({k: c[k] for k in ("narracao", "imagem", "voz", "camera", "busca") if k in c})
            if dados.get("excluir") is not None:  # remove uma cena e renumera imagens
                remover_cena(d, r, int(dados["excluir"]))
            salvar_rot(d, r)
            return self.send(200, {"ok": True})
        if path == "/api/editor/buscar":  # nova foto gratis para UMA cena
            d = pasta_video(dados["aba"], dados["pasta"]); n = int(dados["cena"]); r = ler_rot(d)
            sys.path.insert(0, BASE)
            import imagens_auto, requests
            usados = set(dados.get("pular", []))
            res = imagens_auto.buscar(dados.get("busca") or r["cenas"][n - 1].get("busca") or "dark", usados)
            if not res:
                return self.send(200, {"erro": "Nenhuma imagem encontrada para essa busca. Tente outras palavras (em ingles)."})
            img = requests.get(res[0], headers=imagens_auto.UA, timeout=40); img.raise_for_status()
            trocar_visual(d, n, ".jpg", img.content)
            with open(os.path.join(d, "imagens", "CREDITOS.txt"), "a", encoding="utf-8") as fh:
                fh.write(f"cena{n:02d}: {res[1]}\n")
            return self.send(200, {"ok": True})
        self.send(404, {"erro": "rota desconhecida"})


def trocar_visual(d, n, ext, corpo):
    pi = os.path.join(d, "imagens"); os.makedirs(pi, exist_ok=True)
    antigas = os.path.join(pi, "_substituidas"); os.makedirs(antigas, exist_ok=True)
    for f in os.listdir(pi):  # guarda a anterior em vez de apagar
        if re.match(rf"cena0*{n}\.", f.lower()):
            os.replace(os.path.join(pi, f), os.path.join(antigas, f"{time.strftime('%H%M%S')}_{f}"))
    open(os.path.join(pi, f"cena{n:02d}{ext}"), "wb").write(corpo)


def remover_cena(d, r, n):
    r["cenas"].pop(n - 1)
    pi = os.path.join(d, "imagens"); vis = visuais(d)
    if n in vis:
        os.makedirs(os.path.join(pi, "_substituidas"), exist_ok=True)
        os.replace(os.path.join(pi, vis[n]), os.path.join(pi, "_substituidas", f"removida_{vis[n]}"))
    for k in sorted(x for x in vis if x > n):
        f = vis[k]; os.replace(os.path.join(pi, f), os.path.join(pi, f"cena{k-1:02d}{os.path.splitext(f)[1]}"))


def enfileirar(cfg, qtd):
    nome_modo = {"short": "Short", "longo": "Video longo", "novela": "Novela"}.get(cfg.get("modo"), "Video")
    dur = int(cfg.get("duracao") or 0)
    timeout = max(60, int(dur / 60 * 10) + 60) if dur else 180  # folga: ~1 min/cena no pior caso (15 min -> 210 min)
    if cfg.get("modo") == "mapa":  # desenho quadro a quadro no processador: ~20-25 min de PC por minuto de video
        timeout = max(60, int(dur / 60 * 30) + 60)
    if cfg.get("modo") == "novela":
        timeout *= max(1, int(cfg.get("partes", 5)))
    ids = []
    for i in range(qtd):
        arq = os.path.join(JOBS_DIR, f"cfg_{uuid.uuid4().hex[:8]}.json")
        json.dump(cfg, open(arq, "w", encoding="utf-8"), ensure_ascii=False)
        titulo = f"{nome_modo}: {cfg.get('titulo') or cfg.get('tema') or 'tema livre'}"[:80]
        ids.append(FILA.add("gerar", titulo, ["gerar_video.py", "--config", arq], timeout)["id"])
    return {"ids": ids}


if __name__ == "__main__":
    FILA = Fila()
    print("Painel aberto em http://localhost:8765  (feche esta janela para parar)")
    if "--sem-navegador" not in sys.argv:
        webbrowser.open("http://localhost:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()

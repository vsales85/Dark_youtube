"""Dark Studio - gerador de videos.
Uso (compativel com versoes anteriores):
  python gerar_video.py ["tema"]                      video longo 16:9
  python gerar_video.py --short ["tema"]              Short 9:16
  python gerar_video.py --novela N ["tema"]           novela em N partes (Shorts)
  python gerar_video.py --duracao SEG ...             duracao alvo
  python gerar_video.py --refazer <pasta>             remonta (reaproveita roteiro, sem custo de texto)
  python gerar_video.py --config arquivo.json         todas as opcoes do painel (ver CONFIG_PADRAO)
Saida: Para_Aprovar/<data>_<titulo>/ video.mp4, miniatura.jpg, roteiro.json, imagens/
"""
import json, os, re, subprocess, sys, wave, datetime, asyncio, random, time, shutil
from dotenv import load_dotenv
from google import genai
from google.genai import types
import imageio_ffmpeg, edge_tts, requests
import custos

load_dotenv()
BASE = os.path.dirname(os.path.abspath(__file__))
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                      http_options=types.HttpOptions(timeout=180_000))  # 3 min por chamada, nunca trava
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
MODELOS_TEXTO = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.1-flash-lite"]  # o que falhar vai pro fim
MODELO_IMAGEM = os.environ.get("MODELO_IMAGEM", "gemini-2.5-flash-image")

# ---------------------------------------------------------------- configuracao
TELAS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}

VOZES = {  # Edge TTS (gratis). So existe 1 voz masculina PT-BR; variamos tom/velocidade para diferenciar personagens
    "radialista": ("pt-BR-AntonioNeural", "-16Hz", -12),   # locutor de radio mais velho, grave e pausado
    "narrador_grave": ("pt-BR-AntonioNeural", "-8Hz", -6),
    "masculina": ("pt-BR-AntonioNeural", "+0Hz", 0),
    "homem_velho": ("pt-BR-AntonioNeural", "-14Hz", -10),
    "homem_jovem": ("pt-BR-AntonioNeural", "+8Hz", 4),
    "feminina": ("pt-BR-FranciscaNeural", "+0Hz", 0),
    "mulher_jovem": ("pt-BR-ThalitaMultilingualNeural", "+0Hz", 2),
    "mulher_velha": ("pt-BR-FranciscaNeural", "-10Hz", -8),
    "crianca": ("pt-BR-ThalitaMultilingualNeural", "+18Hz", 5),
    "antonio_grave": ("pt-BR-AntonioNeural", "-6Hz", -6),  # mais grave sem filtro de radio
    "andrew": ("en-US-AndrewMultilingualNeural", "+0Hz", -4),  # vozes multilingues falando portugues
    "brian": ("en-US-BrianMultilingualNeural", "+0Hz", -4),
    "william": ("en-AU-WilliamMultilingualNeural", "+0Hz", -4),
    "ava": ("en-US-AvaMultilingualNeural", "+0Hz", -4),
    "emma": ("en-US-EmmaMultilingualNeural", "+0Hz", -4),
}

TEMAS_CANAL = {
    "misterio": {"nome": "Mistérios e suspense", "voz": "antonio_grave", "ambiente": "suspense",
                 "estilo": "dark moody cinematic still, low-key lighting, deep shadows, teal and amber palette, 35mm film grain, shallow depth of field",
                 "roteiro": "Narrador em terceira pessoa, tom de documentario de misterio, perguntas que intrigam, pistas e revelacoes graduais."},
    "terror": {"nome": "Terror e lendas urbanas", "voz": "antonio_grave", "ambiente": "terror",
               "estilo": "supernatural horror cinematic still, fog, cold desaturated colors, harsh contrast, flickering fluorescent light, film grain, unsettling composition",
               "roteiro": "Suspense sobrenatural crescente, atmosfera opressiva, sustos sugeridos e nunca violencia grafica. Ficcao inspirada em lendas, deixe claro que e adaptacao."},
    "novela": {"nome": "Novelas e dramas", "voz": "feminina", "ambiente": "drama",
               "estilo": "dramatic telenovela cinematic still, warm practical lighting, emotional close-ups, rich colors, soft film grain",
               "roteiro": "Drama familiar em primeira pessoa, emocao real, dialogos curtos entre aspas, segredos e reviravoltas."},
    "relatos": {"nome": "Histórias reais (dramatizadas)", "voz": "masculina", "ambiente": "drama",
                "estilo": "realistic cinematic still, natural light, documentary realism, muted colors",
                "roteiro": "Relato dramatizado em primeira pessoa, coloquial, verossimil. Ficcao inspirada em situacoes reais, sem pessoas reais."},
    "civilizacoes": {"nome": "Civilizações perdidas", "voz": "narrador_grave", "ambiente": "epico",
                     "estilo": "epic ancient civilization matte painting, golden hour, volumetric light, dust, monumental scale, cinematic",
                     "roteiro": "Documentario narrado, fatos historicos corretos e teorias claramente marcadas como teorias, tom de descoberta."},
    "ciencia": {"nome": "Ciência e universo", "voz": "narrador_grave", "ambiente": "espaco",
                "estilo": "cinematic space scene, nebula, deep cosmos, scientific realism, high detail, awe inspiring",
                "roteiro": "Divulgacao cientifica envolvente, fatos corretos, comparacoes faceis, sensacao de assombro."},
    "curiosidades": {"nome": "Curiosidades", "voz": "masculina", "ambiente": "leve",
                     "estilo": "vivid cinematic photo, bright clean lighting, high detail",
                     "roteiro": "Ritmo rapido, fatos surpreendentes e verdadeiros, ganchos a cada poucos segundos."},
    "historia": {"nome": "História em mapas: impérios perdidos, guerras, mistérios e curiosidades", "voz": "gemini:Charon", "ambiente": "epico",
                 "estilo": "", "roteiro": "Historia real do Brasil e do mundo, alternando 4 tipos: reinos e imperios perdidos, guerras e soldados, misterios da historia (enigmas e desaparecimentos, separando fato de teoria) e curiosidades de geografia (fronteiras, mapas que mudaram). Fatos conferidos, tom de descoberta."},
    "personalizado": {"nome": "Personalizado", "voz": "masculina", "ambiente": "suspense",
                      "estilo": "cinematic still, dramatic lighting, film grain", "roteiro": ""},
}

CENAS_POR_DURACAO = os.path.join(BASE, "cenas_por_duracao.json")
TABELA_CENAS_PADRAO = [[15, 3, 4], [30, 5, 6], [35, 5, 7], [60, 8, 12], [120, 14, 20],
                       [300, 30, 38], [600, 52, 62], [1200, 95, 115], [1800, 140, 165], [3600, 260, 300]]

CONFIG_PADRAO = {"tema_canal": "relatos", "tema": "", "titulo": "", "sinopse": "", "estilo": "",
                 "modo": "longo", "visual": "cinematografico", "qualidade": "cinematografico", "tela": None, "duracao": None, "cenas": None, "partes": 5,
                 "voz": None, "vozes_personagens": True, "falas": False, "velocidade": 0, "idioma": "pt-BR",
                 "producao": "economico", "musica": True, "orcamento_brl": 0, "imagens": "local"}
CFG = dict(CONFIG_PADRAO)


def tela():
    t = CFG["tela"] or ("9:16" if CFG["modo"] in ("short", "novela") else "16:9")
    return t, TELAS[t]


def tema_canal():
    return TEMAS_CANAL.get(CFG["tema_canal"], TEMAS_CANAL["relatos"])


def tamanho():
    """Palavras e cenas para a duracao. Tabela editavel em cenas_por_duracao.json."""
    curto = CFG["modo"] in ("short", "novela")
    seg = CFG["duracao"] or (55 if curto else 600)
    wps = (2.8 if curto else 2.5) * (1 + CFG["velocidade"] / 100)
    if not os.path.exists(CENAS_POR_DURACAO):
        json.dump(TABELA_CENAS_PADRAO, open(CENAS_POR_DURACAO, "w"), indent=1)
    tab = json.load(open(CENAS_POR_DURACAO))
    lo, hi = next(((a, b) for s, a, b in tab if seg <= s), (tab[-1][1] * seg // tab[-1][0], tab[-1][2] * seg // tab[-1][0]))
    if CFG["cenas"]:
        lo = hi = int(CFG["cenas"])
    p = seg * wps
    return {"seg": seg, "pmin": int(p * 0.95), "pmax": int(p * 1.05), "cmin": lo, "cmax": hi}


# ---------------------------------------------------------------- IA de texto
def modelo_por_memoria():
    """PC com pouca memoria usa modelo menor (14B precisa de ~10 GB; 7B ~5 GB; 3B ~2,5 GB)."""
    try:
        import ctypes
        class M(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("c", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("livre", ctypes.c_ulonglong),
                        ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong), ("f", ctypes.c_ulonglong)]
        m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        gb = m.total / 2 ** 30
    except Exception:
        gb = 16
    return "qwen2.5:14b" if gb >= 24 else "qwen2.5:7b" if gb >= 12 else "qwen2.5:3b"


def ollama_json(prompt, etapa):
    """Reserva AUTOMATICA: escreve com o Ollama no proprio PC (gratis, sem limite, sem internet).
    Descarrega o modelo da placa logo depois (keep_alive=0) para nao disputar com o gerador de imagens."""
    import requests, config
    url = config._env("OLLAMA_URL", "http://localhost:11434")
    modelo = config._env("OLLAMA_MODELO") or modelo_por_memoria()
    try:
        requests.get(f"{url}/api/version", timeout=3)
    except Exception:  # liga o Ollama se estiver instalado e desligado
        exe = config._env("OLLAMA_EXE", os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"))
        if not os.path.exists(exe):
            raise RuntimeError("Ollama nao instalado")
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(6)
    print(f"   usando o Ollama ({modelo}) no PC para escrever...", flush=True)
    r = requests.post(f"{url}/api/chat", timeout=900, json={
        "model": modelo, "stream": False, "format": "json", "keep_alive": 0,
        "options": {"temperature": 0.8, "num_ctx": 16384},
        "messages": [{"role": "system", "content": "Responda SOMENTE com JSON valido, em portugues do Brasil. Seja fiel aos fatos historicos."},
                     {"role": "user", "content": prompt}]})
    r.raise_for_status()
    custos_registro = {"modelo": f"ollama:{modelo}", "etapa": etapa}
    try:
        custos.registrar(f"ollama:{modelo}", None, etapa=etapa)
    except Exception:
        pass
    return json.loads(r.json()["message"]["content"])


def pedir_json(prompt, etapa):
    inicio = time.time()
    for rodada in range(3):
        if rodada >= 1 or time.time() - inicio > 240:  # Gemini falhou/demorou: tenta o Ollama no PC antes de esperar mais
            try:
                return ollama_json(prompt, etapa)
            except Exception as e:
                print(f"   ! Ollama indisponivel ({str(e)[:70]}) - voltando a tentar o Gemini", flush=True)
        for m in list(MODELOS_TEXTO):
            try:
                r = client.models.generate_content(
                    model=m, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.95))
                custos.registrar(m, r, etapa=etapa)
                return json.loads(r.text)
            except Exception as e:
                print(f"   ! {m} ocupado/indisponivel - tentando outro...")
                if m in MODELOS_TEXTO and len(MODELOS_TEXTO) > 1:  # nao insiste no modelo sobrecarregado
                    MODELOS_TEXTO.remove(m); MODELOS_TEXTO.append(m)
        time.sleep(15)
    raise SystemExit("Nenhum modelo de texto disponivel agora. Tente mais tarde.")


def contexto():
    tc = tema_canal()
    partes = [f"GENERO DO CANAL: {tc['nome']}. {tc['roteiro']}"]
    if CFG["tema"]: partes.append(f"TEMA: {CFG['tema']}")
    if CFG["titulo"]: partes.append(f"TITULO DEFINIDO: {CFG['titulo']} (use exatamente este titulo)")
    if CFG["sinopse"]: partes.append(f"SINOPSE/ESTRUTURA OBRIGATORIA (siga a risca, inclusive tempos de cada bloco):\n{CFG['sinopse']}")
    if not CFG["tema"] and not CFG["sinopse"]: partes.append("TEMA: escolha um tema original e forte para este genero.")
    partes.append("""PRIMEIROS 30 SEGUNDOS (decidem a retencao - mapa usado pelos canais de terror que mais retem):
- 0-3s: COMECE NA ACAO, no momento mais perturbador (cold open). Nada de "ola", "neste video", "bem-vindos", nada de contexto.
- ~8s: uma PISTA/EVIDENCIA nova e concreta (um objeto, um som, uma data, um nome).
- ~16s: uma VIRADA de clima ou de som (silencio repentino, batida, sussurro) - indique no campo "som".
- ~24s: uma CONTRADICAO que o espectador precisa ver resolvida ("so que ela tinha morrido em 1987").
- ~30s: a PROMESSA clara do que sera revelado ate o final.
DEPOIS: uma quebra de padrao a cada 20-40s (revelacao, mudanca de lugar, dialogo, som) e um novo gancho a cada 1-2 min.
Frases curtas. Linguagem falada. Use reticencias para pausas dramaticas de locutor.
ORIGINALIDADE: historia 100% original (estruturas de sucesso sim; nunca copie roteiros, falas ou titulos de outros canais).""")
    if tema_canal()["voz"] == "radialista" and not CFG["voz"] or CFG["voz"] == "radialista":
        partes.append("TOM: narrador de radio a meia-noite, voz de locutor experiente que conta o caso com calma e suspense; "
                      "pode se dirigir ao ouvinte ('voce que esta ouvindo...') DEPOIS dos primeiros 30 segundos.")
    if CFG.get("falas"):
        partes.append("""MINI-HISTORIA COM FALAS (obrigatorio): os PERSONAGENS contam a historia conversando entre si.
- Pelo menos 60% das cenas sao FALAS de personagens; o narrador aparece pouco (abertura, transicoes, fecho).
- Em cena de fala, "narracao" contem SOMENTE o que o personagem diz, em primeira pessoa, sem aspas e sem "ele disse".
- "voz" = o NOME EXATO do personagem que fala (ou "narrador"). Uma pessoa fala por cena; alterne os personagens.
- 2 a 3 personagens no maximo, com vozes contrastantes (ex: homem e mulher, jovem e idoso).
- Dialogo natural, frases curtas, reacoes ("O que foi isso?", "Nao abre essa porta!"), gancho forte e final com reviravolta.""")
    partes.append(f"IDIOMA DA NARRACAO: {CFG['idioma']}. Regras: sem violencia grafica, sem pessoas reais, coerencia total, nada aleatorio.")
    return "\n".join(partes)


CENA_JSON = """{{"narracao": "texto falado (1 a 2 frases, ~8-12 segundos; use ... para pausas dramaticas)",
   "personagens": ["nomes EXATOS dos personagens que aparecem na imagem desta cena (vazio se nenhum)"],
   "voz": "quem fala nesta cena: narrador OU o NOME EXATO do personagem que fala (ou um tipo: masculina | homem_velho | homem_jovem | feminina | mulher_jovem | mulher_velha | crianca)",
   "camera": "zoom_in | zoom_out | pan_esq | pan_dir | sobe | desce | tremor",
   "som": "efeito sonoro/ambiente sugerido",
   "busca": "2 a 3 palavras EM INGLES para banco de imagens",
   "imagem": "prompt EM INGLES que mostre EXATAMENTE o que a narracao desta cena conta: quem (pelo nome), onde, fazendo o que, enquadramento (close/plano medio/plano geral), angulo e luz. Cinematografico. Sem texto na imagem"}}"""


def gerar_roteiro_simples(t):
    return pedir_json(f"""Voce e roteirista de um canal dark brasileiro de alta retencao.
{contexto()}
Escreva UMA historia completa. {t['pmin']} a {t['pmax']} palavras no total (cerca de {t['seg']} segundos narrada) - conte as palavras.
A PRIMEIRA frase e o gancho mais forte. Divida em {t['cmin']} a {t['cmax']} cenas (podem ter tamanhos diferentes).
Responda SOMENTE JSON:
{{"titulo": "max 70 caracteres, magnetico", "descricao": "3 linhas sem spoiler + 5 hashtags",
  "personagens": [{{"nome": "", "voz": "", "aparencia_en": "descricao fisica fixa em ingles"}}],
  "cenas": [{CENA_JSON}]}}""", "roteiro")


def gerar_roteiro_blocos(t):
    """Videos longos: primeiro o plano com blocos de tempo, depois cada bloco -> duracao bem mais precisa."""
    print("   planejando estrutura...")
    n_blocos = max(3, round(t["seg"] / 75))
    plano = pedir_json(f"""Voce e roteirista-chefe de um canal dark brasileiro de alta retencao.
{contexto()}
Planeje UM video de {t['seg']} segundos dividido em {n_blocos} blocos (ou nos blocos da sinopse, se houver).
Defina personagens com aparencia FIXA (para manter consistencia visual) e as pistas/reviravoltas.
Responda SOMENTE JSON:
{{"titulo": "max 70 caracteres", "descricao": "3 linhas sem spoiler + 5 hashtags",
  "personagens": [{{"nome": "", "papel": "", "voz": "masculina|homem_velho|homem_jovem|feminina|mulher_jovem|mulher_velha|crianca", "aparencia_en": ""}}],
  "blocos": [{{"titulo": "", "inicio_s": 0, "fim_s": 60, "objetivo": "o que acontece e qual pista/gancho"}}],
  "final": "a reviravolta final"}}""", "plano")
    cenas, feito = [], []
    total_cenas = (t["cmin"] + t["cmax"]) / 2
    for i, b in enumerate(plano["blocos"], 1):
        seg = max(15, b["fim_s"] - b["inicio_s"])
        palavras = int(seg * t["pmin"] / t["seg"] * 1.03)
        nc = max(2, round(total_cenas * seg / t["seg"]))
        print(f"   bloco {i}/{len(plano['blocos'])}: {b['titulo']} ({seg}s)")
        r = pedir_json(f"""Voce escreve o bloco {i} de {len(plano['blocos'])} do video "{plano['titulo']}".
{contexto()}
PERSONAGENS (aparencia fixa, use igual nos prompts de imagem): {json.dumps(plano['personagens'], ensure_ascii=False)}
PLANO COMPLETO: {json.dumps(plano['blocos'], ensure_ascii=False)}
FINAL PLANEJADO: {plano.get('final', '')}
JA NARRADO ATE AQUI (continue sem repetir): {' | '.join(feito[-3:]) or 'nada, este e o inicio'}
ESTE BLOCO: {b['titulo']} - {b['objetivo']}
Escreva EXATAMENTE cerca de {palavras} palavras de narracao (bloco de {seg} segundos), em {nc} cenas.
{"Comece com um gancho impactante." if i == 1 else "Continue de onde parou, sem recapitular."}
{"Feche a historia com a reviravolta e uma pergunta ao publico." if i == len(plano['blocos']) else "Termine o bloco com tensao para o proximo."}
Responda SOMENTE JSON: {{"resumo": "2 frases do que aconteceu", "cenas": [{CENA_JSON}]}}""", "roteiro")
        cenas += r["cenas"]
        feito.append(r.get("resumo", ""))
    return {"titulo": CFG["titulo"] or plano["titulo"], "descricao": plano["descricao"],
            "personagens": plano["personagens"], "plano": plano["blocos"], "cenas": cenas}


def gerar_novela(n, t):
    return pedir_json(f"""Voce e roteirista de uma NOVELA EM PARTES para um canal dark brasileiro.
{contexto()}
Crie UMA historia dividida em EXATAMENTE {n} PARTES. Planeje tudo antes: personagens com aparencia fixa,
segredo central, pistas e uma reviravolta final coerente.
Cada parte: {t['pmin']} a {t['pmax']} palavras (~{t['seg']}s), {t['cmin']} a {t['cmax']} cenas.
Parte 1 abre com o gancho mais forte. Da parte 2 em diante, primeira frase = recapitulacao relampago (max 12 palavras).
Toda parte menos a ultima termina em CLIFFHANGER com "Continua na parte X.". A ultima entrega a reviravolta e pede comentarios.
Responda SOMENTE JSON:
{{"serie": "max 40 caracteres", "personagens": [{{"nome": "", "voz": "", "aparencia_en": ""}}],
  "partes": [{{"titulo": "max 60 caracteres, termina com (Parte N)", "descricao": "2 linhas + 3 hashtags",
              "cenas": [{CENA_JSON}]}}]}}""", "novela")


# ---------------------------------------------------------------- voz
VOZ_CLONE_URL = os.environ.get("VOZ_CLONE_URL", "http://localhost:3900")


def vozes_clonadas():
    """Vozes do servico de clonagem (SupoClip / Chatterbox, local, licenca MIT). Vazio se o servico estiver desligado."""
    try:
        import requests
        return requests.get(f"{VOZ_CLONE_URL}/v1/audio/voices", timeout=3).json().get("data", [])
    except Exception:
        return []


def voz_clonada(texto, mp3, voz_id, expressao=None):
    import requests
    r = requests.post(f"{VOZ_CLONE_URL}/v1/audio/speech", timeout=1800,
                      json={"voice": voz_id, "input": texto, **({"exaggeration": expressao} if expressao else {})})
    r.raise_for_status()
    open(mp3, "wb").write(r.content)


VOZ_CAIU = False


def gerar_voz(texto, arquivo, quem, expressao=None):
    chave = CFG["voz"] or tema_canal()["voz"]
    if CFG["vozes_personagens"] and quem and quem != "narrador" and (quem in VOZES or str(quem).startswith(("clone:", "gemini:"))):
        chave = quem
    mp3 = arquivo + ".mp3"
    if str(chave).startswith(("clone:", "gemini:")):  # Gemini TTS (direto pela chave) ou voz clonada local
        try:
            import voz as vozes
            vozes.falar(texto, chave, mp3)
        except Exception as e:
            print(f"   ! voz {chave} indisponivel ({str(e)[:60]}) - usando Antonio")
            global VOZ_CAIU
            VOZ_CAIU = True
            chave = "masculina"
            if os.path.exists(mp3): os.remove(mp3)
    voz, pitch, rate = VOZES.get(chave, VOZES["masculina"])
    rate += CFG["velocidade"] + (8 if CFG["modo"] in ("short", "novela") else 0)
    for tentativa in range(3 if not os.path.exists(mp3) else 0):
        try:
            asyncio.run(edge_tts.Communicate(texto, voz, rate=f"{rate:+d}%", pitch=pitch).save(mp3))
            break
        except Exception as e:
            print(f"   ! voz falhou ({str(e)[:50]}), tentando de novo")
            time.sleep(3)
    pausa = 0.6 if texto.rstrip().endswith(("...", "?", "!")) else 0.25
    radio = ""
    if chave in ("radialista", "narrador_grave"):  # timbre de locutor: grave encorpado, presenca e compressao de radio
        radio = ("highpass=f=55,equalizer=f=110:t=q:w=1:g=6,equalizer=f=250:t=q:w=1:g=2,"
                 "equalizer=f=3200:t=q:w=1.4:g=2.5,acompressor=threshold=0.08:ratio=4:attack=8:release=180:makeup=2,")
    ff(["-i", os.path.basename(mp3), "-af", f"{radio}apad=pad_dur={pausa}", "-ar", "24000", "-ac", "1",
        os.path.basename(arquivo)], os.path.dirname(arquivo))
    os.remove(mp3)
    with wave.open(arquivo) as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- imagens
def pode_gastar(usd):
    lim = float(CFG.get("orcamento_brl") or 0)
    if lim <= 0:
        return True  # sem limite definido (no nivel gratuito o Google recusa sem cobrar)
    return (custos.sessao_usd + usd) * custos.precos()["cotacao_usd_brl"] <= lim


def gerar_imagem(prompt, arquivo):
    if not MODELO_IMAGEM or not pode_gastar(0.04):
        return False
    proporcao = tela()[0]
    try:
        r = client.models.generate_content(
            model=MODELO_IMAGEM, contents=prompt,
            config=types.GenerateContentConfig(image_config=types.ImageConfig(aspect_ratio=proporcao)))
        for p in r.candidates[0].content.parts:
            if p.inline_data:
                custos.registrar(MODELO_IMAGEM, r, imagens=1, etapa="imagem")
                open(arquivo, "wb").write(p.inline_data.data)
                return True
    except Exception as e:
        print(f"   ! imagem IA indisponivel ({str(e)[:60]})")
    return False


def baixar_pixabay_video(busca, arquivo, usados):
    chave = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not chave:
        return False
    for q in (busca, busca.split()[0]):
        try:
            r = requests.get("https://pixabay.com/api/videos/", timeout=20,
                             params={"key": chave, "q": q, "per_page": 20, "safesearch": "true"}).json()
            for v in r.get("hits", []):
                f = v["videos"].get("medium") or v["videos"].get("small")
                if v["id"] in usados or not f or not f.get("url"):
                    continue
                with requests.get(f["url"], stream=True, timeout=60) as d, open(arquivo, "wb") as fh:
                    for c in d.iter_content(1 << 16):
                        fh.write(c)
                usados.add(v["id"])
                return True
        except Exception as e:
            print(f"   ! pixabay: {str(e)[:60]}")
    return False


def prompt_imagem(c, rot):
    """Prompt = cena da narracao + ficha FIXA de cada personagem presente + estilo fixo do video."""
    estilo = CFG["estilo"] or tema_canal()["estilo"]
    fichas = {p.get("nome", "").strip().lower(): p.get("aparencia_en", "") for p in rot.get("personagens", []) if p.get("nome")}
    cena = c.get("imagem", "")
    presentes = [n for n in (c.get("personagens") or []) if n.strip().lower() in fichas]
    presentes += [n for n in fichas if n and n in cena.lower() and n not in [x.lower() for x in presentes]]
    desc = "; ".join(f"{n} = {fichas[n.strip().lower()]}" for n in presentes if fichas.get(n.strip().lower()))
    v = VISUAIS.get(CFG.get("visual") or (rot.get("config") or {}).get("visual") or "cinematografico", VISUAIS["cinematografico"])
    return (f"{cena}. " + (f"Characters (keep exactly this appearance): {desc}. " if desc else "") +
            f"{v[0]}, {estilo}, {v[1]}. No text, no watermark.")


# estilo visual das imagens (escolhido no painel)
VISUAIS = {
    "cinematografico": ("Cinematic film still", "anamorphic lens, natural skin texture, soft film grain, realistic, subtle color grading"),
    "hiper_realista": ("RAW photo, ultra realistic photograph", "shot on Sony A7 IV 50mm, natural light, real skin pores, sharp focus, true-to-life colors"),
    "fantasia": ("Dark fantasy digital artwork", "epic painterly concept art, magical atmosphere, glowing light, intricate detail"),
    "pintura": ("Oil painting illustration", "visible brush strokes, dramatic chiaroscuro, classical painting style"),
    "noir": ("Black and white film noir still", "high contrast monochrome, hard shadows, 1940s cinema, grainy film"),
    "vintage": ("1970s analog film photo", "faded kodak colors, light leaks, heavy grain, retro atmosphere"),
    # documentario em desenho (estilo LoRA "cartoon", licenca MIT) - caricatura, contorno preto, cores chapadas
    "cartoon_doc": ("2d cartoon illustration, editorial caricature, thick black outlines, flat cel colors",
                    "big heads and thin legs, expressive faces, detailed illustrated background, documentary animation style"),
}


def semente(c, rot, i):
    """Mesma semente para as cenas com os mesmos personagens -> rostos/roupas mais parecidos."""
    import zlib
    nomes = sorted(n.strip().lower() for n in (c.get("personagens") or []))
    base = "|".join(nomes) if nomes else f"{rot.get('titulo','')}#{i}"
    return zlib.crc32(base.encode()) % 2**31


def lote_local(cenas, rot, pasta, forcar=False):
    """Gera no PC, num lote so (texto -> imagens -> decodificar), todas as cenas que ainda nao tem visual."""
    if CFG.get("imagens", "local") != "local" or CFG["producao"] == "manual":
        return 0
    try:
        import imagem_local
        if not imagem_local.disponivel():
            return 0
    except Exception:
        return 0
    dest = os.path.join(pasta, "imagens"); os.makedirs(dest, exist_ok=True)
    existentes = {os.path.splitext(f)[0].lower() for f in os.listdir(dest)}
    pedidos = [{"prompt": prompt_imagem(c, rot), "saida": os.path.join(dest, f"cena{i+1:02d}.png"),
                "proporcao": tela()[0], "seed": semente(c, rot, i),
                 **({"lora": "cartoon", "rosto": False} if (CFG.get("visual") or "") == "cartoon_doc" else {}),
                 "qualidade": CFG.get("qualidade") or "cinematografico"}
               for i, c in enumerate(cenas) if forcar or f"cena{i+1:02d}" not in existentes]
    th = (rot.get("thumb") or {}).get("prompt")  # imagem exclusiva para a miniatura, no mesmo lote
    if th and (forcar or "thumb" not in existentes):
        pedidos.append({"prompt": th, "saida": os.path.join(dest, "thumb.png"), "proporcao": "16:9", "seed": 7777})
    if not pedidos:
        return 0
    print(f"   gerando {len(pedidos)} imagens no seu PC (em lote)...", flush=True)
    try:
        return imagem_local.gerar_lote(pedidos)
    except Exception as e:
        print(f"   ! imagem local falhou ({str(e)[:80]}) - usando outras fontes", flush=True)
        return 0


def obter_visual(i, c, rot, pasta, usados):
    """Garante imagens/cenaNN.(png|jpg|mp4). Ordem: arquivo existente (seu/cache) -> IA Google -> Pixabay video -> foto Openverse/Pixabay."""
    dest = os.path.join(pasta, "imagens")
    os.makedirs(dest, exist_ok=True)
    nome = f"cena{i+1:02d}"
    for f in os.listdir(dest):
        if os.path.splitext(f)[0].lower() == nome and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm")):
            return os.path.join(dest, f)
    if SO_LOCAL:
        return None
    if CFG["producao"] == "manual":
        return None
    if gerar_imagem(prompt_imagem(c, rot), os.path.join(dest, nome + ".png")):
        return os.path.join(dest, nome + ".png")
    if baixar_pixabay_video(c.get("busca", "dark"), os.path.join(dest, nome + ".mp4"), usados):
        return os.path.join(dest, nome + ".mp4")
    try:
        import imagens_auto
        res = imagens_auto.buscar(c.get("busca") or "dark scene", usados)
        if res:
            img = requests.get(res[0], headers=imagens_auto.UA, timeout=40)
            img.raise_for_status()
            arq = os.path.join(dest, nome + ".jpg")
            open(arq, "wb").write(img.content)
            with open(os.path.join(dest, "CREDITOS.txt"), "a", encoding="utf-8") as fh:
                fh.write(f"{nome}: {res[1]}\n")
            return arq
    except Exception as e:
        print(f"   ! foto: {str(e)[:60]}")
    return None


# ---------------------------------------------------------------- montagem
def movimento(tipo, fr, W, H):
    c = f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    m = {
        "zoom_in": f"z='1+0.22*on/{fr}':{c}",
        "zoom_out": f"z='1.22-0.22*on/{fr}':{c}",
        "pan_dir": f"z=1.18:x='(iw-iw/zoom)*on/{fr}':y='ih/2-(ih/zoom/2)'",
        "pan_esq": f"z=1.18:x='(iw-iw/zoom)*(1-on/{fr})':y='ih/2-(ih/zoom/2)'",
        "desce": f"z=1.18:x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/{fr}'",
        "sobe": f"z=1.18:x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{fr})'",
        "tremor": f"z=1.12:x='iw/2-(iw/zoom/2)+sin(on*1.9)*7':y='ih/2-(ih/zoom/2)+cos(on*2.7)*7'",
    }
    return m.get(tipo) or m[random.choice(list(m)[:6])]


def ts(s):
    return f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}"


def criar_legendas(cenas, duracoes, arquivo, W, H):
    vertical = H > W
    tam = 78 if vertical else (66 if W > H else 70)
    estilo = (f"Style: L,Arial,{tam},&H00FFFFFF,&H00000000,1,6,2,5,0,1" if vertical
              else f"Style: L,Arial,{tam},&H0000FFFF,&H00000000,1,5,2,2,{int(H*0.08)},1")
    linhas = ["[Script Info]", f"PlayResX: {W}", f"PlayResY: {H}", "", "[V4+ Styles]",
              "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginV, Bold",
              estilo, "", "[Events]", "Format: Layer, Start, End, Style, Text"]
    t = 0.0
    for cena, dur in zip(cenas, duracoes):
        palavras = cena["narracao"].split()
        n = 3 if vertical else 6
        blocos = [palavras[i:i+n] for i in range(0, len(palavras), n)]
        fala = dur - 0.2
        total = sum(len(" ".join(b)) for b in blocos) or 1
        for b in blocos:
            d = fala * len(" ".join(b)) / total
            linhas.append(f"Dialogue: 0,{ts(t)},{ts(t+d)},L,{' '.join(b).upper()}")
            t += d
        t += dur - fala
    open(arquivo, "w", encoding="utf-8").write("\n".join(linhas))


AMBIENTES = {  # trilha gerada pelo FFmpeg (gratis) quando nao ha musica na pasta musica/
    "terror": "anoisesrc=c=brown:a=0.5:r=44100,lowpass=f=220,tremolo=f=0.15:d=0.7,volume=0.9",
    "suspense": "anoisesrc=c=brown:a=0.4:r=44100,lowpass=f=300,tremolo=f=0.08:d=0.5,volume=0.8",
    "drama": "anoisesrc=c=pink:a=0.15:r=44100,lowpass=f=500,volume=0.5",
    "epico": "anoisesrc=c=brown:a=0.35:r=44100,lowpass=f=400,volume=0.7",
    "espaco": "anoisesrc=c=brown:a=0.3:r=44100,lowpass=f=180,aecho=0.8:0.7:900:0.5,volume=0.8",
    "leve": "",
}


def faixa_musica():
    pasta = os.path.join(BASE, "musica")
    amb = tema_canal()["ambiente"]
    if os.path.isdir(pasta):
        arqs = [f for f in os.listdir(pasta) if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg"))]
        pref = [f for f in arqs if amb in f.lower()] or arqs
        if pref:
            return ["-stream_loop", "-1", "-i", os.path.join(pasta, random.choice(pref))], 0.22
    if AMBIENTES.get(amb):
        return ["-f", "lavfi", "-i", AMBIENTES[amb]], 0.5
    return None, 0


def miniatura(rot, pasta, W, H, texto=None):
    """Miniatura de alto clique: imagem dedicada (thumb.png) ou a cena mais forte, texto CURTO e enorme
    no lado escuro, 1 palavra em destaque, contraste/vinheta de cinema e selo. Salva miniatura.jpg."""
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps
    TW, TH = (1280, 720) if W >= H else (1080, 1920)
    vertical = TH > TW
    img_dir = os.path.join(pasta, "imagens")
    th = rot.get("thumb") or {}
    fundo = None
    if os.path.exists(os.path.join(img_dir, "thumb.png")):
        fundo = Image.open(os.path.join(img_dir, "thumb.png")).convert("RGB")
    elif os.path.isdir(img_dir):
        # cena com o personagem principal/entidade tem prioridade; senao, um terco do video
        fotos = sorted(f for f in os.listdir(img_dir) if re.match(r"cena\d+\.(png|jpe?g|webp)$", f.lower()))
        alvo = None
        nomes = [p.get("nome", "").lower() for p in rot.get("personagens", [])]
        for i, c in enumerate(rot.get("cenas", [])):
            if any(n and n in " ".join(c.get("personagens") or []).lower() + c.get("imagem", "").lower() for n in nomes[-1:]):
                alvo = next((f for f in fotos if f.lower().startswith(f"cena{i+1:02d}.")), None)
                if alvo: break
        alvo = alvo or (fotos[min(len(fotos) - 1, len(fotos) // 3)] if fotos else None)
        if alvo:
            fundo = Image.open(os.path.join(img_dir, alvo)).convert("RGB")
    if fundo is None and os.path.exists(os.path.join(pasta, "video.mp4")):
        ff(["-ss", "3", "-i", "video.mp4", "-frames:v", "1", "thumb_tmp.png"], pasta)
        fundo = Image.open(os.path.join(pasta, "thumb_tmp.png")).convert("RGB")
    if fundo is None:
        fundo = Image.new("RGB", (TW, TH), (12, 10, 10))
    if vertical:
        fundo = _cobrir(fundo, TW, TH)
    else:
        # foto empurrada para a DIREITA (o rosto fica livre); a esquerda vira um fundo escuro desfocado para o texto
        foto = _cobrir(fundo, int(TW * 0.66), TH)
        base = _cobrir(fundo, TW, TH).filter(ImageFilter.GaussianBlur(28))
        base = ImageEnhance.Brightness(base).enhance(0.35)
        fade = Image.new("L", foto.size, 255)
        fd = ImageDraw.Draw(fade)
        for x in range(int(foto.width * 0.18)):
            fd.line([(x, 0), (x, TH)], fill=int(255 * x / (foto.width * 0.18)))
        base.paste(foto, (TW - foto.width, 0), fade)
        fundo = base

    # grade de cinema: contraste, saturacao leve, sombras frias
    fundo = ImageEnhance.Contrast(fundo).enhance(1.28)
    fundo = ImageEnhance.Color(fundo).enhance(1.12)
    fundo = ImageEnhance.Sharpness(fundo).enhance(1.4)
    # escurece o lado do texto (esquerda no 16:9, base no vertical) + vinheta
    mask = Image.new("L", (TW, TH), 0)
    md = ImageDraw.Draw(mask)
    if vertical:
        for y in range(TH):
            md.line([(0, y), (TW, y)], fill=int(235 * max(0, (y / TH - 0.45) / 0.55) ** 1.2))
    else:
        for x in range(TW):
            md.line([(x, 0), (x, TH)], fill=int(200 * max(0, 1 - x / (TW * 0.42)) ** 1.3))
    fundo = Image.composite(Image.new("RGB", (TW, TH), (4, 4, 6)), fundo, mask)
    vin = Image.new("L", (TW, TH), 0)
    ImageDraw.Draw(vin).ellipse([-TW * .25, -TH * .35, TW * 1.25, TH * 1.35], fill=255)
    vin = ImageOps.invert(vin.filter(ImageFilter.GaussianBlur(TW // 8)))
    fundo = Image.composite(Image.new("RGB", (TW, TH), (0, 0, 0)), fundo, vin.point(lambda v: int(v * .75)))

    d = ImageDraw.Draw(fundo)
    frase = (texto or th.get("texto") or re.sub(r"\(Parte.*?\)|:.*$", "", rot["titulo"])).strip().upper()
    destaque = (th.get("destaque") or frase.split()[-1]).upper()
    fonte = __import__("config").FONTE_IMPACT
    largura = TW * (0.86 if vertical else 0.36)
    tam = int(TH * (0.085 if vertical else 0.15))
    while True:  # quebra em ate 3 linhas, o maior tamanho que couber
        f = ImageFont.truetype(fonte, tam)
        linhas, atual = [], ""
        for p in frase.split():
            t = (atual + " " + p).strip()
            if d.textlength(t, font=f) > largura and atual:
                linhas.append(atual); atual = p
            else:
                atual = t
        linhas.append(atual)
        if len(linhas) <= 3 or tam < 50:
            break
        tam -= 6
    alt = tam * 1.02
    x0 = TW * (0.07 if vertical else 0.05)
    y = (TH * 0.62) if vertical else (TH - len(linhas) * alt) / 2 + TH * 0.03
    sombra = Image.new("RGBA", (TW, TH), (0, 0, 0, 0)); sd = ImageDraw.Draw(sombra)
    pos = []
    for l in linhas:
        pos.append((x0, y, l)); sd.text((x0 + 6, y + 8), l, font=f, fill=(0, 0, 0, 230)); y += alt
    fundo.paste(sombra.filter(ImageFilter.GaussianBlur(9)), (0, 0), sombra.filter(ImageFilter.GaussianBlur(9)))
    d = ImageDraw.Draw(fundo)
    traco = max(5, tam // 13)
    for x, y, l in pos:  # palavra de destaque em amarelo, resto branco
        cx = x
        for palavra in l.split():
            cor = (255, 214, 10) if destaque.strip(".,!?") in palavra.strip(".,!?") else (255, 255, 255)
            d.text((cx, y), palavra, font=f, fill=cor, stroke_width=traco, stroke_fill=(0, 0, 0))
            cx += d.textlength(palavra + " ", font=f)
    selo = (f"PARTE {rot['parte']}" if rot.get("parte") else th.get("selo", "")).upper()
    if selo:
        fs = ImageFont.truetype(fonte, int(TH * (0.032 if vertical else 0.06)))
        sw = d.textlength(selo, font=fs)
        sy = (TH * 0.62 - TH * 0.06) if vertical else TH * 0.07
        d.rectangle([x0, sy, x0 + sw + 34, sy + fs.size * 1.35], fill=(200, 16, 46))
        d.text((x0 + 17, sy + fs.size * 0.12), selo, font=fs, fill="white")
    fundo.save(os.path.join(pasta, "miniatura.jpg"), quality=93)
    if os.path.exists(os.path.join(pasta, "thumb_tmp.png")):
        os.remove(os.path.join(pasta, "thumb_tmp.png"))


def _cobrir(im, W, H):
    r = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1))
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def ff(args, cwd):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], cwd=cwd, check=True)


def voz_do_personagem(quem, rot):
    """Se quem fala e um personagem, usa SEMPRE a mesma voz dele (elenco fixo, salvo no roteiro)."""
    if not quem:
        return quem
    elenco = rot.setdefault("elenco", {})
    nomes = {p.get("nome", "").strip().lower(): p for p in rot.get("personagens", []) if p.get("nome")}
    k = str(quem).strip().lower()
    if k not in nomes:
        return quem  # narrador ou tipo de voz
    if k not in elenco:
        v = nomes[k].get("voz", "")
        usadas = set(elenco.values())
        ap = " " + re.sub(r"[^a-z ]", " ", nomes[k].get("aparencia_en", "").lower()) + " "
        g_ap = "f" if re.search(r" (woman|girl|female|lady|mother|grandmother) ", ap) else "m" if re.search(r" (man|boy|male|guy|father|grandfather) ", ap) else ""
        g_v = "f" if any(w in v for w in ("femin", "mulher", "ava", "emma", "crianca")) else "m" if v in VOZES else ""
        if v not in VOZES or v in usadas or (g_ap and g_v and g_ap != g_v):  # voz livre e do genero certo
            fem = (g_ap or g_v) == "f"
            opcoes = (["mulher_jovem", "feminina", "mulher_velha", "ava", "emma"] if fem
                      else ["homem_jovem", "masculina", "homem_velho", "antonio_grave", "andrew", "brian"])
            v = next((o for o in ([v] if v in VOZES else []) + opcoes if o not in usadas), opcoes[0])
        elenco[k] = v
    return elenco[k]


def montar(rot, nome=None, pasta=None):
    proporcao, (W, H) = tela()
    nome = nome or re.sub(r"[^\w\- ]", "", rot["titulo"])[:40].strip().replace(" ", "_")
    pasta = pasta or os.path.join(BASE, "Para_Aprovar", f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{nome}")
    os.makedirs(pasta, exist_ok=True)
    rot["formato"] = "short" if CFG["modo"] in ("short", "novela") else "longo"
    rot["config"] = {k: v for k, v in CFG.items()}
    rot["tela"], rot["tema_canal"] = proporcao, tema_canal()["nome"]
    salvar = lambda: json.dump(rot, open(os.path.join(pasta, "roteiro.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    salvar()
    print(f"   Titulo: {rot['titulo']}  |  {len(rot['cenas'])} cenas  |  {proporcao}")

    cenas, duracoes = rot["cenas"], []
    print("2/4 Narracao...", flush=True)
    global VOZ_CAIU
    VOZ_CAIU = False
    for i, c in enumerate(cenas):
        duracoes.append(gerar_voz(c["narracao"], os.path.join(pasta, f"voz{i}.wav"), voz_do_personagem(c.get("voz"), rot)))
    if VOZ_CAIU and str(CFG.get("voz") or tema_canal()["voz"]).startswith(("gemini:", "clone:")):
        # a voz de IA caiu no meio (cota/servico): refaz TODAS as cenas com a mesma voz reserva (nada de vozes misturadas)
        print("   voz de IA indisponivel em parte das cenas - refazendo a narracao inteira com a voz reserva", flush=True)
        CFG["voz"] = "antonio_grave"
        duracoes = [gerar_voz(c["narracao"], os.path.join(pasta, f"voz{i}.wav"), voz_do_personagem(c.get("voz"), rot))
                    for i, c in enumerate(cenas)]
    with wave.open(os.path.join(pasta, "narracao.wav"), "wb") as out:
        for i in range(len(cenas)):
            with wave.open(os.path.join(pasta, f"voz{i}.wav")) as w:
                if i == 0: out.setparams(w.getparams())
                out.writeframes(w.readframes(w.getnframes()))
    total = sum(duracoes)
    criar_legendas(cenas, duracoes, os.path.join(pasta, "legendas.ass"), W, H)

    print("3/4 Imagens e animacao...")
    if not SO_LOCAL:
        lote_local(cenas, rot, pasta)
    usados, fade = set(), 0.35
    base = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30"
    sem_visual = []
    for i, (c, d) in enumerate(zip(cenas, duracoes)):
        arq = obter_visual(i, c, rot, pasta, usados)
        fades = f"fade=t=in:st=0:d={fade},fade=t=out:st={max(0, d - fade):.3f}:d={fade}"
        if arq and arq.lower().endswith((".mp4", ".mov", ".webm")):
            ff(["-stream_loop", "-1", "-i", arq, "-t", f"{d:.3f}", "-an", "-vf", f"{base},eq=brightness=-0.05,{fades}",
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", f"clip{i}.mp4"], pasta)
            continue
        if arq:
            ff(["-i", arq, "-frames:v", "1", f"img{i}.png"], pasta)
        else:
            sem_visual.append(i + 1)
            ff(["-f", "lavfi", "-i", f"color=c=0x101018:s={W}x{H}", "-frames:v", "1", f"img{i}.png"], pasta)
        fr = int(d * 30) + 1
        mov = movimento(c.get("camera", ""), fr, W, H)
        ff(["-loop", "1", "-i", f"img{i}.png", "-t", f"{d:.3f}",
            "-vf", f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                   f"zoompan={mov}:d={fr}:s={W}x{H}:fps=30,{fades}",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", f"clip{i}.mp4"], pasta)
        print(f"   cena {i+1}/{len(cenas)} ok")
        print(f"PROGRESSO {i+1}/{len(cenas)} animando", flush=True)

    print("4/4 Montagem final (legendas + trilha)...")
    open(os.path.join(pasta, "lista.txt"), "w").write("".join(f"file 'clip{i}.mp4'\n" for i in range(len(cenas))))
    musica, vol = faixa_musica() if CFG["musica"] else (None, 0)
    if musica:
        filtro = (f"[0:v]ass=legendas.ass[v];[2:a]volume={vol},afade=t=in:d=2,afade=t=out:st={max(0, total - 3):.2f}:d=3[m];"
                  f"[m][1:a]sidechaincompress=threshold=0.04:ratio=6:release=400[md];"
                  f"[1:a][md]amix=inputs=2:duration=first:normalize=0[a]")
        ff(["-f", "concat", "-safe", "0", "-i", "lista.txt", "-i", "narracao.wav", *musica, "-t", f"{total:.2f}",
            "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "video.mp4"], pasta)
    else:
        ff(["-f", "concat", "-safe", "0", "-i", "lista.txt", "-i", "narracao.wav", "-vf", "ass=legendas.ass",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "video.mp4"], pasta)

    for f in os.listdir(pasta):
        if f.startswith(("clip", "voz", "img", "narracao")) or f == "lista.txt":
            os.remove(os.path.join(pasta, f))
    miniatura(rot, pasta, W, H)
    rot["duracoes"] = [round(x, 2) for x in duracoes]
    rot["duracao_s"] = round(total, 1)
    rot["custo_usd"] = round(rot.get("custo_usd_texto", custos.sessao_usd), 5)
    rot["sem_visual"] = sem_visual
    rot["gerado_em"] = datetime.datetime.now().isoformat(timespec="seconds")
    salvar()
    open(os.path.join(pasta, "info.txt"), "w", encoding="utf-8").write(
        f"TITULO:\n{rot['titulo']}\n\nDESCRICAO:\n{rot['descricao']}\n")
    aviso = f" | ATENCAO: {len(sem_visual)} cenas sem imagem (fundo escuro)" if sem_visual else ""
    print(f"\nPronto! {os.path.abspath(pasta)}\\video.mp4 ({total:.0f}s){aviso}")
    return pasta


# ---------------------------------------------------------------- entrada
SO_LOCAL = False


def main():
    global SO_LOCAL, MODELO_IMAGEM
    args = sys.argv[1:]
    if "--config" in args:
        i = args.index("--config")
        CFG.update({k: v for k, v in json.load(open(args[i + 1], encoding="utf-8")).items() if v not in (None, "")})
        del args[i:i + 2]
    if "--duracao" in args:
        i = args.index("--duracao")
        CFG["duracao"] = int(args[i + 1]); del args[i:i + 2]
    if "--novela" in args:
        i = args.index("--novela")
        CFG["modo"], CFG["partes"] = "novela", int(args[i + 1]); del args[i:i + 2]
    if "--short" in args:
        CFG["modo"] = "short"; args.remove("--short")
    if CFG["duracao"]:
        CFG["duracao"] = max(15, min(3600, int(CFG["duracao"])))

    if "--refazer" in args:
        pasta = os.path.abspath(args[args.index("--refazer") + 1])
        rot = json.load(open(os.path.join(pasta, "roteiro.json"), encoding="utf-8"))
        CFG.update(rot.get("config") or {"modo": rot.get("formato", "longo")})
        SO_LOCAL, MODELO_IMAGEM = "--buscar" not in args, ""  # remontar nunca usa IA paga
        if "--imagens-ia" in args:  # troca TODAS as imagens por imagens geradas no PC a partir da historia
            CFG["imagens"], CFG["producao"] = "local", "economico"
            dest = os.path.join(pasta, "imagens"); antigas = os.path.join(dest, "_substituidas")
            if os.path.isdir(dest):
                os.makedirs(antigas, exist_ok=True)
                for f in os.listdir(dest):
                    if f.lower().startswith("cena"):
                        os.replace(os.path.join(dest, f), os.path.join(antigas, f"antes_ia_{f}"))
            lote_local(rot["cenas"], rot, pasta)
        rot["custo_usd_texto"] = rot.get("custo_usd", 0)
        montar(rot, pasta=pasta)
        return

    if args and not CFG["tema"]:
        CFG["tema"] = " ".join(args)
    if CFG["modo"] == "mapa":  # Shorts de historia com mapa animado (motor proprio, sem placa de video)
        import mapa_animado
        mapa_animado.gerar({**CFG, "voz": CFG["voz"] or tema_canal()["voz"], "canal": "O Que a História Escondeu" if CFG["tema_canal"] == "historia" else tema_canal()["nome"],
                            "duracao": CFG["duracao"] or 60, "tela": CFG["tela"] or "9:16"})
        return
    t = tamanho()
    print(f"1/4 Roteiro ({tema_canal()['nome']}, ~{t['seg']}s, {t['cmin']}-{t['cmax']} cenas)...")
    if CFG["modo"] == "novela":
        n = max(2, min(15, int(CFG["partes"])))
        nov = gerar_novela(n, t)
        serie = re.sub(r"[^\w\- ]", "", nov["serie"])[:25].strip().replace(" ", "_")
        for k, rot in enumerate(nov["partes"][:n], 1):
            rot.update({"serie": nov["serie"], "parte": k, "total": n, "personagens": nov.get("personagens", [])})
            print(f"\n=== Parte {k}/{n} ===")
            montar(rot, f"{serie}_P{k:02d}")
        return
    rot = gerar_roteiro_blocos(t) if (CFG["modo"] == "longo" and t["seg"] > 240) else gerar_roteiro_simples(t)
    if CFG["titulo"]:
        rot["titulo"] = CFG["titulo"]
    montar(rot)


if __name__ == "__main__":
    main()

"""Cria um PROJETO DE SERIE completo (bíblia, capítulos, cenas, narração e prompts para Google Flow).
Uso: python projeto_serie.py projetos/<arquivo_config>.json
Saída: Projetos/<nome>/  -> biblia.json, cap01.json..., PROJETO.md, flow/capXX.txt
Não gera vídeo: só planejamento. A montagem vem na etapa 3.
"""
import json, os, re, sys, time
from dotenv import load_dotenv
from google import genai
from google.genai import types
import custos

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODELOS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
SEG_POR_CENA = 8  # clipes do Google Flow (Veo) têm ~8s


def pedir_json(prompt):
    for _ in range(3):
        for m in MODELOS:
            try:
                r = client.models.generate_content(
                    model=m, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9))
                custos.registrar(m, r, etapa="projeto")
                return json.loads(r.text)
            except Exception as e:
                print(f"   ! {m}: {str(e)[:60]} - tentando outro")
        time.sleep(15)
    raise SystemExit("Modelos indisponíveis agora. Rode de novo mais tarde (o que já foi feito fica salvo).")


PROMPT_BIBLIA = """Você é showrunner de uma novela de suspense em Shorts para um canal dark brasileiro.
CONFIGURAÇÃO:
- Gênero: {genero}
- Capítulos: {capitulos} (cada um com {duracao} segundos, formato {formato})
- Ideia: {ideia}

Crie a BÍBLIA DA SÉRIE em PT-BR (só os campos de prompt visual em INGLÊS). Requisitos:
- Uma lenda com regras claras e um segredo final que explica tudo de forma lógica.
- {capitulos} pistas, uma por capítulo, que juntas levam ao segredo (nada aleatório).
- 3 a 5 personagens com nomes brasileiros fictícios. Cada um com "visual_en": descrição física FIXA e detalhada em inglês
  (idade, etnia, cabelo, olhos, roupa exata com cores, acessório marcante) para repetir em TODO prompt e manter consistência.
- Locações recorrentes com "visual_en" fixo.
- "estilo_en": um bloco de estilo visual fixo (câmera, luz, paleta, granulação) para colar em todos os prompts.
- Narrador: quem conta a história (primeira pessoa de um personagem) e o tom da voz.

Responda SOMENTE JSON:
{{"titulo_serie": "", "logline": "", "lenda": {{"historia": "", "regras": [""], "segredo_final": ""}},
  "narrador": {{"personagem": "", "tom": ""}},
  "personagens": [{{"id": "P1", "nome": "", "idade": 0, "papel": "", "personalidade": "", "segredo": "", "arco": "", "visual_en": ""}}],
  "locacoes": [{{"id": "L1", "nome": "", "descricao": "", "visual_en": ""}}],
  "objetos_chave": [{{"nome": "", "visual_en": ""}}],
  "estilo_en": "",
  "capitulos": [{{"numero": 1, "titulo": "", "resumo": "", "pista_revelada": "", "gancho_final": ""}}]}}"""

PROMPT_CAP = """Você é roteirista da série "{titulo}". Escreva o CAPÍTULO {n} de {total}.
BÍBLIA (siga à risca, não invente fatos que a contradigam):
{biblia}

O QUE JÁ ACONTECEU (continuidade):
{anteriores}

PLANO DESTE CAPÍTULO: {plano}

REGRAS:
- Duração {duracao}s: narração total de {palavras_min} a {palavras_max} palavras, PT-BR natural, primeira pessoa do narrador.
- {cenas} cenas de ~{seg}s cada (o Google Flow gera clipes de {seg}s).
- {abertura}
- {final}
- Revele a pista: "{pista}".
- "prompt_flow" em INGLÊS, autossuficiente (o Flow não lembra das cenas anteriores): sempre inclua o visual_en COMPLETO
  dos personagens que aparecem e da locação, a ação, o movimento de câmera, a luz, e termine com o estilo_en e
  "vertical 9:16, no text, no subtitles". Sem violência gráfica.
- "continuidade": o que precisa estar igual à cena anterior (roupa, objeto na mão, ferimento, hora do dia).

Responda SOMENTE JSON:
{{"numero": {n}, "titulo": "", "titulo_youtube": "max 70 caracteres, termina com (Parte {n}/{total})",
  "descricao_youtube": "2 linhas sem spoiler + 4 hashtags",
  "resumo_continuidade": "3 frases do que aconteceu neste capítulo, para o próximo",
  "cenas": [{{"numero": 1, "duracao_s": {seg}, "local": "L1", "personagens": ["P1"],
              "narracao": "texto falado nesta cena", "som": "efeito sonoro/ambiente",
              "continuidade": "", "prompt_flow": ""}}]}}"""


def md_projeto(cfg, bib, caps):
    L = [f"# {bib['titulo_serie']}", "", f"> {bib['logline']}", "",
         f"**Gênero:** {cfg['genero']} · **Capítulos:** {cfg['capitulos']} · **Duração:** {cfg['duracao_s']}s · **Formato:** {cfg['formato']}", "",
         "## A lenda", bib["lenda"]["historia"], "", "**Regras:**", *[f"- {r}" for r in bib["lenda"]["regras"]], "",
         f"**Segredo final (não revelar antes do último capítulo):** {bib['lenda']['segredo_final']}", "",
         f"## Narrador\n{bib['narrador']['personagem']} — tom: {bib['narrador']['tom']}", "", "## Personagens"]
    for p in bib["personagens"]:
        L += [f"### {p['id']} · {p['nome']} ({p['idade']}) — {p['papel']}",
              f"- Personalidade: {p['personalidade']}", f"- Segredo: {p['segredo']}", f"- Arco: {p['arco']}",
              f"- Visual (prompt fixo): `{p['visual_en']}`", ""]
    L += ["## Locações", *[f"- **{l['id']} · {l['nome']}**: {l['descricao']}  \n  `{l['visual_en']}`" for l in bib["locacoes"]], "",
          "## Objetos-chave", *[f"- **{o['nome']}**: `{o['visual_en']}`" for o in bib.get("objetos_chave", [])], "",
          f"## Estilo visual fixo\n`{bib['estilo_en']}`", "", "## Mapa de pistas"]
    L += [f"{c['numero']}. **{c['titulo']}** — pista: {c['pista_revelada']} · gancho: {c['gancho_final']}" for c in bib["capitulos"]]
    for c in caps:
        L += ["", "---", f"## Capítulo {c['numero']} — {c['titulo']}", f"**YouTube:** {c['titulo_youtube']}", ""]
        for s in c["cenas"]:
            L += [f"**Cena {s['numero']}** ({s['duracao_s']}s · {s['local']} · {', '.join(s['personagens'])})",
                  f"- 🎙️ {s['narracao']}", f"- 🔊 {s['som']}", f"- 🔗 Continuidade: {s['continuidade']}",
                  f"- 🎬 Flow: `{s['prompt_flow']}`", ""]
    return "\n".join(L)


def main():
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    nome = re.sub(r"[^\w\- ]", "", cfg["nome"]).strip().replace(" ", "_")
    pasta = os.path.join("Projetos", nome)
    os.makedirs(os.path.join(pasta, "flow"), exist_ok=True)
    json.dump(cfg, open(os.path.join(pasta, "config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    arq_bib = os.path.join(pasta, "biblia.json")
    if os.path.exists(arq_bib):
        bib = json.load(open(arq_bib, encoding="utf-8"))
        print("Etapa 1: bíblia já existe (reaproveitando).")
    else:
        print("Etapa 1: criando bíblia da série...")
        bib = pedir_json(PROMPT_BIBLIA.format(genero=cfg["genero"], capitulos=cfg["capitulos"],
                                              duracao=cfg["duracao_s"], formato=cfg["formato"], ideia=cfg["ideia"]))
        json.dump(bib, open(arq_bib, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"   Série: {bib['titulo_serie']}")

    total, dur = cfg["capitulos"], cfg["duracao_s"]
    n_cenas = round(dur / SEG_POR_CENA)
    bib_txt = json.dumps({k: bib[k] for k in ("lenda", "narrador", "personagens", "locacoes", "objetos_chave", "estilo_en")},
                         ensure_ascii=False)
    caps = []
    for n in range(1, total + 1):
        arq = os.path.join(pasta, f"cap{n:02d}.json")
        if os.path.exists(arq):
            caps.append(json.load(open(arq, encoding="utf-8")))
            continue
        print(f"Etapa 2: capítulo {n}/{total}...")
        plano = bib["capitulos"][n - 1] if n <= len(bib["capitulos"]) else {}
        anteriores = "\n".join(f"Cap {c['numero']}: {c['resumo_continuidade']}" for c in caps) or "Nada ainda (primeiro capítulo)."
        cap = pedir_json(PROMPT_CAP.format(
            titulo=bib["titulo_serie"], n=n, total=total, biblia=bib_txt, anteriores=anteriores,
            plano=json.dumps(plano, ensure_ascii=False), duracao=dur,
            palavras_min=int(dur * 2.2), palavras_max=int(dur * 2.5), cenas=n_cenas, seg=SEG_POR_CENA,
            pista=plano.get("pista_revelada", ""),
            abertura="Abra com o gancho mais assustador da série." if n == 1 else
                     "Abra com uma recapitulação relâmpago (máx 12 palavras) do capítulo anterior.",
            final=f"Termine num cliffhanger: '{plano.get('gancho_final', '')}' e a frase 'Continua na parte {n + 1}.'"
                  if n < total else "Entregue o segredo final da lenda, feche todos os mistérios e peça comentários."))
        json.dump(cap, open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        open(os.path.join(pasta, "flow", f"cap{n:02d}.txt"), "w", encoding="utf-8").write(
            "\n\n".join(f"### CENA {s['numero']} ({s['duracao_s']}s)\n{s['prompt_flow']}" for s in cap["cenas"]))
        caps.append(cap)

    open(os.path.join(pasta, "PROJETO.md"), "w", encoding="utf-8").write(md_projeto(cfg, bib, caps))
    print(f"\nPronto! Abra: {os.path.abspath(os.path.join(pasta, 'PROJETO.md'))}")


if __name__ == "__main__":
    main()

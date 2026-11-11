"""Prepara os textos de publicacao do YouTube (titulo forte, descricao com capitulos, hashtags, tags)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def capitulos(rot):
    """Capitulos do YouTube (00:00 ...) a partir dos blocos do roteiro e das duracoes reais das cenas."""
    plano, dur = rot.get("plano") or [], rot.get("duracoes") or []
    if not plano or not dur or len(plano) < 3:
        return ""
    total = sum(dur)
    linhas = []
    for b in plano:
        ini = min(total, b.get("inicio_s", 0) * total / max(1, plano[-1].get("fim_s", total)))
        linhas.append(f"{int(ini // 60):02d}:{int(ini % 60):02d} {b.get('titulo', '').strip()}")
    linhas[0] = "00:00" + linhas[0][5:]  # YouTube exige comecar em 00:00
    return "\n".join(linhas)


def gerar(rot):
    import gerar_video as g  # reaproveita a rotacao de modelos e o registro de custos
    resumo = " ".join(c["narracao"] for c in rot["cenas"])[:6000]
    curto = rot.get("formato") == "short"
    r = g.pedir_json(f"""Voce e especialista em SEO e CTR do YouTube Brasil para canais dark de {rot.get('tema_canal', 'historias')}.
Video: "{rot['titulo']}" ({'Short' if curto else 'video longo'}).
Historia (resumo da narracao): {resumo}

Crie os textos de publicacao. Regras:
- 3 opcoes de TITULO em PT-BR, max 70 caracteres, curiosidade + emocao, sem clickbait mentiroso, sem CAPS em tudo
  (pode 1-2 palavras em CAPS). {'Inclua #shorts no fim de cada titulo.' if curto else ''}
- DESCRICAO: 1a linha = gancho forte (aparece na busca); 2-3 linhas resumindo SEM spoiler do final;
  uma linha "Esta e uma historia ficticia/dramatizada, narrada com recursos de inteligencia artificial.";
  convite para inscrever e comentar; 3 a 5 hashtags no final.
- TAGS: 12 a 15 palavras-chave de busca em PT-BR (sem #), do mais especifico ao mais amplo.
- MINIATURA: 3 frases CURTAS (3 a 5 palavras, PT-BR, em CAPS) para escrever na thumbnail, que criem curiosidade/medo
  sem repetir o titulo (ex: "NAO OLHE PARA O ESPELHO", "ELA AINDA ESTA LA"), e a palavra de destaque de cada uma.
Responda SOMENTE JSON: {{"titulos": ["", "", ""], "descricao": "", "hashtags": ["#..."], "tags": [""],
  "miniatura": [{{"texto": "", "destaque": ""}}]}}""", "seo")
    caps = capitulos(rot)
    desc = r["descricao"].strip()
    if caps and "00:00" not in desc:
        desc += "\n\nCapítulos:\n" + caps
    th = rot.get("thumb") or {}
    if r.get("miniatura"):
        th["opcoes"] = r["miniatura"][:3]
        rot["thumb"] = th
    return {"miniatura": r.get("miniatura", [])[:3], "titulos": r.get("titulos", [])[:3] or [rot["titulo"]], "titulo": (r.get("titulos") or [rot["titulo"]])[0],
            "descricao": desc, "tags": [t.strip("# ") for t in r.get("tags", [])][:15],
            "categoria": "24", "para_criancas": False, "conteudo_ia": True}


def sugerir_temas(tema_canal, nome_tema, ja_feitos=()):
    """IA sugere 6 temas com alto potencial de visualizacao para o nicho escolhido (1 chamada, cota gratis)."""
    import gerar_video as g
    r = g.pedir_json(f"""Voce e estrategista de canais dark do YouTube Brasil. Nicho: {nome_tema}.
Sugira 6 temas de video com MAIOR potencial de views no Brasil agora (se o nicho tiver varios tipos, misture-os): lendas, casos e historias que o publico
brasileiro mais busca e comenta neste nicho (misture classicos muito buscados e angulos novos).
Evite repetir: {", ".join(ja_feitos) or "nada"}.
Para cada um: "tema" (assunto em 1 frase), "titulo" (titulo forte, max 70 caracteres) e "por_que" (1 frase: por que da views).
Responda SOMENTE JSON: {{"sugestoes": [{{"tema": "", "titulo": "", "por_que": ""}}]}}""", "sugestao")
    return r.get("sugestoes", [])[:6]

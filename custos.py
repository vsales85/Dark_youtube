"""Registro de gastos estimados com APIs (custos.jsonl).
Os preços ficam em precos.json (edite se o Google mudar). O valor oficial está sempre em:
https://console.cloud.google.com/billing
"""
import json, os, datetime, threading

BASE = os.path.dirname(os.path.abspath(__file__))
ARQ = os.path.join(BASE, "custos.jsonl")
ARQ_PRECOS = os.path.join(BASE, "precos.json")
_lock = threading.Lock()
sessao_usd = 0.0  # gasto acumulado neste processo (custo por video)

# US$ por 1 milhão de tokens (entrada, saída) e por imagem. ESTIMATIVAS - confira em ai.google.dev/pricing
PRECOS_PADRAO = {
    "cotacao_usd_brl": 5.50,
    "texto": {"default": [0.30, 2.50], "lite": [0.10, 0.40], "pro": [1.25, 10.0]},
    "imagem_por_unidade": {"default": 0.039, "pro": 0.134},
}


def precos():
    if not os.path.exists(ARQ_PRECOS):
        json.dump(PRECOS_PADRAO, open(ARQ_PRECOS, "w", encoding="utf-8"), indent=2)
    return json.load(open(ARQ_PRECOS, encoding="utf-8"))


def _faixa(modelo):
    return "lite" if "lite" in modelo else "pro" if "pro" in modelo else "default"


def registrar(modelo, resposta=None, imagens=0, etapa=""):
    p = precos()
    tin = tout = 0
    meta = getattr(resposta, "usage_metadata", None)
    if meta:
        tin = meta.prompt_token_count or 0
        tout = (meta.candidates_token_count or 0) + (getattr(meta, "thoughts_token_count", 0) or 0)
    f = _faixa(modelo)
    usd = 0.0
    if imagens:
        usd += imagens * p["imagem_por_unidade"].get(f, p["imagem_por_unidade"]["default"])
    else:
        pin, pout = p["texto"].get(f, p["texto"]["default"])
        usd += tin / 1e6 * pin + tout / 1e6 * pout
    reg = {"quando": datetime.datetime.now().isoformat(timespec="seconds"), "modelo": modelo, "etapa": etapa,
           "tokens_in": tin, "tokens_out": tout, "imagens": imagens, "usd": round(usd, 6)}
    global sessao_usd
    sessao_usd += usd
    with _lock, open(ARQ, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(reg) + "\n")
    return usd


def resumo():
    p = precos()
    regs = []
    if os.path.exists(ARQ):
        regs = [json.loads(l) for l in open(ARQ, encoding="utf-8") if l.strip()]
    hoje = datetime.date.today().isoformat()
    mes = hoje[:7]
    def soma(f): return round(sum(r["usd"] for r in regs if f(r)), 4)
    total, dia, m = soma(lambda r: True), soma(lambda r: r["quando"].startswith(hoje)), soma(lambda r: r["quando"].startswith(mes))
    por_modelo = {}
    for r in regs:
        por_modelo[r["modelo"]] = round(por_modelo.get(r["modelo"], 0) + r["usd"], 4)
    uso_hoje = {}
    for r in regs:
        if r["quando"].startswith(hoje):
            u = uso_hoje.setdefault(r["modelo"], {"chamadas": 0, "tokens": 0, "imagens": 0})
            u["chamadas"] += 1; u["tokens"] += r["tokens_in"] + r["tokens_out"]; u["imagens"] += r["imagens"]
    c = p["cotacao_usd_brl"]
    return {"usd": {"hoje": dia, "mes": m, "total": total}, "brl": {"hoje": round(dia * c, 2), "mes": round(m * c, 2), "total": round(total * c, 2)},
            "chamadas": len(regs), "imagens": sum(r["imagens"] for r in regs), "por_modelo": por_modelo,
            "ultimos": regs[-8:][::-1], "cotacao": c, "uso_hoje": uso_hoje,
            "tokens_total": sum(r["tokens_in"] + r["tokens_out"] for r in regs)}

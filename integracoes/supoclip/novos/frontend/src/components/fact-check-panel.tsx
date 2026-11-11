"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Loader2, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Check = { claim: string; verdict: "ok" | "impreciso" | "falso" | "verificar"; explanation: string; correction: string; source: string };

const API = "/api/tasks/studio";
const BADGE: Record<Check["verdict"], { label: string; className: string }> = {
  ok: { label: "✅ Certo", className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  impreciso: { label: "⚠️ Impreciso", className: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  falso: { label: "❌ Errado", className: "bg-red-500/15 text-red-700 dark:text-red-300" },
  verificar: { label: "🔎 Conferir", className: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
};

/** Finds the claim in the script tolerating differences in spaces, line breaks, quotes and ellipsis. */
function findClaim(script: string, claim: string): [number, number] | null {
  const exact = script.indexOf(claim);
  if (exact >= 0) return [exact, exact + claim.length];
  const words = claim
    .replace(/[“”"«»]/g, " ")
    .replace(/…/g, "...")
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return null;
  const esc = (w: string) =>
    w
      .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      .replace(/\\\.\\\.\\\./g, "(?:\\.\\.\\.|…)")
      .replace(/['’]/g, "['’]");
  const re = new RegExp(words.map(esc).join("[\\s“”\"«»]+"), "i");
  const m = re.exec(script);
  return m ? [m.index, m.index + m[0].length] : null;
}

/** Fact-check the script: verdict, suggested wording and the law/source behind each claim. */
export function FactCheckPanel({
  script,
  onScriptChange,
  onSources,
}: {
  script: string;
  onScriptChange: (script: string) => void;
  onSources: (sources: string[]) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [checks, setChecks] = useState<Check[] | null>(null);
  const [portugal, setPortugal] = useState(false);
  const [drafts, setDrafts] = useState<Record<number, string>>({});

  const run = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${API}/script/check`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ script }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error(body?.detail ?? `Erro ${r.status}`);
      setChecks(body.checks ?? []);
      setDrafts({});
      setPortugal(!!body.portugal_portuguese);
      onSources(Array.from(new Set((body.checks as Check[]).map((c) => c.source).filter(Boolean))));
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const markOk = (index: number, claim: string) =>
    setChecks((list) => list && list.map((c, i) => (i === index ? { ...c, verdict: "ok", claim, correction: "" } : c)));

  const apply = (index: number, check: Check, text: string) => {
    const novo = text.trim();
    if (!novo) {
      toast.error("Escreva o texto corrigido.");
      return;
    }
    const pos = findClaim(script, check.claim);
    if (!pos) {
      toast.error("Não achei esse trecho no roteiro (ele foi editado?). Clique em Conferir de novo.");
      return;
    }
    onScriptChange(script.slice(0, pos[0]) + novo + script.slice(pos[1]));
    markOk(index, novo);
    toast.success("Trecho corrigido no roteiro");
  };

  const problems = checks?.filter((c) => c.verdict !== "ok").length ?? 0;

  return (
    <div className="space-y-3 rounded-xl border border-dashed p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">Conferir fatos e fontes</p>
          <p className="text-xs text-muted-foreground">A IA confere cada afirmação e mostra a lei ou fonte. As fontes vão para a descrição do vídeo.</p>
        </div>
        <Button size="sm" variant="secondary" onClick={run} disabled={busy || !script.trim()}>
          {busy ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
          {checks ? "Conferir de novo" : "Conferir roteiro"}
        </Button>
      </div>

      {portugal && (
        <p className="rounded-lg bg-amber-500/15 p-2 text-xs text-amber-800 dark:text-amber-200">
          O texto está em <b>português de Portugal</b> (ex.: “sabias”, “teu”). Clique em <b>Corrigir ortografia</b> para adaptar ao português do Brasil.
        </p>
      )}

      {checks && (
        <>
          <p className="text-xs text-muted-foreground">
            {problems === 0 ? "Nenhum problema encontrado." : `${problems} ponto(s) para revisar.`} A IA também erra: em temas de lei e saúde, confira a fonte antes de publicar.
          </p>
          <ul className="space-y-2">
            {checks.map((check, index) => {
              const draft = drafts[index] ?? (check.correction || check.claim);
              return (
                <li key={`${index}-${check.claim}`} className="rounded-lg border p-2 text-sm">
                  <div className="flex flex-wrap items-start gap-2">
                    <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-xs font-medium", BADGE[check.verdict].className)}>{BADGE[check.verdict].label}</span>
                    <span className="min-w-0 flex-1">“{check.claim}”</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{check.explanation}</p>
                  {check.source && <p className="mt-1 text-xs"><b>Fonte:</b> {check.source}</p>}
                  {check.verdict !== "ok" && (
                    <div className="mt-2 space-y-2 rounded-md bg-muted/50 p-2 text-xs">
                      <p className="font-medium">
                        {check.correction ? "Sugestão da IA (pode editar antes de aplicar):" : "Corrija o trecho aqui e clique em Aplicar:"}
                      </p>
                      <textarea
                        className="w-full resize-y rounded-md border bg-background p-2 text-sm leading-relaxed"
                        rows={3}
                        value={draft}
                        onChange={(e) => setDrafts((d) => ({ ...d, [index]: e.target.value }))}
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" onClick={() => apply(index, check, draft)}>Aplicar no roteiro</Button>
                        <Button size="sm" variant="ghost" onClick={() => markOk(index, check.claim)}>Manter como está</Button>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}

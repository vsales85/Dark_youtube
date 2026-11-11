"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Copy, Loader2, Stethoscope } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Facts = {
  title?: string; views?: number; likes?: number; comments?: number; duration?: number;
  hours_online?: number; subscribers?: number; channel?: string; channel_median_views?: number; thumbnail?: string; url?: string;
};
type Analysis = {
  score: number; verdict: string; strengths: string[]; problems: string[]; next_steps: string[];
  new_titles: string[]; new_hook: string; studio_tip: string;
};

const fmt = (n?: number) => (n == null ? "—" : new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 }).format(n));

function copy(text: string) {
  void navigator.clipboard.writeText(text).then(() => toast.success("Copiado"), () => toast.error("Não foi possível copiar"));
}

/** Paste a posted video: public numbers + an AI diagnosis of why it is (not) growing. */
export function VideoAnalysisPanel() {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ facts: Facts; analysis: Analysis } | null>(null);

  const run = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const r = await fetch("/api/tasks/trending/analyze", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error(body?.detail ?? `Erro ${r.status}`);
      setResult(body);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const f = result?.facts;
  const a = result?.analysis;
  const vsChannel = f?.views && f?.channel_median_views ? f.views / Math.max(1, f.channel_median_views) : null;

  return (
    <div className="space-y-4">
      <form onSubmit={run} className="flex flex-col gap-2 rounded-2xl border bg-card p-4 sm:flex-row">
        <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Cole o link do seu vídeo postado no YouTube (Short ou normal)" />
        <Button type="submit" disabled={busy || !url.trim()}>
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Stethoscope className="size-4" />}
          Analisar
        </Button>
      </form>
      {busy && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Lendo o vídeo e comparando com o canal… (uns 20 s)</p>}

      {f && a && (
        <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
          <div className="space-y-2 rounded-2xl border bg-card p-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {f.thumbnail && <img src={f.thumbnail} alt="" className="aspect-video w-full rounded-lg object-cover" />}
            <p className="text-sm font-medium">{f.title}</p>
            <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
              <dt className="text-muted-foreground">Visualizações</dt><dd>{fmt(f.views)}</dd>
              <dt className="text-muted-foreground">Curtidas</dt><dd>{fmt(f.likes)}</dd>
              <dt className="text-muted-foreground">Comentários</dt><dd>{fmt(f.comments)}</dd>
              <dt className="text-muted-foreground">Duração</dt><dd>{f.duration ? `${f.duration} s` : "—"}</dd>
              <dt className="text-muted-foreground">No ar há</dt><dd>{f.hours_online ? `${f.hours_online} h` : "—"}</dd>
              <dt className="text-muted-foreground">Média do canal</dt><dd>{fmt(f.channel_median_views)}</dd>
            </dl>
            {vsChannel !== null && (
              <p className="rounded-md bg-muted/60 p-2 text-xs">
                {vsChannel >= 1 ? `📈 ${vsChannel.toFixed(1)}× a média dos últimos vídeos do canal` : `📉 ${Math.round(vsChannel * 100)}% da média dos últimos vídeos do canal`}
              </p>
            )}
          </div>

          <div className="space-y-4 rounded-2xl border bg-card p-4 text-sm">
            <div className="flex items-start gap-3">
              <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-lg font-bold text-primary-foreground">{a.score}</span>
              <p className="pt-1">{a.verdict}</p>
            </div>
            {a.strengths.length > 0 && (
              <section><p className="mb-1 font-medium">✅ Funcionou</p><ul className="list-disc space-y-0.5 pl-5">{a.strengths.map((s) => <li key={s}>{s}</li>)}</ul></section>
            )}
            {a.problems.length > 0 && (
              <section><p className="mb-1 font-medium">⚠️ O que travou</p><ul className="list-disc space-y-0.5 pl-5">{a.problems.map((s) => <li key={s}>{s}</li>)}</ul></section>
            )}
            <section><p className="mb-1 font-medium">🎯 No próximo vídeo</p><ol className="list-decimal space-y-0.5 pl-5">{a.next_steps.map((s) => <li key={s}>{s}</li>)}</ol></section>
            <section>
              <p className="mb-1 font-medium">Novo gancho (primeira frase)</p>
              <button type="button" onClick={() => copy(a.new_hook)} className="flex w-full items-center justify-between gap-2 rounded-lg border p-2 text-left hover:bg-muted/50">
                <span>{a.new_hook}</span><Copy className="size-3.5 shrink-0 text-muted-foreground" />
              </button>
            </section>
            <section>
              <p className="mb-1 font-medium">Títulos melhores</p>
              {a.new_titles.map((t) => (
                <button key={t} type="button" onClick={() => copy(t)} className="mb-1 flex w-full items-center justify-between gap-2 rounded-lg border p-2 text-left hover:bg-muted/50">
                  <span>{t}</span><Copy className="size-3.5 shrink-0 text-muted-foreground" />
                </button>
              ))}
            </section>
            <p className="rounded-md bg-muted/60 p-2 text-xs">📊 <b>No YouTube Studio:</b> {a.studio_tip}</p>
            <p className="text-xs text-muted-foreground">Análise feita com os dados públicos do vídeo. Retenção e origem do público só aparecem no YouTube Studio.</p>
          </div>
        </div>
      )}
    </div>
  );
}

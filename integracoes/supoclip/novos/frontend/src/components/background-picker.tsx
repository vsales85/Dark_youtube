"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, ImageOff, Loader2, RefreshCw, Sparkles, Undo2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export type Credit = { title?: string; author?: string; license?: string; source?: string; ai?: boolean };
export type Pick = { token: string; file: string; credit?: Credit };
type Option = { file: string; credit?: Credit };
type Part = { text: string; query: string; options: Option[]; index: number; removed: boolean; loading: boolean };

const API = "/api/tasks/studio";
const STYLES = [
  ["cinema", "🎬 Cinema"],
  ["historia", "📜 História (sépia)"],
  ["fe", "🕊️ Fé (luz dourada)"],
  ["noticia", "📰 Notícia"],
  ["suspense", "🕵️ Suspense"],
];

async function readError(response: Response) {
  const body = await response.json().catch(() => null);
  return body?.detail || body?.error || `Erro ${response.status}`;
}

/** Suggest an image for each part of the script; the user picks what is published. */
export function BackgroundPicker({ script, format, onChange }: { script: string; format: string; onChange: (picks: Pick[]) => void }) {
  const [source, setSource] = useState<"free" | "ai">("ai");
  const [style, setStyle] = useState("cinema");
  const [token, setToken] = useState("");
  const [parts, setParts] = useState<Part[]>([]);
  const [planning, setPlanning] = useState(false);

  const publish = (next: Part[], tk = token) => {
    setParts(next);
    onChange(
      next
        .filter((p) => !p.removed && p.options[p.index])
        .map((p) => ({ token: tk, file: p.options[p.index].file, credit: p.options[p.index].credit })),
    );
  };

  const fetchMore = async (tk: string, list: Part[], i: number, src: string) => {
    const part = list[i];
    const r = await fetch(`${API}/backgrounds/more`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token: tk, part: i, query: part.query, source: src, format, seed: Math.floor(Math.random() * 99999) + 1 }),
    });
    if (!r.ok) throw new Error(await readError(r));
    return (await r.json()).options as Option[];
  };

  const plan = async () => {
    setPlanning(true);
    try {
      const r = await fetch(`${API}/backgrounds/plan`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ script, source, style, format }),
      });
      if (!r.ok) throw new Error(await readError(r));
      const body = await r.json();
      let list: Part[] = body.parts.map((p: { text: string; query: string; options: Option[] }) => ({
        ...p, index: 0, removed: false, loading: source === "ai",
      }));
      setToken(body.token);
      publish(list, body.token);
      if (source === "ai") {
        toast.info("As imagens aparecem uma a uma (cerca de 45 s cada). Você já pode ir escolhendo.");
        for (let i = 0; i < list.length; i++) {
          try {
            const options = await fetchMore(body.token, list, i, "ai");
            list = list.map((p, j) => (j === i ? { ...p, options, loading: false } : p));
          } catch (e) {
            list = list.map((p, j) => (j === i ? { ...p, loading: false } : p));
            toast.error((e as Error).message);
          }
          publish(list, body.token);
        }
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setPlanning(false);
    }
  };

  const another = async (i: number) => {
    const list = parts.map((p, j) => (j === i ? { ...p, loading: true } : p));
    setParts(list);
    try {
      const options = await fetchMore(token, list, i, source);
      publish(parts.map((p, j) => (j === i ? { ...p, options: [...p.options, ...options], index: p.options.length, loading: false, removed: false } : p)));
    } catch (e) {
      toast.error((e as Error).message);
      setParts(parts.map((p, j) => (j === i ? { ...p, loading: false } : p)));
    }
  };

  const update = (i: number, change: Partial<Part>) => publish(parts.map((p, j) => (j === i ? { ...p, ...change } : p)));
  const thumb = format === "vertical" ? "aspect-[9/16]" : "aspect-video";

  return (
    <div className="space-y-3 rounded-xl border p-3">
      <div>
        <p className="text-sm font-medium">Imagens para cada trecho do roteiro</p>
        <p className="text-xs text-muted-foreground">O app sugere uma imagem por trecho. Você troca, remove ou edita a busca, e só o que você deixar vai para o vídeo.</p>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <Button size="sm" variant={source === "ai" ? "default" : "outline"} onClick={() => setSource("ai")}>✨ Imagens com IA (cinematográficas)</Button>
        <Button size="sm" variant={source === "free" ? "default" : "outline"} onClick={() => setSource("free")}>📷 Fotos reais livres (rápido)</Button>
        {source === "ai" && (
          <select className="h-8 rounded-md border bg-background px-2 text-sm" value={style} onChange={(e) => setStyle(e.target.value)} aria-label="Estilo das imagens">
            {STYLES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </select>
        )}
        <Button size="sm" variant="secondary" onClick={plan} disabled={planning || !script.trim()}>
          {planning ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
          {parts.length ? "Gerar de novo" : "Gerar imagens"}
        </Button>
      </div>
      {!script.trim() && <p className="text-xs text-muted-foreground">Escreva o roteiro no passo 1 primeiro.</p>}
      {source === "ai" && (
        <p className="text-xs text-muted-foreground">
          Gerador grátis: cerca de 45 s por imagem e uma pequena marca “pollinations.ai” no canto. Ao postar, marque o vídeo como “conteúdo gerado por IA”.
        </p>
      )}

      {parts.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {parts.map((part, i) => {
            const option = part.options[part.index];
            return (
              <div key={i} className={cn("space-y-1.5 rounded-lg border p-2", part.removed && "opacity-50")}>
                <div className={cn("relative overflow-hidden rounded-md bg-muted", thumb)}>
                  {part.loading ? (
                    <div className="flex h-full flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
                      <Loader2 className="size-5 animate-spin" /> criando…
                    </div>
                  ) : option && !part.removed ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={`${API}/backgrounds/${token}/${option.file}`} alt={part.query} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
                      <ImageOff className="size-5" /> {part.removed ? "removida" : "sem imagem"}
                    </div>
                  )}
                  <span className="absolute left-1 top-1 rounded bg-black/60 px-1.5 text-[11px] text-white">{i + 1}</span>
                </div>
                <p className="line-clamp-2 text-[11px] text-muted-foreground">“{part.text}”</p>
                <Input className="h-7 text-[11px]" value={part.query} onChange={(e) => update(i, { query: e.target.value })} aria-label={`Busca do trecho ${i + 1}`} />
                <div className="flex items-center justify-between gap-1">
                  <Button size="icon" variant="ghost" className="size-7" disabled={part.index === 0} onClick={() => update(i, { index: part.index - 1 })} aria-label="Anterior">
                    <ChevronLeft className="size-3.5" />
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 flex-1 px-2 text-[11px]" disabled={part.loading} onClick={() => void another(i)}>
                    <RefreshCw className="size-3" /> Outra
                  </Button>
                  <Button size="icon" variant="ghost" className="size-7" disabled={part.index >= part.options.length - 1} onClick={() => update(i, { index: part.index + 1 })} aria-label="Próxima">
                    <ChevronRight className="size-3.5" />
                  </Button>
                  <Button size="icon" variant="ghost" className="size-7" onClick={() => update(i, { removed: !part.removed })} aria-label={part.removed ? "Voltar" : "Remover"}>
                    {part.removed ? <Undo2 className="size-3.5" /> : <ImageOff className="size-3.5" />}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

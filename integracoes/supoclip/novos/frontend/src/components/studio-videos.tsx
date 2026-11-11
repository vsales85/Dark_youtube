"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Clapperboard, Copy, Download, FileText, Loader2, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

type PostText = { titles: string[]; description: string; hashtags: string[] };
type StudioVideo = { id: string; title: string; status: string; step?: string; progress?: number; error?: string; format: string; post?: PostText };

function copy(text: string, what: string) {
  void navigator.clipboard.writeText(text).then(
    () => toast.success(`${what} copiado`),
    () => toast.error("Não foi possível copiar"),
  );
}

/** Title options, description and hashtags for posting, each one click to copy. */
function PostTextDialog({ video, onUpdated }: { video: StudioVideo; onUpdated: (post: PostText) => void }) {
  const [busy, setBusy] = useState(false);
  const post = video.post;

  const generate = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${API}/videos/${video.id}/post-text`, { method: "POST" });
      if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `Erro ${r.status}`);
      onUpdated(await r.json());
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <button type="button" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
          <FileText className="size-3.5" /> Título e descrição
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Texto para postar</DialogTitle>
          <DialogDescription>Sugestões da IA a partir do roteiro. Clique para copiar.</DialogDescription>
        </DialogHeader>
        {!post ? (
          <Button onClick={generate} disabled={busy}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            Gerar título, descrição e hashtags
          </Button>
        ) : (
          <div className="space-y-4 text-sm">
            <div className="space-y-1.5">
              <p className="font-medium">Títulos (escolha um)</p>
              {post.titles.map((title) => (
                <button key={title} type="button" onClick={() => copy(title, "Título")} className="flex w-full items-center justify-between gap-2 rounded-lg border p-2 text-left hover:bg-muted/50">
                  <span>{title}</span>
                  <Copy className="size-3.5 shrink-0 text-muted-foreground" />
                </button>
              ))}
            </div>
            <div className="space-y-1.5">
              <p className="font-medium">Descrição</p>
              <button type="button" onClick={() => copy(`${post.description}\n\n${post.hashtags.join(" ")}`, "Descrição")} className="w-full rounded-lg border p-2 text-left hover:bg-muted/50">
                <span className="block whitespace-pre-line">{post.description}</span>
                <span className="mt-2 block text-primary">{post.hashtags.join(" ")}</span>
                <span className="mt-2 flex items-center gap-1 text-xs text-muted-foreground"><Copy className="size-3" /> copia a descrição com as hashtags</span>
              </button>
            </div>
            <Button variant="outline" size="sm" onClick={generate} disabled={busy}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Gerar outras opções
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

const API = "/api/tasks/studio";

/** 'Vídeo do zero' renders: in progress (with the current step) and finished. */
export function StudioVideos({ refreshSignal = 0, heading, showLink = false }: { refreshSignal?: number; heading?: string; showLink?: boolean }) {
  const [videos, setVideos] = useState<StudioVideo[]>([]);

  const load = useCallback(async () => {
    const response = await fetch(`${API}/videos`, { cache: "no-store" }).catch(() => null);
    if (response?.ok) setVideos((await response.json()).videos ?? []);
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshSignal]);

  const pending = videos.some((v) => v.status === "queued" || v.status === "rendering");
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => void load(), 4000);
    return () => clearInterval(timer);
  }, [pending, load]);

  const remove = async (video: StudioVideo) => {
    if (!window.confirm(`Excluir "${video.title}"? Isso não pode ser desfeito.`)) return;
    const response = await fetch(`${API}/videos/${video.id}`, { method: "DELETE" });
    if (!response.ok) {
      toast.error((await response.json().catch(() => null))?.detail ?? `Erro ${response.status}`);
      return;
    }
    setVideos((list) => list.filter((v) => v.id !== video.id));
    toast.success("Vídeo excluído");
  };

  if (videos.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
          <Clapperboard className="size-4" />
          {heading ?? "Meus vídeos"}
          {pending && <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] normal-case text-primary">gerando…</span>}
        </h2>
        {showLink && <Link href="/studio" className="text-xs font-medium text-primary hover:underline">Novo vídeo do zero</Link>}
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {videos.map((v) => (
          <div key={v.id} className="space-y-2">
            {v.status === "done" ? (
              <video
                src={`${API}/videos/${v.id}/file`}
                controls
                preload="metadata"
                className={cn("w-full rounded-xl bg-black", v.format === "vertical" ? "aspect-[9/16]" : "aspect-video")}
              />
            ) : (
              <div className={cn("flex flex-col items-center justify-center gap-2 rounded-xl bg-muted px-3 text-center text-sm", v.format === "vertical" ? "aspect-[9/16]" : "aspect-video")}>
                {v.status === "error" ? (
                  <span className="text-destructive">Falhou: {v.error}</span>
                ) : (
                  <>
                    <Loader2 className="size-5 animate-spin" />
                    <span className="text-2xl font-semibold tabular-nums">{v.progress ?? 0}%</span>
                    <span>{v.step ?? "Na fila"}</span>
                    <div className="h-1.5 w-3/4 overflow-hidden rounded-full bg-background">
                      <div className="h-full bg-primary transition-all" style={{ width: `${v.progress ?? 3}%` }} />
                    </div>
                  </>
                )}
              </div>
            )}
            <p className="line-clamp-2 text-sm font-medium">{v.title}</p>
            {v.status === "done" && (
              <Link href={`/studio?edit=${v.id}`} className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                ✏️ Editar e gerar nova versão
              </Link>
            )}
            {v.status === "done" && (
              <PostTextDialog video={v} onUpdated={(post) => setVideos((list) => list.map((x) => (x.id === v.id ? { ...x, post } : x)))} />
            )}
            <div className="flex items-center justify-between gap-2">
              {v.status === "done" ? (
                <a href={`${API}/videos/${v.id}/file`} download className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                  <Download className="size-3.5" /> Baixar vídeo
                </a>
              ) : <span />}
              {v.status !== "queued" && v.status !== "rendering" && (
                <button
                  type="button"
                  onClick={() => void remove(v)}
                  className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="size-3.5" /> Excluir
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

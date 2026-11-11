"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ExternalLink, Flame, Loader2, Plus, Scissors, Search, Stethoscope, Trash2, Tv } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { VideoAnalysisPanel } from "@/components/video-analysis";

type Video = {
  id: string;
  url: string;
  title: string;
  channel: string;
  duration?: number | null;
  views?: number | null;
  views_per_hour?: number | null;
  published?: number | string | null;
  thumbnail: string;
  reuse_allowed?: boolean;
  license?: string | null;
};
type Channel = { channel_id: string; name: string; auto?: boolean };
type AutoCut = { title: string; channel: string; url: string; at: number; task_id?: string; error?: string };

const API = "/api/tasks/trending";
const PERIODS = [["hoje", "Hoje"], ["semana", "Esta semana"], ["mes", "Este mês"], ["ano", "Este ano"]];

async function readError(response: Response) {
  const body = await response.json().catch(() => null);
  return body?.detail || body?.error || `Erro ${response.status}`;
}

function compact(n?: number | null) {
  if (n == null) return "—";
  return new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function age(published?: number | string | null) {
  if (!published) return "";
  const ms = typeof published === "number" ? published * 1000 : Date.parse(published);
  const hours = Math.max(0, (Date.now() - ms) / 3_600_000);
  if (hours < 1) return "agora há pouco";
  if (hours < 24) return `há ${Math.round(hours)} h`;
  return `há ${Math.round(hours / 24)} dia(s)`;
}

function VideoCard({ video }: { video: Video }) {
  return (
    <div className="flex flex-col overflow-hidden rounded-xl border bg-card">
      <a href={video.url} target="_blank" rel="noreferrer" className="relative block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={video.thumbnail} alt="" loading="lazy" className="aspect-video w-full object-cover" />
        {video.views_per_hour ? (
          <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-orange-600 px-2 py-0.5 text-xs font-semibold text-white">
            <Flame className="size-3" /> {compact(video.views_per_hour)}/h
          </span>
        ) : null}
        {video.duration ? (
          <span className="absolute bottom-2 right-2 rounded bg-black/75 px-1.5 text-xs text-white">
            {Math.floor(video.duration / 60)}:{String(video.duration % 60).padStart(2, "0")}
          </span>
        ) : null}
      </a>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <p className="line-clamp-2 text-sm font-medium">{video.title}</p>
        <p className="text-xs text-muted-foreground">{video.channel}</p>
        {video.license !== undefined && (
          video.reuse_allowed ? (
            <span className="w-fit rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-300" title={video.license ?? ""}>
              ✅ Pode reutilizar (Creative Commons): dê crédito ao canal
            </span>
          ) : (
            <span className="w-fit rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-300">
              ⚠️ Direitos reservados: use só como inspiração
            </span>
          )
        )}
        <p className="text-xs text-muted-foreground">{compact(video.views)} visualizações · {age(video.published)}</p>
        <div className="mt-auto flex gap-2 pt-2">
          <Button asChild size="sm" className="flex-1">
            <Link href={`/?url=${encodeURIComponent(video.url)}`}><Scissors className="size-3.5" /> Cortar</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <a href={video.url} target="_blank" rel="noreferrer" aria-label="Abrir no YouTube"><ExternalLink className="size-3.5" /></a>
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function TrendingPage() {
  const [tab, setTab] = useState<"search" | "channels" | "analyze">("search");
  const [query, setQuery] = useState("");
  const [period, setPeriod] = useState("semana");
  const [shorts, setShorts] = useState(false);
  const [reusable, setReusable] = useState(false);
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<Video[] | null>(null);

  const [channels, setChannels] = useState<Channel[]>([]);
  const [newChannel, setNewChannel] = useState("");
  const [adding, setAdding] = useState(false);
  const [feed, setFeed] = useState<Video[] | null>(null);
  const [autocuts, setAutocuts] = useState<AutoCut[]>([]);

  const search = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    try {
      const r = await fetch(`${API}/search?${new URLSearchParams({ q: query, period, shorts: String(shorts), reusable: String(reusable) })}`, { cache: "no-store" });
      if (!r.ok) throw new Error(await readError(r));
      setResults((await r.json()).videos ?? []);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSearching(false);
    }
  };

  const loadFeed = useCallback(async () => {
    const [c, f, a] = await Promise.all([
      fetch(`${API}/channels`, { cache: "no-store" }),
      fetch(`${API}/feed`, { cache: "no-store" }),
      fetch(`${API}/autocuts`, { cache: "no-store" }),
    ]);
    if (c.ok) setChannels((await c.json()).channels ?? []);
    if (a.ok) setAutocuts((await a.json()).items ?? []);
    setFeed(f.ok ? (await f.json()).videos ?? [] : []);
  }, []);

  useEffect(() => {
    if (tab === "channels" && feed === null) void loadFeed();
  }, [tab, feed, loadFeed]);

  const addChannel = async (event: React.FormEvent) => {
    event.preventDefault();
    setAdding(true);
    try {
      const r = await fetch(`${API}/channels`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ channel: newChannel }),
      });
      if (!r.ok) throw new Error(await readError(r));
      setNewChannel("");
      setFeed(null);
      toast.success("Canal adicionado");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setAdding(false);
    }
  };

  const addOfficial = async () => {
    const r = await fetch(`${API}/channels/official`, { method: "POST" });
    if (!r.ok) {
      toast.error(await readError(r));
      return;
    }
    setChannels((await r.json()).channels ?? []);
    setFeed(null);
    toast.success("Fontes oficiais adicionadas. Conteúdo público: cite a fonte nos vídeos.");
  };

  const toggleAuto = async (channel: Channel) => {
    if (
      !channel.auto &&
      !window.confirm(
        `Ligar o corte automático de “${channel.name}”?\n\nO app vai criar cortes SOZINHO de cada vídeo novo deste canal (até 2 a cada 30 min), sem perguntar. Isso usa bastante o computador.`,
      )
    ) return;
    const r = await fetch(`${API}/channels/${channel.channel_id}/auto`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ auto: !channel.auto }),
    });
    if (!r.ok) {
      toast.error(await readError(r));
      return;
    }
    setChannels((await r.json()).channels ?? []);
    toast.success(channel.auto ? "Corte automático desligado" : "Ligado: os próximos vídeos novos deste canal serão cortados sozinhos");
  };

  const removeChannel = async (channel: Channel) => {
    const r = await fetch(`${API}/channels/${channel.channel_id}`, { method: "DELETE" });
    if (r.ok) {
      setChannels((await r.json()).channels ?? []);
      setFeed(null);
    }
  };

  return (
    <main className="mx-auto w-full max-w-7xl space-y-5 px-4 py-6 sm:px-8 md:py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Em alta</h1>
        <p className="text-sm text-muted-foreground">Ache vídeos que estão crescendo rápido e mande direto para o corte.</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Button variant={tab === "search" ? "default" : "outline"} onClick={() => setTab("search")}><Search className="size-4" /> Buscar por tema</Button>
        <Button variant={tab === "channels" ? "default" : "outline"} onClick={() => setTab("channels")}><Tv className="size-4" /> Meus canais</Button>
        <Button variant={tab === "analyze" ? "default" : "outline"} onClick={() => setTab("analyze")}><Stethoscope className="size-4" /> Analisar meu vídeo</Button>
      </div>

      {tab === "analyze" && <VideoAnalysisPanel />}

      {tab === "search" && (
        <>
          <form onSubmit={search} className="space-y-3 rounded-2xl border bg-card p-4">
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tema (ex.: abordagem policial, história do Brasil, salmo 91)" />
              <Button type="submit" disabled={searching || !query.trim()}>
                {searching ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
                Buscar
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex flex-wrap gap-1.5">
                {PERIODS.map(([id, label]) => (
                  <Button key={id} type="button" size="sm" variant={period === id ? "default" : "outline"} onClick={() => setPeriod(id)}>{label}</Button>
                ))}
              </div>
              <label className="flex items-center gap-2 text-sm"><Switch checked={shorts} onCheckedChange={setShorts} /> Só vídeos curtos (até 3 min)</label>
              <label className="flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-300">
                <Switch checked={reusable} onCheckedChange={setReusable} /> Só reutilizáveis (Creative Commons, sem problema de direitos)
              </label>
            </div>
            <p className="text-xs text-muted-foreground">Ordenado por visualizações por hora 🔥 (quem está crescendo mais rápido). A busca leva uns 20 segundos.</p>
          </form>
          {searching && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Buscando no YouTube…</p>}
          {results && !searching && (
            results.length === 0 ? (
              <p className="rounded-2xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">Nada encontrado nesse período. Tente outro tema ou um período maior.</p>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {results.map((video) => <VideoCard key={video.id} video={video} />)}
              </div>
            )
          )}
        </>
      )}

      {tab === "channels" && (
        <>
          <div className="space-y-3 rounded-2xl border bg-card p-4">
            <form onSubmit={addChannel} className="flex flex-col gap-2 sm:flex-row">
              <Input value={newChannel} onChange={(e) => setNewChannel(e.target.value)} placeholder="Link do canal ou @nome (ex.: @canaldahistoria)" />
              <Button type="submit" disabled={adding || !newChannel.trim()}>
                {adding ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                Acompanhar canal
              </Button>
            </form>
            <Button type="button" size="sm" variant="outline" onClick={addOfficial}>
              🏛️ Adicionar fontes oficiais (TV Senado, Agência Brasil)
            </Button>
            {channels.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {channels.map((channel) => (
                  <span key={channel.channel_id} className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs">
                    {channel.name}
                    <label className="inline-flex items-center gap-1 text-muted-foreground" title="Corta sozinho cada vídeo novo deste canal">
                      <Switch checked={!!channel.auto} onCheckedChange={() => void toggleAuto(channel)} className="scale-75" aria-label={`Cortar sozinho ${channel.name}`} />
                      cortar sozinho
                    </label>
                    <button type="button" aria-label={`Parar de acompanhar ${channel.name}`} onClick={() => void removeChannel(channel)} className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="size-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Os vídeos mais novos aparecem abaixo. Com “cortar sozinho” ligado, cada vídeo <b>novo</b> do canal vai para o corte automaticamente
              (verificação a cada 30 min, até 2 por vez). Vídeos que já existiam não são cortados.
            </p>
          </div>
          {autocuts.length > 0 && (
            <div className="space-y-2 rounded-2xl border bg-card p-4">
              <p className="text-sm font-medium">Cortados automaticamente</p>
              <ul className="divide-y text-sm">
                {autocuts.map((item) => (
                  <li key={`${item.url}-${item.at}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <span className="min-w-0">
                      <span className="block truncate">{item.title}</span>
                      <span className="text-xs text-muted-foreground">{item.channel} · {age(item.at)}</span>
                    </span>
                    {item.task_id ? (
                      <Button asChild size="sm" variant="outline"><Link href={`/tasks/${item.task_id}`}>Ver cortes</Link></Button>
                    ) : (
                      <span className="text-xs text-destructive">Não foi possível: {item.error}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {feed === null ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Carregando…</p>
          ) : feed.length === 0 ? (
            <p className="rounded-2xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
              {channels.length ? "Nenhum vídeo novo." : "Adicione canais que costumam bombar para acompanhar os vídeos novos deles aqui."}
            </p>
          ) : (
            <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4")}>
              {feed.map((video) => <VideoCard key={video.id} video={video} />)}
            </div>
          )}
        </>
      )}
    </main>
  );
}

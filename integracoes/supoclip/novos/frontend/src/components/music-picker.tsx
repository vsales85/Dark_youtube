"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Check, FolderOpen, Loader2, Music, Pause, Play, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

export type Track = { id: string; title: string; description?: string; feel?: string; length?: string; credit?: string };

const API = "/api/tasks/studio/music";

function readFile(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Pick background music: AI suggestions for the script, your library, or a file from the PC. Listen first. */
export function MusicPicker({
  script,
  value,
  onChange,
  volume,
  onVolume,
}: {
  script: string;
  value: Track | null;
  onChange: (track: Track | null) => void;
  volume: number;
  onVolume: (volume: number) => void;
}) {
  const [tab, setTab] = useState<"ai" | "library">("ai");
  const [suggested, setSuggested] = useState<Track[]>([]);
  const [reason, setReason] = useState("");
  const [library, setLibrary] = useState<Track[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [playing, setPlaying] = useState<string | null>(null);
  const [buffering, setBuffering] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => () => audioRef.current?.pause(), []);

  const loadLibrary = () =>
    fetch(`${API}/library`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { tracks: [] }))
      .then((body) => setLibrary(body.tracks ?? []))
      .catch(() => undefined);

  useEffect(() => {
    void loadLibrary();
  }, []);

  const suggest = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/suggest`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ script }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error(body?.detail ?? `Erro ${r.status}`);
      setSuggested(body.tracks ?? []);
      setReason(body.reason ?? "");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const toggle = (track: Track) => {
    const audio = audioRef.current ?? new Audio();
    audioRef.current = audio;
    if (playing === track.id) {
      audio.pause();
      setPlaying(null);
      return;
    }
    audio.pause();
    audio.src = `${API}/play?id=${encodeURIComponent(track.id)}`;
    audio.volume = 0.8;
    setBuffering(track.id);
    audio.oncanplay = () => setBuffering(null);
    audio.onended = () => setPlaying(null);
    audio.onerror = () => {
      setBuffering(null);
      setPlaying(null);
      toast.error("Não consegui tocar essa música agora.");
    };
    void audio.play().then(() => setPlaying(track.id)).catch(() => setBuffering(null));
  };

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      const r = await fetch(`${API}/library`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: file.name, audio: await readFile(file) }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error(body?.detail ?? `Erro ${r.status}`);
      await loadLibrary();
      onChange({ id: body.id, title: body.title });
      setTab("library");
      toast.success("Música salva na sua biblioteca e escolhida.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const list = tab === "ai" ? suggested : library;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Button size="sm" variant={tab === "ai" ? "default" : "outline"} onClick={() => setTab("ai")}><Sparkles className="size-4" /> Sugestões da IA</Button>
        <Button size="sm" variant={tab === "library" ? "default" : "outline"} onClick={() => setTab("library")}><Music className="size-4" /> Minhas músicas ({library.length})</Button>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted/50">
          {uploading ? <Loader2 className="size-4 animate-spin" /> : <FolderOpen className="size-4" />} Enviar do PC
          <input type="file" accept="audio/*" hidden onChange={(e) => void upload(e.target.files?.[0])} />
        </label>
        {value && <Button size="sm" variant="ghost" onClick={() => onChange(null)}>Sem música</Button>}
      </div>

      {tab === "ai" && (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" onClick={suggest} disabled={loading || !script.trim()}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {suggested.length ? "Sugerir outras" : "Sugerir músicas para este roteiro"}
          </Button>
          {reason && <p className="text-xs text-muted-foreground">🎼 {reason}</p>}
        </div>
      )}
      {tab === "library" && library.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Envie do PC ou coloque arquivos na pasta <b>D:\SupoClip\musicas</b> (ex.: baixados da Biblioteca de áudio do YouTube). Eles aparecem aqui para reusar.
        </p>
      )}

      {list.length > 0 && (
        <ul className="max-h-72 divide-y overflow-y-auto rounded-lg border">
          {list.map((track) => (
            <li key={track.id} className={cn("flex items-center gap-2 p-2 text-sm", value?.id === track.id && "bg-primary/5")}>
              <Button size="icon" variant="ghost" className="size-8 shrink-0" aria-label={`Ouvir ${track.title}`} onClick={() => toggle(track)}>
                {buffering === track.id ? <Loader2 className="size-4 animate-spin" /> : playing === track.id ? <Pause className="size-4" /> : <Play className="size-4" />}
              </Button>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{track.title}</span>
                <span className="block truncate text-xs text-muted-foreground">{[track.feel, track.length?.replace(/^00:/, ""), track.description].filter(Boolean).join(" · ")}</span>
              </span>
              <Button size="sm" variant={value?.id === track.id ? "default" : "outline"} onClick={() => onChange(track)}>
                {value?.id === track.id ? <><Check className="size-3.5" /> Escolhida</> : "Usar"}
              </Button>
            </li>
          ))}
        </ul>
      )}

      {value && (
        <div className="space-y-1.5 rounded-lg bg-muted/40 p-2">
          <Label>🎵 {value.title} · volume por baixo da narração: {volume}%</Label>
          <Slider aria-label="Volume da música" min={0} max={40} step={1} value={[volume]} onValueChange={([v]) => onVolume(v)} />
          {value.credit && <p className="text-xs text-muted-foreground">O crédito obrigatório vai sozinho para a descrição: “{value.credit}”.</p>}
        </div>
      )}
    </div>
  );
}

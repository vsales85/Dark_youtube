"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play, Scissors } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const fmt = (s: number) => s.toFixed(1).replace(".", ",");

/** Length of a video (data URL or URL) in seconds. */
export function videoDuration(src: string): Promise<number> {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => resolve(Number.isFinite(video.duration) ? video.duration : 0);
    video.onerror = () => resolve(0);
    video.src = src;
  });
}

/** Choose where a clip starts and ends while watching it. */
export function TrimButton({
  src,
  index,
  start,
  end,
  duration,
  onChange,
}: {
  src: string;
  index: number;
  start: number;
  end: number;
  duration: number;
  onChange: (start: number, end: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [range, setRange] = useState<[number, number]>([start, end || duration]);
  const [playing, setPlaying] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    if (open) setRange([start, end || duration]);
  }, [open, start, end, duration]);

  const playSelection = () => {
    const video = videoRef.current;
    if (!video) return;
    if (playing) {
      video.pause();
      setPlaying(false);
      return;
    }
    video.currentTime = range[0];
    void video.play();
    setPlaying(true);
  };

  const onTime = () => {
    const video = videoRef.current;
    if (video && playing && video.currentTime >= range[1]) {
      video.pause();
      setPlaying(false);
    }
  };

  const seek = (value: [number, number]) => {
    const moved = value[0] !== range[0] ? value[0] : value[1];
    setRange(value);
    if (videoRef.current) videoRef.current.currentTime = moved;
  };

  const max = Math.max(duration, 0.1);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="h-7 w-full px-1 text-[11px]">
          <Scissors className="size-3" /> {fmt(start)}–{fmt(end || duration)} s
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Cortar vídeo {index + 1}</DialogTitle>
          <DialogDescription>Arraste as duas bolinhas para escolher o começo e o fim. O vídeo mostra o ponto que você está marcando.</DialogDescription>
        </DialogHeader>
        <video ref={videoRef} src={src} muted playsInline onTimeUpdate={onTime} className="mx-auto max-h-[50vh] rounded-lg bg-black" />
        <Slider aria-label="Começo e fim" min={0} max={max} step={0.1} value={range} onValueChange={(v) => seek([v[0], v[1]] as [number, number])} />
        <div className="flex items-center justify-between text-sm">
          <span>Começa em <b>{fmt(range[0])} s</b></span>
          <span>Termina em <b>{fmt(range[1])} s</b></span>
        </div>
        <p className="text-center text-sm text-muted-foreground">Trecho escolhido: <b>{fmt(range[1] - range[0])} s</b> de {fmt(duration)} s</p>
        <DialogFooter className="gap-2 sm:justify-between">
          <Button variant="secondary" onClick={playSelection}>
            {playing ? <Pause className="size-4" /> : <Play className="size-4" />} {playing ? "Pausar" : "Tocar seleção"}
          </Button>
          <Button
            onClick={() => {
              onChange(range[0], range[1] >= duration - 0.05 ? 0 : range[1]);
              setOpen(false);
            }}
          >
            Usar este trecho
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type Item = { src: string; start: number; end: number; duration: number; isVideo: boolean };

/** Plays the chosen pieces one after another, in order (no narration). */
export function SequencePreview({ items }: { items: Item[] }) {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const item = items[current];

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  useEffect(() => {
    if (!open || !item) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (item.isVideo) {
      const video = videoRef.current;
      if (video) {
        video.currentTime = item.start;
        void video.play();
      }
    } else {
      timerRef.current = setTimeout(() => setCurrent((c) => c + 1), 3000);
    }
  }, [open, current, item]);

  const onTime = () => {
    const video = videoRef.current;
    if (video && item && video.currentTime >= (item.end || item.duration) - 0.05) setCurrent((c) => c + 1);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); setCurrent(0); }}>
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary" disabled={items.length === 0}><Play className="size-4" /> Prévia da sequência</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Prévia da sequência</DialogTitle>
          <DialogDescription>Os trechos escolhidos, na ordem. No vídeo final entram também a narração, a legenda e as transições.</DialogDescription>
        </DialogHeader>
        {item ? (
          <div className="space-y-2">
            {item.isVideo ? (
              <video key={current} ref={videoRef} src={item.src} muted playsInline onTimeUpdate={onTime} className="mx-auto max-h-[60vh] rounded-lg bg-black" />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={item.src} alt="" className="mx-auto max-h-[60vh] rounded-lg" />
            )}
            <p className="text-center text-sm text-muted-foreground">Trecho {current + 1} de {items.length}</p>
          </div>
        ) : (
          <div className="space-y-2 text-center">
            <p className="text-sm">Fim da sequência.</p>
            <Button size="sm" onClick={() => setCurrent(0)}><Play className="size-4" /> Ver de novo</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

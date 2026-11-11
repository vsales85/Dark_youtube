"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, ImageIcon, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const FORMATS = [
  { id: "shorts", label: "Capa Shorts 9:16", className: "aspect-[9/16] w-40" },
  { id: "youtube", label: "YouTube 16:9", className: "aspect-video w-72" },
];

export function ClipThumbnailsButton({ taskId, clipId, open: controlledOpen, onOpenChange }: { taskId: string; clipId: string; open?: boolean; onOpenChange?: (open: boolean) => void }) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const setOpen = onOpenChange ?? setLocalOpen;
  const [times, setTimes] = useState<number[]>([]);
  const [time, setTime] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const base = `/api/tasks/${taskId}/clips/${clipId}/thumbnail`;

  useEffect(() => {
    if (!open || times.length) return;
    fetch(`${base}/candidates`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Erro ${response.status}`);
        const result = await response.json();
        setTimes(result.times);
        setTime(result.times[0] ?? 0);
        setText((current) => current || result.text);
      })
      .catch((error) => toast.error(`Não foi possível ler o clipe: ${error.message}`));
  }, [open, base, times.length]);

  const generate = async () => {
    setBusy(true);
    try {
      const response = await fetch(base, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ time, text }),
      });
      if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? `Erro ${response.status}`);
      setVersion(Date.now());
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {controlledOpen === undefined && (
        <DialogTrigger asChild>
          <Button variant="outline" size="sm">
            <ImageIcon className="size-4" />
            Thumbs
          </Button>
        </DialogTrigger>
      )}
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Thumbnails de impacto</DialogTitle>
          <DialogDescription>Escolha o frame, ajuste o título e gere a capa do Shorts e a thumb do YouTube.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Frame</Label>
            <div className="flex gap-2">
              {times.length === 0 && <Loader2 className="size-5 animate-spin text-muted-foreground" />}
              {times.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTime(t)}
                  className={`overflow-hidden rounded-md border-2 ${time === t ? "border-primary" : "border-transparent opacity-70"}`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`${base}/frame?t=${t}`} alt={`Frame em ${t.toFixed(1)}s`} className="h-36 w-auto" />
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="thumb-text">Título</Label>
            <Textarea id="thumb-text" rows={2} value={text} onChange={(event) => setText(event.target.value)} />
            <p className="text-xs text-muted-foreground">
              Use *asteriscos* nas palavras de impacto para deixá-las em amarelo. Curto funciona melhor (3 a 7 palavras).
            </p>
          </div>

          <Button onClick={generate} disabled={busy || time === null || !text.trim()}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : <ImageIcon className="size-4" />}
            Gerar thumbnails
          </Button>

          {version > 0 && (
            <div className="flex flex-wrap items-start gap-4">
              {FORMATS.map((format) => (
                <div key={format.id} className="space-y-1.5">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`${base}/${format.id}.jpg?v=${version}`} alt={format.label} className={`${format.className} rounded-md border object-cover`} />
                  <a
                    href={`${base}/${format.id}.jpg?v=${version}`}
                    download={`thumb_${format.id}.jpg`}
                    className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    <Download className="size-3" /> {format.label}
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, Mic, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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

type Voice = { voice_id: string; name?: string };

// "0:05-0:09, 12-15" -> [[5, 9], [12, 15]]
function parseRanges(value: string): [number, number][] {
  const seconds = (part: string) => {
    const [a, b] = part.trim().split(":");
    return b === undefined ? Number(a) : Number(a) * 60 + Number(b);
  };
  return value
    .split(",")
    .map((item) => item.split("-"))
    .filter((pair) => pair.length === 2)
    .map(([a, b]) => [seconds(a), seconds(b)] as [number, number])
    .filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b) && b > a);
}

async function readError(response: Response) {
  const body = await response.json().catch(() => null);
  return (body && (body.detail || body.error)) || `Erro ${response.status}`;
}

export function ClipNarrationButton({
  taskId,
  clipId,
  onDone, open: controlledOpen, onOpenChange }: {
  taskId: string;
  clipId: string;
  onDone: () => void; open?: boolean; onOpenChange?: (open: boolean) => void }) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const setOpen = onOpenChange ?? setLocalOpen;
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voice, setVoice] = useState("");
  const [instructions, setInstructions] = useState("");
  const [script, setScript] = useState("");
  const [ranges, setRanges] = useState("");
  const [volume, setVolume] = useState(15);
  const [writing, setWriting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const base = `/api/tasks/${taskId}/clips/${clipId}/narration`;

  const stopPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  };

  const poll = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      const response = await fetch(base, { cache: "no-store" });
      if (!response.ok) return;
      const result = await response.json();
      setStatus(result.status);
      if (result.status === "done") {
        stopPolling();
        toast.success("Versão narrada criada");
        onDone();
      } else if (result.status === "error") {
        stopPolling();
        toast.error("Falha na narração", { description: result.error });
      }
    }, 4000);
  }, [base, onDone]);

  useEffect(() => stopPolling, []);

  useEffect(() => {
    if (!open || voices.length) return;
    fetch(`/api/tasks/${taskId}/narration/voices`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(await readError(response));
        const list: Voice[] = (await response.json()).voices ?? [];
        setVoices(list);
        if (list[0]) setVoice((current) => current || list[0].voice_id);
      })
      .catch((error) => toast.error(String(error.message ?? error)));
  }, [open, taskId, voices.length]);

  const writeScript = async () => {
    setWriting(true);
    try {
      const response = await fetch(`${base}/script`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ instructions, original_ranges: parseRanges(ranges) }),
      });
      if (!response.ok) throw new Error(await readError(response));
      setScript((await response.json()).script);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setWriting(false);
    }
  };

  const render = async () => {
    const response = await fetch(base, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        script,
        voice,
        original_volume: volume / 100,
        original_ranges: parseRanges(ranges),
      }),
    });
    if (!response.ok) {
      toast.error(await readError(response));
      return;
    }
    setStatus("queued");
    toast.info("Narração na fila. A voz pode levar alguns minutos.");
    poll();
  };

  const busy = status === "queued" || status === "rendering";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {controlledOpen === undefined && (
        <DialogTrigger asChild>
          <Button variant="outline" size="sm">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Mic className="size-4" />}
            Narração
          </Button>
        </DialogTrigger>
      )}
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Narração estilo matéria</DialogTitle>
          <DialogDescription>
            Cria uma nova versão do clipe com a sua voz clonada. O clipe original não muda.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="narration-voice">Voz</Label>
            <select
              id="narration-voice"
              className="h-9 w-full rounded-md border bg-background px-2 text-sm"
              value={voice}
              onChange={(event) => setVoice(event.target.value)}
            >
              {voices.map((item) => (
                <option key={item.voice_id} value={item.voice_id}>{item.name ?? item.voice_id}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="narration-ranges">Trechos com a fala original (opcional)</Label>
            <Input
              id="narration-ranges"
              placeholder="ex.: 0:05-0:09, 0:20-0:24"
              value={ranges}
              onChange={(event) => setRanges(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Nesses trechos a narração pausa e o áudio original volta a 100%.
            </p>
          </div>

          <div className="space-y-1.5">
            <div className="flex gap-2">
              {[
                { label: "Remover áudio original", value: 0 },
                { label: "Original baixinho", value: 15 },
                { label: "Original alto", value: 50 },
              ].map((preset) => (
                <Button
                  key={preset.value}
                  type="button"
                  size="sm"
                  variant={volume === preset.value ? "default" : "outline"}
                  onClick={() => setVolume(preset.value)}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
            <Label>
              Volume do áudio ORIGINAL do vídeo enquanto a narração fala:{" "}
              {volume === 0 ? "removido (só a narração)" : `${volume}%`}
            </Label>
            <Slider aria-label="Volume original" min={0} max={100} step={5} value={[volume]} onValueChange={([v]) => setVolume(v)} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="narration-instructions">Orientação para a IA (opcional)</Label>
            <Input
              id="narration-instructions"
              placeholder="ex.: tom urgente, foco na ação policial"
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
            />
            <Button variant="secondary" size="sm" onClick={writeScript} disabled={writing}>
              {writing ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Gerar roteiro com IA
            </Button>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="narration-script">Roteiro</Label>
            <Textarea
              id="narration-script"
              rows={8}
              value={script}
              onChange={(event) => setScript(event.target.value)}
              placeholder="Escreva ou gere o texto. Separe os blocos com uma linha em branco: cada bloco é falado num intervalo entre os trechos originais."
            />
          </div>
        </div>

        <DialogFooter>
          <Button onClick={render} disabled={busy || !script.trim() || !voice}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Mic className="size-4" />}
            {busy ? "Gerando..." : "Criar versão narrada"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

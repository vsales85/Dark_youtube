"use client";

import { useState } from "react";
import { toast } from "sonner";
import { EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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

export function ClipCoverButton({ taskId, clipId, onDone, open: controlledOpen, onOpenChange }: { taskId: string; clipId: string; onDone: () => void; open?: boolean; onOpenChange?: (open: boolean) => void }) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const setOpen = onOpenChange ?? setLocalOpen;
  const [top, setTop] = useState(55);
  const [height, setHeight] = useState(10);
  const [mode, setMode] = useState<"blur" | "dark">("blur");
  const [busy, setBusy] = useState(false);
  const [frameTime, setFrameTime] = useState(2);

  const apply = async () => {
    setBusy(true);
    try {
      const response = await fetch(`/api/tasks/${taskId}/clips/${clipId}/cover`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ top: top / 100, height: height / 100, mode }),
      });
      if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? `Erro ${response.status}`);
      toast.success("Nova versão criada com a legenda original coberta");
      setOpen(false);
      onDone();
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
            <EyeOff className="size-4" />
            Cobrir legenda
          </Button>
        </DialogTrigger>
      )}
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Cobrir legenda original</DialogTitle>
          <DialogDescription>
            Posicione a faixa vermelha sobre a legenda que já vem no vídeo. A nossa legenda continua no lugar dela.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-4">
          <div className="relative w-40 shrink-0 overflow-hidden rounded-md border">
            {open && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`/api/tasks/${taskId}/clips/${clipId}/thumbnail/frame?t=${frameTime}`}
                alt="Prévia do clipe"
                className="block w-full"
              />
            )}
            <div
              className={`absolute inset-x-0 border-y-2 border-red-500 ${mode === "dark" ? "bg-black/80" : "bg-white/30 backdrop-blur-md"}`}
              style={{ top: `${top}%`, height: `${height}%` }}
            />
          </div>

          <div className="flex-1 space-y-4">
            <div className="space-y-1.5">
              <Label>Posição: {top}% do topo</Label>
              <Slider aria-label="Posição" min={0} max={95} step={1} value={[top]} onValueChange={([v]) => setTop(Math.min(v, 100 - height))} />
            </div>
            <div className="space-y-1.5">
              <Label>Altura: {height}%</Label>
              <Slider aria-label="Altura" min={2} max={40} step={1} value={[height]} onValueChange={([v]) => setHeight(Math.min(v, 100 - top))} />
            </div>
            <div className="space-y-1.5">
              <Label>Momento da prévia: {frameTime}s</Label>
              <Slider aria-label="Momento" min={0} max={60} step={1} value={[frameTime]} onValueChange={([v]) => setFrameTime(v)} />
            </div>
            <div className="flex gap-2">
              <Button size="sm" type="button" variant={mode === "blur" ? "default" : "outline"} onClick={() => setMode("blur")}>Desfocar</Button>
              <Button size="sm" type="button" variant={mode === "dark" ? "default" : "outline"} onClick={() => setMode("dark")}>Faixa escura</Button>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button onClick={apply} disabled={busy}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : <EyeOff className="size-4" />}
            {busy ? "Processando..." : "Criar versão com legenda coberta"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Palette } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type Preset = { id: string; label: string };

/** Colour looks for a clip; applying one creates a new version after it. */
export function ClipColorDialog({
  taskId,
  clipId,
  onDone,
  open,
  onOpenChange,
}: {
  taskId: string;
  clipId: string;
  onDone: () => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selected, setSelected] = useState("cinema");
  const [busy, setBusy] = useState(false);
  const base = `/api/tasks/${taskId}/clips/${clipId}/color`;

  useEffect(() => {
    if (!open || presets.length) return;
    fetch(`${base}/presets`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { presets: [] }))
      .then((body) => setPresets(body.presets ?? []))
      .catch(() => undefined);
  }, [open, base, presets.length]);

  const apply = async () => {
    setBusy(true);
    try {
      const r = await fetch(base, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ preset: selected }),
      });
      if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `Erro ${r.status}`);
      toast.success("Nova versão criada com a cor aplicada");
      onOpenChange(false);
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Cor do vídeo</DialogTitle>
          <DialogDescription>Escolha um visual. Cria uma nova versão do clipe; o original não muda.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
          {[{ id: "original", label: "Original" }, ...presets].map((preset) => (
            <button
              key={preset.id}
              type="button"
              disabled={preset.id === "original"}
              onClick={() => setSelected(preset.id)}
              className={cn(
                "space-y-1 rounded-lg border-2 p-1 text-left text-xs font-medium",
                selected === preset.id ? "border-primary" : "border-transparent",
                preset.id === "original" && "opacity-70",
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`${base}/preview/${preset.id}.jpg`} alt={preset.label} loading="lazy" className="aspect-[9/16] w-full rounded-md bg-muted object-cover" />
              <span className="block px-1">{preset.label}</span>
            </button>
          ))}
        </div>
        <DialogFooter>
          <Button onClick={apply} disabled={busy || !presets.length}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Palette className="size-4" />}
            {busy ? "Aplicando..." : "Criar versão com esta cor"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

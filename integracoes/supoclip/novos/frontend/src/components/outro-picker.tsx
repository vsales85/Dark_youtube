"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Check, FolderOpen, Loader2, Mic, Trash2, Volume2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export type OutroChoice = { id: string; audio: "original" | "narrator"; text: string };
type ChannelOutros = { channel: string; outros: { id: string; name: string }[]; cta?: string };

const API = "/api/tasks/studio/outros";
export const DEFAULT_OUTRO_TEXT = "Curta e compartilhe.";
const FRASES_PRONTAS = [
  "Curta e compartilhe.",
  "Curta, compartilhe e se inscreva.",
  "Se inscreva para descobrir mais segredos.",
  "Comente o que você achou e compartilhe.",
  "Compartilhe com quem precisa ouvir isso hoje.",
  "Siga o canal para a próxima parte.",
];

function readFile(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Palette of outros (vinhetas) kept per channel; keep its sound or have the narrator speak over it. */
export function OutroPicker({
  value,
  onChange,
  channel,
}: {
  value: OutroChoice;
  onChange: (value: OutroChoice) => void;
  channel: string;
}) {
  const [groups, setGroups] = useState<ChannelOutros[]>([]);
  const [uploading, setUploading] = useState(false);

  const load = () =>
    fetch(API, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { channels: [] }))
      .then((body) => setGroups(body.channels ?? []))
      .catch(() => undefined);

  useEffect(() => {
    void load();
  }, []);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    const target = window.prompt("De qual canal é esta vinheta?", channel || "")?.trim();
    if (!target) return;
    setUploading(true);
    try {
      const r = await fetch(API, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ channel: target, name: file.name, video: await readFile(file) }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error(body?.detail ?? `Erro ${r.status}`);
      await load();
      onChange({ ...value, id: body.id });
      toast.success(`Vinheta salva em canais\\${target}\\vinhetas e escolhida.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Apagar esta vinheta da pasta do canal?")) return;
    await fetch(`${API}?id=${encodeURIComponent(id)}`, { method: "DELETE" });
    if (value.id === id) onChange({ ...value, id: "" });
    void load();
  };

  /** Frase final do canal dono da vinheta (canais/<canal>/cta.txt). */
  const ctaOf = (outroId: string) => {
    const dono = outroId.split("/")[0];
    return groups.find((g) => g.channel === dono)?.cta || DEFAULT_OUTRO_TEXT;
  };
  const donoAtual = value.id.split("/")[0];
  const [salvando, setSalvando] = useState(false);
  const editado = useRef(false);

  // A frase sempre segue o canal da vinheta escolhida (inclusive ao reabrir
  // configuracoes salvas), a menos que o usuario tenha editado nesta sessao.
  useEffect(() => {
    if (value.audio !== "narrator" || !value.id || editado.current) return;
    const cta = groups.find((g) => g.channel === donoAtual)?.cta;
    if (cta && cta !== value.text) onChange({ ...value, text: cta });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groups, value.id, value.audio]);
  const salvarCta = async () => {
    setSalvando(true);
    try {
      const r = await fetch(`${API}/cta`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ channel: donoAtual, text: value.text }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error(body?.detail ?? `Erro ${r.status}`);
      await load();
      toast.success(`Frase final salva para o canal ${donoAtual}`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSalvando(false);
    }
  };

  // Show the active channel's outros first.
  const ordered = [...groups].sort((a, b) => Number(b.channel === channel) - Number(a.channel === channel));

  return (
    <div className="space-y-3 rounded-xl border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Label>Vinheta no final do vídeo</Label>
        <div className="flex gap-1.5">
          <Button size="sm" variant={!value.id ? "default" : "outline"} onClick={() => onChange({ ...value, id: "" })}>Sem vinheta</Button>
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm hover:bg-muted/50">
            {uploading ? <Loader2 className="size-4 animate-spin" /> : <FolderOpen className="size-4" />} Adicionar vinheta
            <input type="file" accept="video/*" hidden onChange={(e) => void upload(e.target.files?.[0])} />
          </label>
        </div>
      </div>

      {ordered.length === 0 && (
        <p className="text-xs text-muted-foreground">Nenhuma vinheta ainda. Clique em “Adicionar vinheta” ou coloque vídeos em D:\SupoClip\canais\&lt;canal&gt;\vinhetas.</p>
      )}

      {ordered.map((group) => (
        <div key={group.channel} className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">{group.channel}</p>
          <div className="flex flex-wrap gap-3">
            {group.outros.map((outro) => (
              <div key={outro.id} className={cn("w-28 space-y-1 rounded-lg border-2 p-1", value.id === outro.id ? "border-primary" : "border-transparent")}>
                <video
                  src={`${API}/file?id=${encodeURIComponent(outro.id)}`}
                  muted
                  loop
                  playsInline
                  preload="metadata"
                  onMouseEnter={(e) => void e.currentTarget.play()}
                  onMouseLeave={(e) => e.currentTarget.pause()}
                  className="aspect-[9/16] w-full rounded-md bg-black object-cover"
                />
                <p className="line-clamp-2 text-[11px]">{outro.name}</p>
                <div className="flex items-center justify-between">
                  <Button size="sm" variant={value.id === outro.id ? "default" : "outline"} className="h-6 px-2 text-[11px]" onClick={() => { editado.current = false; onChange({ ...value, id: outro.id, text: value.audio === "narrator" ? ctaOf(outro.id) : value.text }); }}>
                    {value.id === outro.id ? <><Check className="size-3" /> Escolhida</> : "Usar"}
                  </Button>
                  <button type="button" aria-label="Apagar vinheta" onClick={() => void remove(outro.id)} className="text-muted-foreground hover:text-destructive">
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {value.id && (
        <div className="space-y-2 rounded-lg bg-muted/40 p-2">
          <div className="flex flex-wrap gap-1.5">
            <Button size="sm" variant={value.audio === "original" ? "default" : "outline"} onClick={() => onChange({ ...value, audio: "original" })}>
              <Volume2 className="size-4" /> Manter o som da vinheta
            </Button>
            <Button size="sm" variant={value.audio === "narrator" ? "default" : "outline"} onClick={() => onChange({ ...value, audio: "narrator", text: ctaOf(value.id) })}>
              <Mic className="size-4" /> O narrador fala
            </Button>
          </div>
          {value.audio === "narrator" && (
            <>
              <Input value={value.text} onChange={(e) => { editado.current = true; onChange({ ...value, text: e.target.value }); }} placeholder={DEFAULT_OUTRO_TEXT} />
              <div className="flex flex-wrap gap-1.5">
                {FRASES_PRONTAS.map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => { editado.current = true; onChange({ ...value, text: f }); }}
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-[11px] hover:bg-muted",
                      value.text.trim() === f && "border-primary bg-primary/10 font-medium",
                    )}
                  >
                    {f}
                  </button>
                ))}
              </div>
              {value.text.trim() !== (groups.find((g) => g.channel === donoAtual)?.cta ?? "") && (
                <Button size="sm" variant="secondary" disabled={salvando || !value.text.trim()} onClick={() => void salvarCta()}>
                  {salvando ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />} Salvar como frase padrão de {donoAtual}
                </Button>
              )}
              <p className="text-xs text-muted-foreground">Cada canal tem sua frase final. Falado com a mesma voz do vídeo; o som da vinheta fica baixinho por baixo.</p>
            </>
          )}
          <p className="text-xs text-muted-foreground">Passe o mouse sobre a vinheta para assistir.</p>
        </div>
      )}
    </div>
  );
}

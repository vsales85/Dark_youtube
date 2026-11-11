"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Loader2, Play, Plus, Sparkles, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export type Pronunciation = { from: string; to: string };
type Hint = { word: string; spoken: string; reason: string };

const API = "/api/tasks/studio";

async function readError(response: Response) {
  const body = await response.json().catch(() => null);
  return body?.detail || body?.error || `Erro ${response.status}`;
}

/** Saved respellings (server-side, per user) plus an AI review of the script. */
export function PronunciationPanel({
  script,
  onChange,
  onListen,
}: {
  script: string;
  onChange: (items: Pronunciation[]) => void;
  onListen: (text: string) => void;
}) {
  const [items, setItems] = useState<Pronunciation[]>([]);
  const [hints, setHints] = useState<Hint[] | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [draft, setDraft] = useState<Pronunciation>({ from: "", to: "" });

  useEffect(() => {
    fetch(`${API}/pronunciations`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((body) => {
        setItems(body.items ?? []);
        onChange(body.items ?? []);
      })
      .catch(() => undefined);
    // onChange is a state setter from the parent; load once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async (next: Pronunciation[]) => {
    setItems(next);
    onChange(next);
    const r = await fetch(`${API}/pronunciations`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ items: next }),
    });
    if (!r.ok) toast.error(await readError(r));
  };

  const add = (entry: Pronunciation) => {
    if (!entry.from.trim() || !entry.to.trim()) return;
    const rest = items.filter((i) => i.from.toLowerCase() !== entry.from.trim().toLowerCase());
    void save([...rest, { from: entry.from.trim(), to: entry.to.trim() }]);
  };

  const review = async () => {
    setReviewing(true);
    try {
      const r = await fetch(`${API}/pronunciations/review`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ script }),
      });
      if (!r.ok) throw new Error(await readError(r));
      const list: Hint[] = (await r.json()).hints ?? [];
      setHints(list);
      if (list.length === 0) toast.success("Nenhuma palavra difícil encontrada no roteiro");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setReviewing(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-dashed p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-medium">Revisar pronúncia com IA</p>
            <p className="text-xs text-muted-foreground">A IA lê o roteiro e aponta nomes, siglas e palavras estrangeiras que a voz pode errar.</p>
          </div>
          <Button size="sm" variant="secondary" onClick={review} disabled={reviewing || !script.trim()}>
            {reviewing ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            Revisar roteiro
          </Button>
        </div>
        {hints && hints.length > 0 && (
          <ul className="mt-3 divide-y rounded-lg border">
            {hints.map((hint, index) => (
              <li key={hint.word} className="flex flex-wrap items-center gap-2 p-2 text-sm">
                <span className="font-medium">{hint.word}</span>
                <span className="text-muted-foreground">→</span>
                <Input
                  className="h-8 w-40"
                  value={hint.spoken}
                  onChange={(e) => setHints((list) => list && list.map((h, j) => (j === index ? { ...h, spoken: e.target.value } : h)))}
                  aria-label={`Como falar ${hint.word}`}
                />
                <span className="text-xs text-muted-foreground">{hint.reason}</span>
                <span className="ml-auto flex gap-1">
                  <Button size="icon" variant="ghost" className="size-8" aria-label={`Ouvir ${hint.spoken}`} onClick={() => onListen(hint.spoken)}>
                    <Play className="size-3.5" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      add({ from: hint.word, to: hint.spoken });
                      setHints((list) => list && list.filter((h) => h.word !== hint.word));
                    }}
                  >
                    <Check className="size-3.5" /> Aceitar
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setHints((list) => list && list.filter((h) => h.word !== hint.word))}>
                    Ignorar
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="mb-2 text-sm font-medium">Dicionário ({items.length})</p>
        <p className="mb-2 text-xs text-muted-foreground">Só a voz muda; a legenda mantém a escrita certa. Fica salvo na sua conta e vale para todos os vídeos.</p>
        <ul className="max-h-56 divide-y overflow-y-auto rounded-lg border">
          {items.length === 0 && <li className="p-2 text-xs text-muted-foreground">Nenhuma palavra ainda.</li>}
          {items.map((item) => (
            <li key={item.from} className="flex items-center gap-2 p-2 text-sm">
              <span className="font-medium">{item.from}</span>
              <span className="text-muted-foreground">soa como</span>
              <span>{item.to}</span>
              <span className="ml-auto flex gap-1">
                <Button size="icon" variant="ghost" className="size-8" aria-label={`Ouvir ${item.to}`} onClick={() => onListen(item.to)}>
                  <Play className="size-3.5" />
                </Button>
                <Button size="icon" variant="ghost" className="size-8" aria-label={`Remover ${item.from}`} onClick={() => void save(items.filter((i) => i.from !== item.from))}>
                  <Trash2 className="size-3.5" />
                </Button>
              </span>
            </li>
          ))}
        </ul>
        <form
          className="mt-2 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            add(draft);
            setDraft({ from: "", to: "" });
          }}
        >
          <Input className="h-8" placeholder="Como escreve (ex.: Cohen)" value={draft.from} onChange={(e) => setDraft({ ...draft, from: e.target.value })} />
          <Input className="h-8" placeholder="Como deve soar (ex.: Côen)" value={draft.to} onChange={(e) => setDraft({ ...draft, to: e.target.value })} />
          <Button size="sm" type="submit" disabled={!draft.from.trim() || !draft.to.trim()}>
            <Plus className="size-3.5" /> Adicionar
          </Button>
        </form>
      </div>
    </div>
  );
}

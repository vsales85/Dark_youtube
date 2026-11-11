"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { FolderOpen, Loader2, Mic, Plus, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const API = "/api/tasks/studio";
const SAMPLE_TEXT =
  "Hoje eu quero falar com você sobre esperança. Mesmo nos dias difíceis, existe um caminho. Respire fundo, confie e dê o próximo passo, com calma e com fé.";

function toDataUrl(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** "Monte sua voz": record or upload 10-30 s and turn it into a narrator voice. */
export function CreateVoiceDialog({ onCreated }: { onCreated: (voiceId: string) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [gender, setGender] = useState<"Male" | "Female">("Male");
  const [audio, setAudio] = useState<{ blob: Blob; label: string } | null>(null);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
    recorderRef.current?.stream.getTracks().forEach((t) => t.stop());
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timerRef.current) clearInterval(timerRef.current);
        setRecording(false);
        setAudio({ blob: new Blob(chunks, { type: recorder.mimeType }), label: "Gravação do microfone" });
      };
      recorderRef.current = recorder;
      recorder.start();
      setSeconds(0);
      setRecording(true);
      timerRef.current = setInterval(() => {
        setSeconds((s) => {
          if (s + 1 >= 30) recorder.state === "recording" && recorder.stop();
          return s + 1;
        });
      }, 1000);
    } catch {
      toast.error("Não consegui acessar o microfone. Permita o acesso no navegador.");
    }
  };

  const save = async () => {
    if (!audio) return;
    setSaving(true);
    try {
      const r = await fetch(`${API}/my-voices`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name, gender, consent, audio: await toDataUrl(audio.blob) }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error(body?.detail ?? `Erro ${r.status}`);
      toast.success(`Voz criada (${body.seconds} s de referência). Teste com ▶.`);
      onCreated(body.id);
      setOpen(false);
      setName("");
      setAudio(null);
      setConsent(false);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline"><Plus className="size-4" /> Criar minha voz</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Monte sua voz</DialogTitle>
          <DialogDescription>Grave pelo microfone ou envie um áudio. O app limpa a gravação e cria uma voz para narrar seus vídeos.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="voice-name">Nome da voz</Label>
            <Input id="voice-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Minha voz, Minha voz – Oração" />
          </div>
          <div className="space-y-1.5">
            <Label>Gênero</Label>
            <div className="flex gap-1.5">
              <Button size="sm" variant={gender === "Male" ? "default" : "outline"} onClick={() => setGender("Male")}>Masculina</Button>
              <Button size="sm" variant={gender === "Female" ? "default" : "outline"} onClick={() => setGender("Female")}>Feminina</Button>
            </div>
          </div>
          <div className="space-y-2">
            <Label>Áudio (10 a 30 segundos, uma pessoa falando, sem música)</Label>
            <div className="flex flex-wrap gap-2">
              {recording ? (
                <Button size="sm" variant="destructive" onClick={() => recorderRef.current?.stop()}>
                  <Square className="size-4" /> Parar ({seconds} s)
                </Button>
              ) : (
                <Button size="sm" onClick={startRecording}><Mic className="size-4" /> Gravar do microfone</Button>
              )}
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted/50">
                <FolderOpen className="size-4" /> Enviar arquivo
                <input
                  type="file"
                  accept="audio/*,video/*"
                  hidden
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) setAudio({ blob: file, label: file.name });
                  }}
                />
              </label>
            </div>
            {audio && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">{audio.label}</p>
                <audio controls src={URL.createObjectURL(audio.blob)} className="h-9 w-full" />
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Ao gravar, leia em voz natural, num lugar silencioso: <i>“{SAMPLE_TEXT}”</i> Para uma voz de oração, grave lendo uma oração, calmo e devagar.
            </p>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <Checkbox checked={consent} onCheckedChange={(v) => setConsent(v === true)} className="mt-0.5" />
            Declaro que a voz é minha ou que a pessoa autorizou o uso dela nos meus vídeos.
          </label>
        </div>
        <DialogFooter>
          <Button onClick={save} disabled={saving || recording || !audio || !name.trim() || !consent}>
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Mic className="size-4" />}
            Criar voz
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

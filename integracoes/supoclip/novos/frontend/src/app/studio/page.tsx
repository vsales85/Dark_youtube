"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Check, ChevronDown, ImagePlus, Lightbulb, Loader2, Play, Sparkles, SpellCheck, Square, Trash2, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { StudioVideos } from "@/components/studio-videos";
import { PronunciationPanel, type Pronunciation } from "@/components/pronunciation-panel";
import { CreateVoiceDialog } from "@/components/create-voice-dialog";
import { FactCheckPanel } from "@/components/fact-check-panel";
import { BackgroundPicker, type Pick } from "@/components/background-picker";
import { MusicPicker, type Track } from "@/components/music-picker";
import { SequencePreview, TrimButton, videoDuration } from "@/components/media-trim";
import { DEFAULT_OUTRO_TEXT, OutroPicker, type OutroChoice } from "@/components/outro-picker";

type Voice = { id: string; name: string; gender?: string; group: string };
type Profile = {
  id: string; name: string; subject?: string; voice?: string; tone?: string; speed?: number; accent?: number;
  expressive?: number; cta_on?: boolean; cta_text?: string; cta_link?: string; look?: string; format?: string;
  transition?: string; effect?: string; hook?: boolean; seconds?: number; outro?: string; outro_audio?: string; outro_text?: string; pause?: number;
};

const API = "/api/tasks/studio";
const STEPS = ["Roteiro", "Voz", "Pronúncia", "Fundo", "Finalizar"];
// Presets only move the voice sliders; "Normal" is the app's default setup.
const TONES = [
  { id: "normal", label: "Normal", speed: 0, expressive: 50, accent: 30, pause: 0.25, hint: "Como sempre foi: fala natural." },
  { id: "oracao", label: "🙏 Oração", speed: -5, expressive: 35, accent: 25, pause: 0.6, hint: "Calma e reverente, com uma pausa curta depois de cada frase. Se ficar lenta, deixe a velocidade em 0." },
  { id: "noticia", label: "📰 Notícia", speed: 5, expressive: 45, accent: 20, pause: 0.25, hint: "Ritmo firme e neutro, de locutor." },
  { id: "suspense", label: "🕵️ Suspense", speed: -5, expressive: 70, accent: 30, pause: 0.6, hint: "Um pouco mais lento e dramático." },
  { id: "motivacional", label: "🔥 Motivacional", speed: 10, expressive: 80, accent: 30, pause: 0.25, hint: "Mais rápido e intenso." },
];

const LOOKS = [
  ["", "Natural"], ["cinema", "🎬 Cinema"], ["dramatico", "Dramático"], ["quente", "Quente"],
  ["frio", "Frio"], ["vintage", "Vintage"], ["pb", "Preto e branco"],
];

const TRANSITIONS = [
  ["fade", "Esmaecer"], ["fadeblack", "Escurecer (preto)"], ["dissolve", "Dissolver"], ["zoomin", "Zoom"],
  ["slideleft", "Deslizar para o lado"], ["slideup", "Deslizar para cima"], ["circleopen", "Círculo"],
  ["wipeleft", "Cortina"], ["none", "Corte seco"],
];

async function readError(response: Response) {
  const body = await response.json().catch(() => null);
  return body?.detail || body?.error || `Erro ${response.status}`;
}

function readFile(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Collapsed block for options most videos never touch. */
function Advanced({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details className="group rounded-xl border">
      <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 text-sm font-medium">
        {title}
        <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
      </summary>
      <div className="space-y-4 border-t p-3">{children}</div>
    </details>
  );
}

export default function StudioPage() {
  const [step, setStep] = useState(0);

  const [theme, setTheme] = useState("");
  const [seconds, setSeconds] = useState(45);
  const [script, setScript] = useState("");
  const [writing, setWriting] = useState(false);
  const [fixing, setFixing] = useState(false);
  const [sources, setSources] = useState<string[]>([]);
  const [picks, setPicks] = useState<Pick[]>([]);
  const [hook, setHook] = useState(true);
  const [hookText, setHookText] = useState("");
  const [look, setLook] = useState("");
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeProfile, setActiveProfile] = useState("");
  const [daily, setDaily] = useState("");

  useEffect(() => {
    fetch(`${API}/profiles`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { profiles: [] }))
      .then((body) => setProfiles(body.profiles ?? []))
      .catch(() => undefined);
  }, []);

  const [voices, setVoices] = useState<Voice[]>([]);
  const [voice, setVoice] = useState("");
  const [filter, setFilter] = useState("Todas");
  const [speed, setSpeed] = useState(0);
  const [accent, setAccent] = useState(30);
  const [expressive, setExpressive] = useState(50);
  const [tone, setTone] = useState("normal");
  const [pause, setPause] = useState(0.25);
  const [outro, setOutro] = useState<OutroChoice>({ id: "", audio: "narrator", text: DEFAULT_OUTRO_TEXT });
  const [subject, setSubject] = useState("");
  const [ideas, setIdeas] = useState<{ theme: string; hook: string }[]>([]);
  const [loadingIdeas, setLoadingIdeas] = useState(false);

  useEffect(() => {
    try {
      setSubject(localStorage.getItem("studio.subject") ?? "");
    } catch {
      /* storage blocked: start empty */
    }
  }, []);

  const saveSubject = (value: string) => {
    setSubject(value);
    try {
      localStorage.setItem("studio.subject", value);
    } catch {
      /* storage blocked: keep for this visit */
    }
  };

  const loadIdeas = async () => {
    setLoadingIdeas(true);
    try {
      const r = await fetch(`${API}/ideas`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ subject, avoid: ideas.map((i) => i.theme) }),
      });
      if (!r.ok) throw new Error(await readError(r));
      setIdeas((await r.json()).ideas ?? []);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoadingIdeas(false);
    }
  };

  const applyTone = (id: string) => {
    const preset = TONES.find((t) => t.id === id);
    if (!preset) return;
    setTone(id);
    setSpeed(preset.speed);
    setExpressive(preset.expressive);
    setAccent(preset.accent);
    setPause(preset.pause);
  };
  const [testPhrase, setTestPhrase] = useState("Naquele ano, o presidente Getúlio Vargas precisava de um pretexto.");
  const [playing, setPlaying] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [pronunciation, setPronunciation] = useState<Pronunciation[]>([]);

  const [images, setImages] = useState<string[]>([]);
  const [mediaMeta, setMediaMeta] = useState<{ start: number; end: number; duration: number }[]>([]);
  const [music, setMusic] = useState<Track | null>(null);
  const [musicVolume, setMusicVolume] = useState(12);
  const [format, setFormat] = useState<"vertical" | "horizontal">("vertical");
  const [captions, setCaptions] = useState(true);
  const [ctaOn, setCtaOn] = useState(false);
  const [ctaText, setCtaText] = useState("Acesse o link na descrição.");
  const [ctaLink, setCtaLink] = useState("");
  const [transition, setTransition] = useState("fade");
  const [effect, setEffect] = useState("zoom");
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);

  const loadVoices = (select?: string) =>
    fetch(`${API}/voices`, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) throw new Error(await readError(r));
        const list: Voice[] = (await r.json()).voices ?? [];
        setVoices(list);
        const preferred = list.find((v) => v.group === "Minhas vozes") ?? list.find((v) => v.id.includes("Antonio")) ?? list[0];
        if (select) setVoice(select);
        else if (preferred) setVoice((current) => current || preferred.id);
      })
      .catch((e) => toast.error(`Vozes indisponíveis: ${e.message}`));

  useEffect(() => {
    void loadVoices();
    // Load once on open; later reloads are explicit (after create/delete).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const deleteVoice = async (v: Voice) => {
    if (!window.confirm(`Apagar a voz "${v.name}"? A gravação de referência será removida.`)) return;
    const r = await fetch(`${API}/my-voices/${v.id.replace(/^vs:/, "")}`, { method: "DELETE" });
    if (!r.ok) {
      toast.error(await readError(r));
      return;
    }
    if (voice === v.id) setVoice("");
    void loadVoices();
  };

  const voiceSettings = voice.startsWith("vs:") ? { cfg_weight: accent / 100, exaggeration: expressive / 100 } : undefined;
  const selectedVoice = voices.find((v) => v.id === voice);
  const words = script.trim() ? script.trim().split(/\s+/).length : 0;
  const paragraphs = script.split(/\n\s*\n/).filter((p) => p.trim()).length;
  const sentences = (script.match(/[.!?…]+(\s|$)/g) ?? []).length;
  // Measured on real renders: cloned voices speak ~1.9 words/s, Edge ~2.5; long
  // pauses add their length after every sentence.
  // The spoken call to action and the narrator's outro line are part of the audio too.
  const extraWords =
    (ctaOn ? ctaText.split(/\s+/).filter(Boolean).length : 0) +
    (outro.id && outro.audio === "narrator" ? outro.text.split(/\s+/).filter(Boolean).length : 0);
  const narrationSeconds = words
    ? Math.round(
        (words + extraWords) / ((voice.startsWith("vs:") ? 1.9 : 2.5) * (1 + speed / 100)) +
          (pause >= 0.6 ? sentences * pause : Math.ceil(script.length / 280) * 0.25),
      )
    : 0;
  const sceneCount = images.length + picks.length;
  const paragraphMismatch = paragraphs > 1 && sceneCount > 1 && paragraphs !== sceneCount;

  // One paragraph per scene, keeping the author's own breaks: too many ->
  // merge the shortest neighbouring pair; too few -> split the longest
  // paragraph at the sentence end nearest its middle. Words never change.
  const fitParagraphsToScenes = () => {
    const count = (text: string) => text.split(/\s+/).filter(Boolean).length;
    let parts = script.split(/\n\s*\n/).map((p) => p.replace(/\s*\n\s*/g, " ").trim()).filter(Boolean);
    while (parts.length > sceneCount) {
      let best = 0;
      for (let i = 1; i < parts.length - 1; i++) {
        if (count(parts[i]) + count(parts[i + 1]) < count(parts[best]) + count(parts[best + 1])) best = i;
      }
      parts = [...parts.slice(0, best), `${parts[best]} ${parts[best + 1]}`, ...parts.slice(best + 2)];
    }
    while (parts.length < sceneCount) {
      const longest = parts.reduce((max, p, i) => (count(p) > count(parts[max]) ? i : max), 0);
      const sentences = parts[longest].split(/(?<=[.!?…,])\s+/);
      if (sentences.length < 2) {
        toast.error(`Não há frases suficientes para ${sceneCount} cenas. Escreva mais uma frase ou remova uma cena.`);
        return;
      }
      const half = count(parts[longest]) / 2;
      let cut = 1, bestGap = Infinity, running = 0;
      sentences.slice(0, -1).forEach((sentence, i) => {
        running += count(sentence);
        if (Math.abs(running - half) < bestGap) { bestGap = Math.abs(running - half); cut = i + 1; }
      });
      parts = [...parts.slice(0, longest), sentences.slice(0, cut).join(" "), sentences.slice(cut).join(" "), ...parts.slice(longest + 1)];
    }
    const before = script;
    setScript(parts.join("\n\n"));
    toast.success(`Roteiro em ${sceneCount} parágrafos, um por cena.`, { action: { label: "Desfazer", onClick: () => setScript(before) } });
  };

  const groups = useMemo(() => ["Todas", "Femininas", "Masculinas", ...Array.from(new Set(voices.map((v) => v.group)))], [voices]);
  const shown = voices.filter((v) =>
    filter === "Todas" ? true : filter === "Femininas" ? v.gender === "Female" : filter === "Masculinas" ? v.gender === "Male" : v.group === filter,
  );

  const backgrounds = images.length + picks.length;
  const missing = [!script.trim() && "roteiro", !voice && "voz", backgrounds === 0 && "imagens de fundo"].filter(Boolean) as string[];
  const done = [!!script.trim(), !!voice, true, backgrounds > 0, false];

  const writeScript = async () => {
    setWriting(true);
    try {
      const r = await fetch(`${API}/script`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ theme, seconds }),
      });
      if (!r.ok) throw new Error(await readError(r));
      setScript((await r.json()).script);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setWriting(false);
    }
  };

  const fixScript = async () => {
    setFixing(true);
    const before = script;
    try {
      const r = await fetch(`${API}/script/fix`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ script }),
      });
      if (!r.ok) throw new Error(await readError(r));
      const fixed: string = (await r.json()).script;
      if (fixed === before) {
        toast.success("Nenhum erro encontrado");
        return;
      }
      setScript(fixed);
      toast.success("Ortografia corrigida", { action: { label: "Desfazer", onClick: () => setScript(before) } });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setFixing(false);
    }
  };

  const preview = async (id: string, text?: string, key = id) => {
    audioRef.current?.pause();
    if (playing === key) {
      setPlaying(null);
      return;
    }
    setPlaying(key);
    try {
      const r = await fetch(`${API}/sample`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ voice: id, speed, text, pronunciation, voice_settings: id.startsWith("vs:") ? voiceSettings : undefined }),
      });
      if (!r.ok) throw new Error(await readError(r));
      const audio = new Audio(URL.createObjectURL(await r.blob()));
      audioRef.current = audio;
      audio.onended = () => setPlaying(null);
      await audio.play();
    } catch (e) {
      setPlaying(null);
      toast.error((e as Error).message);
    }
  };

  const addImages = async (files: FileList | null) => {
    if (!files) return;
    const data = await Promise.all(Array.from(files).slice(0, Math.max(0, 12 - images.length - picks.length)).map(readFile));
    const meta = await Promise.all(
      data.map(async (src) => ({ start: 0, end: 0, duration: src.startsWith("data:video/") ? await videoDuration(src) : 0 })),
    );
    setImages((current) => [...current, ...data]);
    setMediaMeta((current) => [...current, ...meta]);
  };

  // Keep each item's cut (start/end) attached to it when reordering/removing.
  const moveMedia = (index: number, delta: number) => {
    const swap = <T,>(list: T[]) => {
      const next = [...list];
      [next[index], next[index + delta]] = [next[index + delta], next[index]];
      return next;
    };
    setImages(swap);
    setMediaMeta(swap);
  };

  const removeMedia = (index: number) => {
    setImages((list) => list.filter((_, j) => j !== index));
    setMediaMeta((list) => list.filter((_, j) => j !== index));
  };

  const setTrim = (index: number, start: number, end: number) =>
    setMediaMeta((list) => list.map((m, j) => (j === index ? { ...m, start, end } : m)));

  const videoSeconds = mediaMeta.reduce((sum, m, i) => sum + (images[i]?.startsWith("data:video/") ? (m.end || m.duration) - m.start : 0), 0);

  const create = async () => {
    setCreating(true);
    try {
      const r = await fetch(`${API}/videos`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: theme || script.slice(0, 60),
          script,
          voice,
          speed,
          format,
          captions,
          images,
          image_starts: mediaMeta.map((m) => m.start),
          image_ends: mediaMeta.map((m) => m.end),
          music_track: music?.id,
          music_volume: musicVolume / 100,
          pronunciation,
          voice_settings: voiceSettings,
          pause,
          outro: outro.id,
          outro_audio: outro.audio,
          outro_text: outro.text,
          transition,
          effect,
          cta_text: ctaOn ? ctaText : "",
          cta_link: ctaOn ? ctaLink : "",
          sources,
          picks,
          hook,
          hook_text: hookText,
          look,
        }),
      });
      if (!r.ok) throw new Error(await readError(r));
      toast.success("Vídeo na fila! Acompanhe abaixo ou na Biblioteca.");
      setRefresh((n) => n + 1);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setCreating(false);
    }
  };

  // "Editar" on a finished video opens /studio?edit=<id> with the same choices and media.
  useEffect(() => {
    const editId = new URLSearchParams(window.location.search).get("edit");
    if (!editId) return;
    const toDataUrl = (blob: Blob) =>
      new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(blob);
      });
    (async () => {
      const r = await fetch(`${API}/videos/${editId}/settings`, { cache: "no-store" });
      if (!r.ok) throw new Error(await readError(r));
      const { options: o, media } = (await r.json()) as { options: Record<string, unknown>; media: string[] };
      setScript(String(o.script ?? ""));
      setTheme(String(o.title ?? ""));
      if (o.voice) setVoice(String(o.voice));
      if (typeof o.speed === "number") setSpeed(o.speed);
      if (typeof o.pause === "number") setPause(o.pause);
      const vs = o.voice_settings as { cfg_weight?: number; exaggeration?: number } | undefined;
      if (vs?.cfg_weight !== undefined) setAccent(Math.round(vs.cfg_weight * 100));
      if (vs?.exaggeration !== undefined) setExpressive(Math.round(vs.exaggeration * 100));
      if (o.format === "vertical" || o.format === "horizontal") setFormat(o.format);
      if (typeof o.captions === "boolean") setCaptions(o.captions);
      if (o.transition) setTransition(String(o.transition));
      if (o.effect) setEffect(String(o.effect));
      if (typeof o.look === "string") setLook(o.look);
      if (typeof o.hook === "boolean") setHook(o.hook);
      if (typeof o.hook_text === "string") setHookText(o.hook_text);
      if (o.cta_text) { setCtaOn(true); setCtaText(String(o.cta_text)); }
      if (o.cta_link) setCtaLink(String(o.cta_link));
      if (typeof o.music_volume === "number") setMusicVolume(Math.round(o.music_volume * 100));
      if (Array.isArray(o.pronunciation)) setPronunciation(o.pronunciation as Pronunciation[]);
      if (Array.isArray(o.sources)) setSources(o.sources as string[]);
      const savedOutro = o.outro as { id?: string; audio?: string; text?: string } | null | undefined;
      if (savedOutro?.id) {
        setOutro({ id: savedOutro.id, audio: savedOutro.audio === "original" ? "original" : "narrator", text: savedOutro.text || DEFAULT_OUTRO_TEXT });
      }
      if (o.music_track) setMusic({ id: String(o.music_track), title: String(o.music_track).split(":").slice(1).join(":").replace(/\.\w+$/, "") });
      const starts = (o.starts ?? {}) as Record<string, number>;
      const ends = (o.ends ?? {}) as Record<string, number>;
      const loaded = await Promise.all(
        media.map(async (name) => {
          const blob = await (await fetch(`${API}/videos/${editId}/media/${encodeURIComponent(name)}`)).blob();
          const src = await toDataUrl(blob);
          const duration = src.startsWith("data:video/") ? await videoDuration(src) : 0;
          return { src, meta: { start: starts[name] ?? 0, end: ends[name] ?? 0, duration } };
        }),
      );
      setImages(loaded.map((m) => m.src));
      setMediaMeta(loaded.map((m) => m.meta));
      setStep(0);
      toast.success("Vídeo aberto para edição. Ao criar, sai uma nova versão (a anterior continua na Biblioteca).");
    })().catch((e) => toast.error(`Não consegui abrir o vídeo para editar: ${(e as Error).message}`));
    // Runs once when the page opens with ?edit=.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const thumb = format === "vertical" ? "h-40 w-24" : "h-24 w-40";

  const currentSettings = (): Omit<Profile, "id" | "name"> => ({
    subject, voice, tone, speed, accent, expressive, cta_on: ctaOn, cta_text: ctaText, cta_link: ctaLink,
    look, format, transition, effect, hook, seconds, outro: outro.id, outro_audio: outro.audio, outro_text: outro.text, pause,
  });

  const saveProfiles = async (list: Profile[]) => {
    const r = await fetch(`${API}/profiles`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ profiles: list }),
    });
    if (!r.ok) throw new Error(await readError(r));
    const saved: Profile[] = (await r.json()).profiles ?? [];
    setProfiles(saved);
    return saved;
  };

  const saveProfile = async (asNew = false) => {
    try {
      const current = profiles.find((p) => p.id === activeProfile);
      if (current && !asNew) {
        await saveProfiles(profiles.map((p) => (p.id === current.id ? { ...p, ...currentSettings() } : p)));
        toast.success(`Ajustes salvos no canal “${current.name}”`);
        return;
      }
      const name = window.prompt("Nome do canal (ex.: Deus É Fiel, Leis e Direitos):")?.trim();
      if (!name) return;
      const saved = await saveProfiles([...profiles, { id: "", name, ...currentSettings() }]);
      const created = saved.find((p) => p.name === name);
      if (created) setActiveProfile(created.id);
      toast.success(`Canal “${name}” salvo`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const applyProfile = (p: Profile) => {
    setActiveProfile(p.id);
    if (p.subject !== undefined) saveSubject(p.subject);
    if (p.voice) setVoice(p.voice);
    if (p.tone) setTone(p.tone);
    if (p.speed !== undefined) setSpeed(p.speed);
    if (p.accent !== undefined) setAccent(p.accent);
    if (p.expressive !== undefined) setExpressive(p.expressive);
    if (p.cta_on !== undefined) setCtaOn(p.cta_on);
    if (p.cta_text) setCtaText(p.cta_text);
    if (p.cta_link !== undefined) setCtaLink(p.cta_link);
    if (p.look !== undefined) setLook(p.look);
    if (p.format === "vertical" || p.format === "horizontal") setFormat(p.format);
    if (p.transition) setTransition(p.transition);
    if (p.effect) setEffect(p.effect);
    if (p.hook !== undefined) setHook(p.hook);
    if (p.seconds) setSeconds(p.seconds);
    if (p.outro !== undefined) {
      setOutro({
        id: p.outro.includes("/") ? p.outro : "",
        audio: p.outro_audio === "original" ? "original" : "narrator",
        text: p.outro_text || DEFAULT_OUTRO_TEXT,
      });
    }
    if (typeof p.pause === "number") setPause(p.pause);
    setIdeas([]);
    toast.success(`Canal “${p.name}” carregado`);
  };

  const dailyVideo = async () => {
    try {
      setDaily("Escolhendo o tema…");
      const ideasResponse = await fetch(`${API}/ideas`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ subject }),
      });
      if (!ideasResponse.ok) throw new Error(await readError(ideasResponse));
      const idea = ((await ideasResponse.json()).ideas ?? [])[0];
      if (!idea) throw new Error("A IA não sugeriu nenhum tema. Tente de novo.");
      setDaily("Escrevendo o roteiro…");
      const scriptResponse = await fetch(`${API}/script`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ theme: `${idea.theme}. Comece com: ${idea.hook}`, seconds }),
      });
      if (!scriptResponse.ok) throw new Error(await readError(scriptResponse));
      const dailyScript: string = (await scriptResponse.json()).script;
      setDaily("Enviando para gerar…");
      const r = await fetch(`${API}/videos`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: idea.theme, script: dailyScript, voice, speed, format, captions: true, images: [], picks: [],
          auto_background: true, hook: true, look, pronunciation, voice_settings: voiceSettings, transition, effect, pause, outro: outro.id, outro_audio: outro.audio, outro_text: outro.text,
          cta_text: ctaOn ? ctaText : "", cta_link: ctaOn ? ctaLink : "",
        }),
      });
      if (!r.ok) throw new Error(await readError(r));
      setScript(dailyScript);
      setTheme(idea.theme);
      setRefresh((n) => n + 1);
      toast.success(`Vídeo do dia em produção: “${idea.theme}”. Acompanhe abaixo ou na Biblioteca.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setDaily("");
    }
  };

  return (
    <main className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-8 md:py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Vídeo do zero</h1>
        <p className="text-sm text-muted-foreground">Narração com a sua voz, fundo com movimento e legenda animada.</p>
      </div>

      <section className="space-y-2 rounded-2xl border bg-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">Canal:</span>
          {profiles.map((p) => (
            <Button key={p.id} size="sm" variant={activeProfile === p.id ? "default" : "outline"} onClick={() => applyProfile(p)}>
              {p.name}
            </Button>
          ))}
          <Button size="sm" variant="ghost" onClick={() => void saveProfile()}>
            {activeProfile ? "Salvar ajustes neste canal" : "+ Salvar ajustes como canal"}
          </Button>
          {activeProfile && (
            <Button size="sm" variant="ghost" className="text-muted-foreground" onClick={() => void saveProfile(true)}>+ Novo canal</Button>
          )}
        </div>
        {activeProfile ? (
          <div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted/40 p-3">
            <div className="min-w-0 flex-1 text-sm">
              <p className="font-medium">⚡ Vídeo do dia</p>
              <p className="text-xs text-muted-foreground">
                Um clique: a IA escolhe um tema de “{subject || "assunto do canal"}”, escreve o roteiro e cria o vídeo com as configurações do canal, imagens livres automáticas e gancho na tela. Depois é só revisar na Biblioteca.
              </p>
            </div>
            <Button onClick={() => void dailyVideo()} disabled={daily !== "" || !subject.trim() || !voice}>
              {daily ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
              {daily || "Criar vídeo do dia"}
            </Button>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Configure tudo uma vez (assunto, voz, tom, visual, link) e salve como canal. Com os seus 3 canais salvos, troca-se tudo com um clique e aparece o botão “Vídeo do dia”.
          </p>
        )}
      </section>

      <nav className="grid grid-cols-5 gap-1.5" aria-label="Etapas">
        {STEPS.map((label, index) => (
          <button
            key={label}
            type="button"
            onClick={() => setStep(index)}
            aria-current={step === index ? "step" : undefined}
            className={cn(
              "flex items-center justify-center gap-1.5 rounded-xl border px-2 py-2 text-xs font-medium sm:text-sm",
              step === index ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted/60",
            )}
          >
            <span className={cn("flex size-5 items-center justify-center rounded-full text-[11px]", step === index ? "bg-primary-foreground/20" : "bg-muted")}>
              {done[index] && step !== index ? <Check className="size-3" /> : index + 1}
            </span>
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </nav>

      <section className="rounded-2xl border bg-card p-5">
        {step === 0 && (
          <div className="space-y-3">
            <div>
              <h2 className="font-semibold">Roteiro</h2>
              <p className="text-sm text-muted-foreground">Cole o texto que o narrador vai falar, ou peça para a IA escrever a partir de um tema.</p>
            </div>
            <Advanced title="Sem ideia? Receber sugestões de temas">
              <form
                className="flex flex-col gap-2 sm:flex-row"
                onSubmit={(e) => {
                  e.preventDefault();
                  void loadIdeas();
                }}
              >
                <Input value={subject} onChange={(e) => saveSubject(e.target.value)} placeholder="Assunto do canal (ex.: fé e oração, história do Brasil)" />
                <Button type="submit" variant="secondary" disabled={loadingIdeas || !subject.trim()}>
                  {loadingIdeas ? <Loader2 className="size-4 animate-spin" /> : <Lightbulb className="size-4" />}
                  {ideas.length ? "Mais sugestões" : "Sugerir temas"}
                </Button>
              </form>
              {ideas.length > 0 && (
                <ul className="grid gap-2 sm:grid-cols-2">
                  {ideas.map((idea) => (
                    <li key={idea.theme}>
                      <button
                        type="button"
                        onClick={() => {
                          setTheme(idea.theme);
                          toast.success("Tema escolhido. Clique em “Escrever com IA”.");
                        }}
                        className={cn("w-full rounded-lg border p-2 text-left text-sm hover:bg-muted/50", theme === idea.theme && "border-primary ring-2 ring-primary/30")}
                      >
                        <span className="block font-medium">{idea.theme}</span>
                        <span className="mt-0.5 block text-xs text-muted-foreground">“{idea.hook}”</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Advanced>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input placeholder="Tema (ex.: Isaías 40:31, a águia que renova as forças)" value={theme} onChange={(e) => setTheme(e.target.value)} />
              <select className="h-9 rounded-md border bg-background px-2 text-sm" value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} aria-label="Duração">
                {[30, 45, 60, 90, 180].map((s) => (
                  <option key={s} value={s}>{s < 60 ? `${s} s` : `${s / 60} min`}</option>
                ))}
              </select>
              <Button variant="secondary" onClick={writeScript} disabled={writing || !theme.trim()}>
                {writing ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                Escrever com IA
              </Button>
            </div>
            <Textarea rows={10} value={script} onChange={(e) => setScript(e.target.value)} placeholder="Cole aqui a passagem ou o roteiro que o narrador vai falar." />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">{words ? `${words} palavras · ${paragraphs} parágrafo(s) · cerca de ${narrationSeconds} s de narração com a voz e as pausas escolhidas` : ""}</p>
              <Button size="sm" variant="outline" onClick={fixScript} disabled={fixing || !script.trim()}>
                {fixing ? <Loader2 className="size-4 animate-spin" /> : <SpellCheck className="size-4" />}
                Corrigir ortografia
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">O texto deste passo é o que aparece na legenda. Ajustes de como falar ficam no passo Pronúncia e não aparecem no vídeo.</p>
            <FactCheckPanel script={script} onScriptChange={setScript} onSources={setSources} />
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <div>
              <h2 className="font-semibold">Voz do narrador</h2>
              <p className="text-sm text-muted-foreground">Toque em ▶ para ouvir. As suas vozes clonadas ficam em “Minhas vozes”.</p>
            </div>
            <div className="space-y-1.5">
              <Label>Tom da narração</Label>
              <div className="flex flex-wrap gap-1.5">
                {TONES.map((t) => (
                  <Button key={t.id} size="sm" variant={tone === t.id ? "default" : "outline"} onClick={() => applyTone(t.id)}>
                    {t.label}
                  </Button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{TONES.find((t) => t.id === tone)?.hint}</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {groups.map((g) => (
                <Button key={g} size="sm" variant={filter === g ? "default" : "outline"} onClick={() => setFilter(g)}>{g}</Button>
              ))}
              <span className="ml-auto">
                <CreateVoiceDialog onCreated={(id) => { setFilter("Minhas vozes"); void loadVoices(id); }} />
              </span>
            </div>
            <div className="grid max-h-72 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
              {voices.length === 0 && <Loader2 className="size-5 animate-spin text-muted-foreground" />}
              {shown.map((v) => (
                <div
                  key={v.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setVoice(v.id)}
                  onKeyDown={(e) => e.key === "Enter" && setVoice(v.id)}
                  className={cn("flex items-center gap-2 rounded-xl border p-2.5 text-left", voice === v.id ? "border-primary ring-2 ring-primary/30" : "hover:bg-muted/50")}
                >
                  <span className="text-lg">{v.gender === "Female" ? "👩" : "👨"}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{v.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">{v.group}</span>
                  </span>
                  <Button size="icon" variant="ghost" className="size-8" aria-label={`Ouvir ${v.name}`} onClick={(e) => { e.stopPropagation(); void preview(v.id); }}>
                    {playing === v.id ? <Square className="size-3.5" /> : <Play className="size-3.5" />}
                  </Button>
                  {v.group === "Minhas vozes" && (
                    <Button size="icon" variant="ghost" className="size-8 text-muted-foreground hover:text-destructive" aria-label={`Apagar ${v.name}`} onClick={(e) => { e.stopPropagation(); void deleteVoice(v); }}>
                      <Trash2 className="size-3.5" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
            <Advanced title="Ajustes da voz e teste">
              <div className="space-y-1.5">
                <Label>Pausa entre frases</Label>
                <div className="flex flex-wrap gap-1.5">
                  {[[0.25, "Curta"], [0.6, "Média"], [1.0, "Longa (oração, reflexão)"]].map(([value, label]) => (
                    <Button key={String(value)} size="sm" variant={pause === value ? "default" : "outline"} onClick={() => setPause(Number(value))}>{label}</Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">Média e Longa geram cada frase separada e deixam um silêncio depois. Use “...” no texto para pausar no meio da frase.</p>
              </div>
              <div className="space-y-1.5">
                <Label>Velocidade: {speed === 0 ? "natural" : `${speed > 0 ? "+" : ""}${speed}%`}</Label>
                <Slider aria-label="Velocidade" min={-30} max={30} step={5} value={[speed]} onValueChange={([v]) => setSpeed(v)} />
              </div>
              {voice.startsWith("vs:") && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>Sotaque: {accent <= 20 ? "bem neutro" : accent <= 40 ? "neutro" : accent <= 60 ? "padrão" : "forte"} ({accent})</Label>
                    <Slider aria-label="Sotaque" min={0} max={100} step={5} value={[accent]} onValueChange={([v]) => setAccent(v)} />
                    <p className="text-xs text-muted-foreground">Mais baixo deixa o “r” e o sotaque mais neutros.</p>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Expressividade: {expressive}</Label>
                    <Slider aria-label="Expressividade" min={25} max={150} step={5} value={[expressive]} onValueChange={([v]) => setExpressive(v)} />
                    <p className="text-xs text-muted-foreground">50 é natural; acima fica mais dramático.</p>
                  </div>
                </div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="test-phrase">Testar uma frase</Label>
                <div className="flex gap-2">
                  <Input id="test-phrase" value={testPhrase} onChange={(e) => setTestPhrase(e.target.value)} />
                  <Button size="sm" variant="secondary" disabled={!voice || !testPhrase.trim()} onClick={() => void preview(voice, testPhrase, "phrase")}>
                    {playing === "phrase" ? <Square className="size-3.5" /> : <Play className="size-3.5" />}
                    Ouvir
                  </Button>
                </div>
              </div>
            </Advanced>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div>
              <h2 className="font-semibold">Pronúncia</h2>
              <p className="text-sm text-muted-foreground">Corrija nomes e siglas antes de gerar, para não perder tempo refazendo o vídeo.</p>
            </div>
            <PronunciationPanel script={script} onChange={setPronunciation} onListen={(text) => voice && void preview(voice, text, `say:${text}`)} />
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div>
              <h2 className="font-semibold">Fundo</h2>
              <p className="text-sm text-muted-foreground">Escolha as imagens de cada trecho, ou envie as suas fotos e vídeos (até 12 no total).</p>
            </div>
            <BackgroundPicker script={script} format={format} onChange={setPicks} />
            <p className="text-sm font-medium">Suas fotos e vídeos (opcional)</p>
            <div className="flex flex-wrap gap-3">
              {images.map((src, i) => (
                <div key={i} className="space-y-1">
                  <div className="group relative">
                    {src.startsWith("data:video/") ? (
                      <video
                        src={`${src}#t=${mediaMeta[i]?.start ?? 0}`}
                        muted
                        loop
                        autoPlay
                        playsInline
                        className={cn("rounded-lg border object-cover", thumb)}
                      />
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={src} alt={`Fundo ${i + 1}`} className={cn("rounded-lg border object-cover", thumb)} />
                    )}
                    <span className="absolute left-1 top-1 rounded bg-black/60 px-1.5 text-[11px] text-white">{i + 1}</span>
                    <button
                      type="button"
                      aria-label="Remover"
                      onClick={() => removeMedia(i)}
                      className="absolute right-1 top-1 rounded-md bg-black/60 p-1 text-white opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between">
                    <Button size="icon" variant="ghost" className="size-6" disabled={i === 0} onClick={() => moveMedia(i, -1)} aria-label="Mover para antes">
                      <ArrowLeft className="size-3" />
                    </Button>
                    <span className="text-[11px] text-muted-foreground">ordem</span>
                    <Button size="icon" variant="ghost" className="size-6" disabled={i === images.length - 1} onClick={() => moveMedia(i, 1)} aria-label="Mover para depois">
                      <ArrowRight className="size-3" />
                    </Button>
                  </div>
                  {src.startsWith("data:video/") && mediaMeta[i] && (
                    <TrimButton
                      src={src}
                      index={i}
                      start={mediaMeta[i].start}
                      end={mediaMeta[i].end}
                      duration={mediaMeta[i].duration}
                      onChange={(start, end) => setTrim(i, start, end)}
                    />
                  )}
                </div>
              ))}
              <label className={cn("flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-xs text-muted-foreground hover:bg-muted/50", thumb)}>
                <ImagePlus className="size-5" />
                Adicionar
                <input type="file" accept="image/*,video/*" multiple hidden onChange={(e) => void addImages(e.target.files)} />
              </label>
            </div>
            {paragraphMismatch && (
              <p className="rounded-lg bg-amber-500/15 p-2 text-xs text-amber-800 dark:text-amber-200">
                ⚠️ Seu roteiro tem <b>{paragraphs} parágrafos</b> e há <b>{sceneCount} vídeos/imagens</b>. Para cada parágrafo cair na
                sua cena, deixe os dois números iguais (junte/separe parágrafos no passo Roteiro ou adicione/remova cenas aqui).
              {" "}
                <Button size="sm" variant="outline" className="ml-1 h-7" onClick={fitParagraphsToScenes}>Ajustar automaticamente</Button>
              </p>
            )}
            {images.length > 0 && (
              <div className="flex flex-wrap items-center gap-3 rounded-lg bg-muted/40 p-2 text-xs">
                <SequencePreview
                  items={images.map((src, i) => ({
                    src,
                    isVideo: src.startsWith("data:video/"),
                    start: mediaMeta[i]?.start ?? 0,
                    end: mediaMeta[i]?.end ?? 0,
                    duration: mediaMeta[i]?.duration ?? 0,
                  }))}
                />
                {videoSeconds > 0 && (
                  <span>
                    Seus vídeos somam <b>{videoSeconds.toFixed(1).replace(".", ",")} s</b> · narração ≈ <b>{narrationSeconds} s</b>.{" "}
                    {Math.abs(videoSeconds - narrationSeconds) > 4
                      ? "Tente deixar os dois parecidos (corte as cenas ou ajuste o texto) para nenhum vídeo repetir ou ficar corrido."
                      : "Ótimo, os tempos batem."}
                  </span>
                )}
              </div>
            )}
            <Advanced title="Movimento e transição">
              <div className="space-y-1.5">
                <Label>Movimento das fotos</Label>
                <div className="flex flex-wrap gap-1.5">
                  {[["zoom", "Zoom suave"], ["pan", "Deslizar"], ["static", "Parado"]].map(([id, label]) => (
                    <Button key={id} size="sm" variant={effect === id ? "default" : "outline"} onClick={() => setEffect(id)}>{label}</Button>
                  ))}
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Transição entre fotos/vídeos</Label>
                <select className="h-9 w-full rounded-md border bg-background px-2 text-sm" value={transition} onChange={(e) => setTransition(e.target.value)}>
                  {TRANSITIONS.map(([id, label]) => (
                    <option key={id} value={id}>{label}</option>
                  ))}
                </select>
              </div>
            </Advanced>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <div>
              <h2 className="font-semibold">Finalizar</h2>
              <p className="text-sm text-muted-foreground">Confira o resumo e crie o vídeo.</p>
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-xl bg-muted/40 p-3 text-sm sm:grid-cols-4">
              <dt className="text-muted-foreground">Roteiro</dt><dd>{words ? `${words} palavras (~${narrationSeconds} s)` : "—"}</dd>
              <dt className="text-muted-foreground">Voz</dt><dd className="truncate">{selectedVoice?.name ?? "—"}</dd>
              <dt className="text-muted-foreground">Pronúncias</dt><dd>{pronunciation.length}</dd>
              <dt className="text-muted-foreground">Fundo</dt><dd>{backgrounds} imagem(ns)</dd>
            </dl>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant={format === "vertical" ? "default" : "outline"} onClick={() => setFormat("vertical")}>Short 9:16</Button>
              <Button size="sm" variant={format === "horizontal" ? "default" : "outline"} onClick={() => setFormat("horizontal")}>YouTube 16:9</Button>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={captions} onCheckedChange={setCaptions} /> Legenda animada (palavra atual em amarelo)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={hook} onCheckedChange={setHook} /> Gancho grande na tela nos 2 primeiros segundos
            </label>
            {hook && (
              <Input value={hookText} onChange={(e) => setHookText(e.target.value)} placeholder="Texto do gancho (vazio = a IA escreve, até 6 palavras)" />
            )}
            <div className="space-y-1.5">
              <Label>Visual do vídeo</Label>
              <div className="flex flex-wrap gap-1.5">
                {LOOKS.map(([id, label]) => (
                  <Button key={id} size="sm" variant={look === id ? "default" : "outline"} onClick={() => setLook(id)}>{label}</Button>
                ))}
              </div>
            </div>
            <div className="space-y-2 rounded-xl border p-3">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Switch checked={ctaOn} onCheckedChange={setCtaOn} /> Chamada no fim do vídeo (seguir o canal, link…)
              </label>
              {ctaOn && (
                <div className="space-y-2">
                  <div className="flex flex-wrap gap-1.5">
                    {["Curte e compartilha com quem precisa ouvir isso hoje!", "Curte e segue o canal para mais vídeos assim!", "Comente AMÉM se você recebe essa palavra.", "Compartilha com alguém que está passando por uma luta.", "Segue o canal: todo dia uma palavra de Deus para você.", "Acesse o link na descrição."].map((preset) => (
                      <Button key={preset} size="sm" variant={ctaText === preset ? "default" : "outline"} onClick={() => setCtaText(preset)}>
                        {preset}
                      </Button>
                    ))}
                  </div>
                  <Input value={ctaText} onChange={(e) => setCtaText(e.target.value)} placeholder="Frase que o narrador fala no final" />
                  <Input value={ctaLink} onChange={(e) => setCtaLink(e.target.value)} placeholder="Link (opcional): vai para a descrição sugerida" />
                  <p className="text-xs text-muted-foreground">O narrador fala a frase no final e ela aparece numa faixa amarela nos últimos segundos.</p>
                </div>
              )}
            </div>
            <OutroPicker value={outro} onChange={setOutro} channel={profiles.find((p) => p.id === activeProfile)?.name ?? ""} />
            <Advanced title={music ? `🎵 Música: ${music.title}` : "🎵 Música de fundo (sem direitos autorais)"}>
              <MusicPicker script={script} value={music} onChange={setMusic} volume={musicVolume} onVolume={setMusicVolume} />
            </Advanced>
            {paragraphMismatch && (
              <p className="rounded-lg bg-amber-500/15 p-2 text-xs text-amber-800 dark:text-amber-200">
                ⚠️ {paragraphs} parágrafos para {sceneCount} cenas: a fala e as imagens podem ficar desencontradas.{" "}
                <Button size="sm" variant="outline" className="ml-1 h-7" onClick={fitParagraphsToScenes}>Ajustar automaticamente</Button>
              </p>
            )}
            {narrationSeconds > 60 && (
              <p className="rounded-lg bg-amber-500/15 p-2 text-xs text-amber-800 dark:text-amber-200">
                ⚠️ A narração deve passar de 1 minuto (~{narrationSeconds} s). Para Short, encurte o texto, aumente a velocidade ou use pausa Média.
              </p>
            )}
            <Button size="lg" onClick={create} disabled={creating || missing.length > 0}>
              {creating ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
              Criar vídeo
            </Button>
            {missing.length > 0 && <p className="text-xs text-muted-foreground">Falta: {missing.join(", ")}.</p>}
          </div>
        )}

        <div className="mt-6 flex justify-between border-t pt-4">
          <Button variant="ghost" onClick={() => setStep((s) => s - 1)} disabled={step === 0}>
            <ArrowLeft className="size-4" /> Voltar
          </Button>
          {step < STEPS.length - 1 && (
            <Button onClick={() => setStep((s) => s + 1)}>
              Próximo: {STEPS[step + 1]} <ArrowRight className="size-4" />
            </Button>
          )}
        </div>
      </section>

      <StudioVideos refreshSignal={refresh} />
    </main>
  );
}

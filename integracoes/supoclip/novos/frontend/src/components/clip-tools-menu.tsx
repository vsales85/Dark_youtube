"use client";

import { useState } from "react";
import { EyeOff, ImageIcon, Mic, Palette, Wrench } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ClipColorDialog } from "@/components/clip-color";
import { ClipCoverButton } from "@/components/clip-cover";
import { ClipNarrationButton } from "@/components/clip-narration";
import { ClipThumbnailsButton } from "@/components/clip-thumbnails";

type Tool = "thumbs" | "cover" | "narration" | "color" | null;

/** One "Ferramentas" button for the clip extras, so the clip view stays clean. */
export function ClipToolsMenu({ taskId, clipId, onChanged }: { taskId: string; clipId: string; onChanged: () => void }) {
  const [tool, setTool] = useState<Tool>(null);
  const close = (open: boolean) => !open && setTool(null);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <Wrench className="size-4" />
            Ferramentas
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64">
          <DropdownMenuItem onSelect={() => setTool("thumbs")}>
            <ImageIcon className="size-4" />
            <span><b className="block font-medium">Thumbnails</b><span className="text-xs text-muted-foreground">Capa do Shorts e thumb 16:9</span></span>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setTool("narration")}>
            <Mic className="size-4" />
            <span><b className="block font-medium">Narração</b><span className="text-xs text-muted-foreground">Sua voz por cima do clipe</span></span>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setTool("cover")}>
            <EyeOff className="size-4" />
            <span><b className="block font-medium">Cobrir legenda</b><span className="text-xs text-muted-foreground">Esconde a legenda original</span></span>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setTool("color")}>
            <Palette className="size-4" />
            <span><b className="block font-medium">Cor do vídeo</b><span className="text-xs text-muted-foreground">Filtros: cinema, vibrante, P&B…</span></span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ClipThumbnailsButton taskId={taskId} clipId={clipId} open={tool === "thumbs"} onOpenChange={close} />
      <ClipNarrationButton taskId={taskId} clipId={clipId} onDone={onChanged} open={tool === "narration"} onOpenChange={close} />
      <ClipCoverButton taskId={taskId} clipId={clipId} onDone={onChanged} open={tool === "cover"} onOpenChange={close} />
      <ClipColorDialog taskId={taskId} clipId={clipId} onDone={onChanged} open={tool === "color"} onOpenChange={close} />
    </>
  );
}

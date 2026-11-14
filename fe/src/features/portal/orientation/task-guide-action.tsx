"use client";

import { Signpost } from "lucide-react";
import { usePathname } from "next/navigation";
import { useRef } from "react";
import { PageAction } from "@/components/ui/page-action";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useOptionalPortalOrientation } from "./portal-orientation";
import { guideOnPage, type TaskGuideId } from "./task-guide-definitions";

export function TaskGuideAction() {
  const context = useOptionalPortalOrientation();
  const pathname = usePathname();
  const trigger = useRef<HTMLButtonElement>(null);
  const selection = useRef<TaskGuideId | null>(null);
  if (!context) return null;
  const guides = context.guides.filter(guide => guideOnPage(guide, pathname));
  if (!guides.length) return null;
  if (guides.length === 1) return <PageAction compact variant="secondary" icon={Signpost} label="Guide" labelDetail={`: ${guides[0].title}`}
    data-guide-launch={guides[0].id} onClick={event => context.launchTask(guides[0].id, event.currentTarget)} />;
  return <DropdownMenu>
    <DropdownMenuTrigger asChild><PageAction compact ref={trigger} variant="secondary" icon={Signpost} label="Guide" labelDetail=": choose a task guide" data-guide-launch={guides.map(guide => guide.id).join(" ")} /></DropdownMenuTrigger>
    <DropdownMenuContent className="max-h-[70dvh] max-w-[calc(100vw-2rem)] overflow-y-auto" onCloseAutoFocus={event => {
      if (!selection.current) return;
      event.preventDefault();
      const id = selection.current;
      selection.current = null;
      // The chooser closes before launching; the guide never competes with an open menu.
      requestAnimationFrame(() => { if (trigger.current) { trigger.current.focus(); context.launchTask(id, trigger.current); } });
    }}>
      {guides.map(guide => <DropdownMenuItem key={guide.id} className="whitespace-normal" onSelect={() => { selection.current = guide.id; }}>
        {context.preferences[guide.id] === "completed" ? "Replay" : "Start"}: {guide.title}
      </DropdownMenuItem>)}
    </DropdownMenuContent>
  </DropdownMenu>;
}

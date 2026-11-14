"use client";

import { ArrowLeft, Download, Info, MoreHorizontal, Pencil, RefreshCw, Search, Settings, Signpost } from "lucide-react";
import { forwardRef } from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

// Deliberately limited to conventional, low-risk actions. Publication, deletion, issuance,
// recording, consent and account access changes keep visible text and their existing review.
// `info` opens read-only details; `guide` starts an optional task guide (Signpost, never the
// Compass brand mark, which reads as the logo or Home).
export const actionIcons = { back: ArrowLeft, download: Download, edit: Pencil, guide: Signpost, info: Info, more: MoreHorizontal, refresh: RefreshCw, search: Search, settings: Settings };
type CompactAction = keyof typeof actionIcons;

export const IconAction = forwardRef<HTMLButtonElement, Omit<ButtonProps, "children" | "aria-label"> & { action: CompactAction; label: string; touchLabel?: string }>(
  ({ action, label, touchLabel, className, variant = "secondary", ...props }, ref) => {
    const Icon = actionIcons[action];
    return (
      <Tooltip label={label}>
        <Button {...props} ref={ref} variant={variant} aria-label={label} className={cn("min-h-11 min-w-11 px-3", className)}>
          <Icon aria-hidden="true" size={18} />
          {/* Touch users see the name without needing a hover or an extra tap. A shorter touchLabel
              suits a row that already shows the object ("About" beside the Counselor's name). */}
          <span aria-hidden="true" className="hidden [@media(pointer:coarse)]:inline">{touchLabel ?? label}</span>
        </Button>
      </Tooltip>
    );
  },
);
IconAction.displayName = "IconAction";

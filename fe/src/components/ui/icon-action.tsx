"use client";

import { ArrowLeft, Download, MoreHorizontal, Pencil, RefreshCw, Search, Settings } from "lucide-react";
import { forwardRef } from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

// Deliberately limited to conventional, low-risk actions. Publication, deletion, issuance,
// recording, consent and account access changes keep visible text and their existing review.
export const actionIcons = { back: ArrowLeft, download: Download, edit: Pencil, more: MoreHorizontal, refresh: RefreshCw, search: Search, settings: Settings };
type CompactAction = keyof typeof actionIcons;

export const IconAction = forwardRef<HTMLButtonElement, Omit<ButtonProps, "children" | "aria-label"> & { action: CompactAction; label: string }>(
  ({ action, label, className, variant = "secondary", ...props }, ref) => {
    const Icon = actionIcons[action];
    return (
      <Tooltip label={label}>
        <Button {...props} ref={ref} variant={variant} aria-label={label} className={cn("min-h-11 min-w-11 px-3", className)}>
          <Icon aria-hidden="true" size={18} />
          {/* Touch users see the name without needing a hover or an extra tap. */}
          <span aria-hidden="true" className="hidden [@media(pointer:coarse)]:inline">{label}</span>
        </Button>
      </Tooltip>
    );
  },
);
IconAction.displayName = "IconAction";

"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactElement } from "react";

// Short, supplementary control names only. No links, instructions or critical information.
// Radix keeps content hoverable, opens on focus/hover, handles collisions and dismisses on Escape.
export function Tooltip({ label, children }: { label: string; children: ReactElement }) {
  return (
    <TooltipPrimitive.Provider delayDuration={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content sideOffset={6} collisionPadding={8} className="z-[60] max-w-xs rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink shadow-float">
            {label}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

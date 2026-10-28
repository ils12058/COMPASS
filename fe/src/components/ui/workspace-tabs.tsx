import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

// Links between the sections of one workspace, drawn as tabs on the canvas. The current tab is
// marked in maroon and with aria-current="page". The feature renders the links itself, so a
// workspace that guards unsaved changes keeps its own link component.
export function WorkspaceTabs({
  label,
  className,
  children,
}: {
  // Names the landmark: "<Workspace> navigation".
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <nav
      aria-label={label}
      className={cn("mb-5 flex w-fit max-w-full flex-wrap gap-1 rounded-lg bg-surface-muted p-1", className)}
    >
      {children}
    </nav>
  );
}

export function workspaceTabClass(current: boolean) {
  return cn(
    "inline-flex min-h-11 items-center rounded-md border px-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
    current
      ? "border-border bg-surface-raised text-brand"
      : "border-transparent text-muted hover:bg-surface-subtle hover:text-ink",
  );
}

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
      className={cn("mb-5 flex flex-wrap gap-x-6 gap-y-1 border-b border-brand-line", className)}
    >
      {children}
    </nav>
  );
}

export function workspaceTabClass(current: boolean) {
  return cn(
    "-mb-px inline-flex min-h-11 items-center border-b-2 px-0.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
    current
      ? "border-brand text-brand"
      : "border-transparent text-muted hover:border-border-strong hover:text-ink",
  );
}

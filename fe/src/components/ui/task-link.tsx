import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils/cn";

// One navigational action per task; retry or other buttons remain outside this link.
export function TaskLink({ href, actionLabel, title, subject, detail, timing, priority, className }: {
  href: string; actionLabel: string; title: string; subject?: string; detail: string;
  timing?: string; priority?: ReactNode; className?: string;
}) {
  const contextId = useId();
  return <Link href={href} aria-label={actionLabel} aria-describedby={contextId}
    className={cn("group flex min-h-11 min-w-0 items-center gap-2 px-3 py-3 text-sm transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:gap-4 sm:px-5", className)}>
    <div className="min-w-0 flex-1 [overflow-wrap:anywhere]">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="font-semibold leading-6 text-ink group-hover:text-brand">{title}</h3>
        {priority ? <span className="text-xs font-semibold text-warning">{priority}</span> : null}
      </div>
      <div id={contextId}>
        {subject ? <p className="mt-0.5 text-ink">{subject}</p> : null}
        <p className="mt-0.5 leading-6 text-muted">{detail}</p>
        {timing ? <p className="mt-0.5 leading-6 text-muted">{timing}</p> : null}
      </div>
    </div>
    <ChevronRight aria-hidden="true" className="h-4 w-4 shrink-0 text-brand" />
  </Link>;
}

import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

type NoticeTone = "neutral" | "info" | "success" | "warning" | "danger";

const frame: Record<NoticeTone, string> = {
  neutral: "border-brand-line",
  info: "border-info/35",
  success: "border-success/35",
  warning: "border-warning/40",
  danger: "border-danger/35",
};

const text: Record<NoticeTone, string> = {
  neutral: "text-muted",
  info: "text-ink",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};

// A message that stands on the canvas by itself: a page-level failure, a refresh problem, a
// lifecycle note, an unavailable workspace. It is framed evenly like a panel, in the tone's color,
// so it reads as part of the page rather than text between two rules. Inside a panel, use
// PanelMessage instead. Pass role="alert" or role="status" when the message must be announced.
export function Notice({
  tone = "neutral",
  title,
  action,
  className,
  children,
  ...props
}: Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  tone?: NoticeTone;
  // Rendered as given, so a page-level failure can pass its own heading element.
  title?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div
      className={cn("rounded-sm border bg-surface-raised px-4 py-3.5 sm:px-5", frame[tone], className)}
      {...props}
    >
      {title ? <div className="font-semibold text-ink">{title}</div> : null}
      {children ? (
        <div className={cn("text-sm leading-6", title && "mt-1", text[tone])}>{children}</div>
      ) : null}
      {action ? <div className="mt-3 flex flex-wrap items-center gap-3">{action}</div> : null}
    </div>
  );
}

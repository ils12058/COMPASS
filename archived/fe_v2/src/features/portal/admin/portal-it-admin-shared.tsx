import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { DiagnosticStatus } from "@/lib/api/generated/model";

export function formatAdminLabel(value: string | null | undefined) {
  const normalized = value?.trim().replace(/[_-]+/g, " ");

  if (!normalized) {
    return "Not available";
  }

  return normalized.replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatAdminDate(value: string | null | undefined) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function getDiagnosticTone(status: DiagnosticStatus) {
  switch (status) {
    case "HEALTHY":
      return "positive" as const;
    case "DEGRADED":
      return "warning" as const;
    case "UNAVAILABLE":
      return "negative" as const;
    default:
      return "neutral" as const;
  }
}

const TONE_CLASSES = {
  positive:
    "bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]",
  warning:
    "bg-[var(--compass-brand-gold)]/20 text-[var(--compass-brand-maroon)]",
  negative: "bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]",
  neutral: "bg-muted text-muted-foreground",
} as const;

export function AdminStatusBadge({
  children,
  tone,
}: {
  children: ReactNode;
  tone: keyof typeof TONE_CLASSES;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}

export function AdminOverviewCard({
  children,
  className = "",
  description,
  icon: Icon,
  title,
}: {
  children: ReactNode;
  className?: string;
  description?: string;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <section
      className={`rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-6 ${className}`}
    >
      <header className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
          <Icon aria-hidden="true" className="size-5" />
        </span>
        <div className="min-w-0">
          <h2 className="font-heading text-xl font-bold tracking-tight">{title}</h2>
          {description ? (
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
      </header>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function AdminCardLoading({ lines = 3 }: { lines?: number }) {
  const heights = ["h-8", "h-4", "h-4", "h-4", "h-4"];

  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          className={`${heights[index] ?? "h-4"} animate-pulse rounded-lg bg-muted ${
            index === 0 ? "w-2/5" : index === lines - 1 ? "w-4/5" : "w-full"
          }`}
        />
      ))}
    </div>
  );
}

export function AdminCardError({
  onRetry,
}: {
  onRetry: () => void;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-muted)] p-4">
      <p role="alert" className="text-sm leading-6 text-muted-foreground">
        This section could not be loaded right now.
      </p>
      <Button
        className="mt-3"
        size="sm"
        type="button"
        variant="outline"
        onClick={onRetry}
      >
        Try again
      </Button>
    </div>
  );
}

export function AdminMetric({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-muted)] p-4">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 font-heading text-2xl font-bold text-foreground">{value}</p>
    </div>
  );
}

"use client";

import Image from "next/image";

import { Button } from "@/components/ui/button";
import type { ServiceStatusView } from "@/lib/system/service-status";

type ActiveMaintenanceStatus = Extract<
  ServiceStatusView,
  { kind: "maintenance_active" }
>;

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatWindow(startsAt: string, endsAt: string): string {
  return `${formatDateTime(startsAt)} – ${formatDateTime(endsAt)}`;
}

export function MaintenanceScreen({
  status,
  onRetry,
  checking,
}: {
  status: ActiveMaintenanceStatus;
  onRetry: () => void;
  checking: boolean;
}) {
  const scheduled = status.startsAt !== null && status.endsAt !== null;

  return (
    <main className="flex min-h-screen items-center px-5 py-12 sm:px-8">
      <section
        aria-labelledby="maintenance-heading"
        className="mx-auto w-full max-w-2xl rounded-2xl border bg-card p-7 text-center shadow-md sm:p-10"
      >
        <Image
          src="/brand/compass-mark.svg"
          alt=""
          width={58}
          height={58}
          unoptimized
          className="mx-auto"
          aria-hidden="true"
        />
        <p className="mt-5 text-sm font-semibold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
          COMPASS
        </p>
        <h1
          id="maintenance-heading"
          className="mt-2 font-heading text-4xl font-bold tracking-tight"
        >
          We’ll be back soon.
        </h1>
        <p className="mx-auto mt-4 max-w-xl leading-7 text-muted-foreground">
          {status.message}
        </p>

        {scheduled ? (
          <p className="mt-5 rounded-xl bg-muted p-4 text-sm">
            <span className="font-semibold">Scheduled maintenance: </span>
            {formatWindow(status.startsAt!, status.endsAt!)}
          </p>
        ) : status.endsAt ? (
          <p className="mt-5 rounded-xl bg-muted p-4 text-sm">
            <span className="font-semibold">Expected end: </span>
            {formatDateTime(status.endsAt)}
          </p>
        ) : null}

        <Button className="mt-6" onClick={onRetry} disabled={checking}>
          {checking ? "Checking…" : "Check again"}
        </Button>
      </section>
    </main>
  );
}

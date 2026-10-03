"use client";

import { PublicPlatformStatus } from "@/lib/api/generated/model";
import { usePlatformPublicStatus } from "@/lib/api/generated/platform-operations/platform-operations";
import { PlatformTimestamp } from "@/features/platform/platform-presentation";

export function PublicMaintenanceNotice() {
  const query = usePlatformPublicStatus({
    query: {
      refetchInterval: 60_000,
      retry: false,
      staleTime: 60_000,
    },
  });
  const status = query.data?.data;

  if (!status || status.status === PublicPlatformStatus.operational) {
    return null;
  }

  const scheduled = status.status === PublicPlatformStatus.maintenance_scheduled;

  return (
    <section
      role="status"
      aria-live="polite"
      aria-labelledby="public-maintenance-heading"
      className={`mb-6 rounded-sm border px-4 py-3 sm:px-5 ${
        scheduled
          ? "border-info/35 bg-surface-raised"
          : "border-warning/40 bg-surface-raised"
      }`}
    >
      <h2
        id="public-maintenance-heading"
        className="text-sm font-semibold text-ink"
      >
        {scheduled ? "Planned maintenance" : "COMPASS is under maintenance"}
      </h2>
      {status.message ? (
        <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-ink">
          {status.message}
        </p>
      ) : null}
      {scheduled ? (
        <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted">
          {status.starts_at ? (
            <div className="flex flex-wrap gap-x-1">
              <dt>Starts:</dt>
              <dd><PlatformTimestamp value={status.starts_at} /></dd>
            </div>
          ) : null}
          {status.ends_at ? (
            <div className="flex flex-wrap gap-x-1">
              <dt>Ends:</dt>
              <dd><PlatformTimestamp value={status.ends_at} /></dd>
            </div>
          ) : null}
        </dl>
      ) : status.ends_at ? (
        <p className="mt-2 text-xs text-muted">
          Expected end: <PlatformTimestamp value={status.ends_at} />
        </p>
      ) : null}
    </section>
  );
}

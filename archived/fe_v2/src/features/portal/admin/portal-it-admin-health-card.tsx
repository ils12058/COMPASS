"use client";

import { Activity } from "lucide-react";

import {
  usePlatformOperationsHealth,
} from "@/lib/api/generated/platform-operations/platform-operations";
import {
  AdminCardError,
  AdminCardLoading,
  AdminOverviewCard,
  AdminStatusBadge,
  formatAdminLabel,
  getDiagnosticTone,
} from "@/features/portal/admin/portal-it-admin-shared";

export function PortalItAdminHealthCard() {
  const healthQuery = usePlatformOperationsHealth({
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const health = healthQuery.data?.data;

  return (
    <AdminOverviewCard
      description="A quick view of the services COMPASS depends on."
      icon={Activity}
      title="Platform health"
    >
      {healthQuery.isPending ? <AdminCardLoading lines={4} /> : null}
      {healthQuery.isError ? (
        <AdminCardError onRetry={() => void healthQuery.refetch()} />
      ) : null}
      {health ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-2xl font-bold">{formatAdminLabel(health.status)}</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {health.summary}
              </p>
            </div>
            <AdminStatusBadge tone={getDiagnosticTone(health.status)}>
              {formatAdminLabel(health.status)}
            </AdminStatusBadge>
          </div>

          {health.checks.length ? (
            <ul className="divide-y rounded-2xl border border-[var(--compass-border)]">
              {health.checks.map((check) => (
                <li
                  key={check.code}
                  className="flex items-center justify-between gap-4 px-4 py-3"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">
                      {check.label}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                      {check.summary}
                    </span>
                  </span>
                  <AdminStatusBadge tone={getDiagnosticTone(check.status)}>
                    {formatAdminLabel(check.status)}
                  </AdminStatusBadge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              No dependency checks were returned.
            </p>
          )}
        </div>
      ) : null}
    </AdminOverviewCard>
  );
}

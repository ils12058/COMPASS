"use client";

import { Wrench } from "lucide-react";

import {
  usePlatformOperationsGetMaintenance,
} from "@/lib/api/generated/platform-operations/platform-operations";
import {
  AdminCardError,
  AdminCardLoading,
  AdminOverviewCard,
  AdminStatusBadge,
  formatAdminDate,
  formatAdminLabel,
} from "@/features/portal/admin/portal-it-admin-shared";

export function PortalItAdminMaintenanceCard() {
  const maintenanceQuery = usePlatformOperationsGetMaintenance({
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const maintenance = maintenanceQuery.data?.data;
  const isActive = maintenance?.state.toLowerCase().includes("active");
  const isScheduled =
    maintenance?.schedule_active || maintenance?.schedule_upcoming;

  return (
    <AdminOverviewCard
      description="See whether a maintenance window is active or upcoming."
      icon={Wrench}
      title="Maintenance"
    >
      {maintenanceQuery.isPending ? <AdminCardLoading lines={4} /> : null}
      {maintenanceQuery.isError ? (
        <AdminCardError onRetry={() => void maintenanceQuery.refetch()} />
      ) : null}
      {maintenance ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-2xl font-bold">
                {formatAdminLabel(maintenance.state)}
              </p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {maintenance.message}
              </p>
            </div>
            <AdminStatusBadge
              tone={isActive ? "negative" : isScheduled ? "warning" : "positive"}
            >
              {isActive ? "Active" : isScheduled ? "Scheduled" : "Clear"}
            </AdminStatusBadge>
          </div>

          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-2xl border border-[var(--compass-border)] p-3">
              <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
                Source
              </dt>
              <dd className="mt-1 font-semibold">{formatAdminLabel(maintenance.source)}</dd>
            </div>
            <div className="rounded-2xl border border-[var(--compass-border)] p-3">
              <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
                Expected end
              </dt>
              <dd className="mt-1 font-semibold">
                {formatAdminDate(maintenance.manual_expected_end_at ?? maintenance.scheduled_end_at)}
              </dd>
            </div>
          </dl>
        </div>
      ) : null}
    </AdminOverviewCard>
  );
}

"use client";

import { History } from "lucide-react";

import {
  usePlatformOperationsListActivity,
} from "@/lib/api/generated/platform-operations/platform-operations";
import {
  AdminCardError,
  AdminCardLoading,
  AdminOverviewCard,
  formatAdminDate,
  formatAdminLabel,
} from "@/features/portal/admin/portal-it-admin-shared";

export function PortalItAdminActivityCard() {
  const activityQuery = usePlatformOperationsListActivity(
    { page: 1, page_size: 5 },
    {
      query: {
        retry: false,
        staleTime: 30_000,
      },
    },
  );
  const activity = activityQuery.data?.data;

  return (
    <AdminOverviewCard
      description="The latest curated technical activity visible to operators."
      icon={History}
      title="Recent platform activity"
    >
      {activityQuery.isPending ? <AdminCardLoading lines={5} /> : null}
      {activityQuery.isError ? (
        <AdminCardError onRetry={() => void activityQuery.refetch()} />
      ) : null}
      {activity ? (
        activity.items.length ? (
          <ol className="divide-y rounded-2xl border border-[var(--compass-border)]">
            {activity.items.map((item) => (
              <li key={item.id} className="px-4 py-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-semibold">{item.title}</p>
                  <time
                    className="shrink-0 text-xs text-muted-foreground"
                    dateTime={item.occurred_at}
                  >
                    {formatAdminDate(item.occurred_at)}
                  </time>
                </div>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  {item.description}
                </p>
                <p className="mt-1 text-xs font-semibold text-[var(--compass-support-strong)]">
                  {item.actor_display_name ?? formatAdminLabel(item.actor_type)}
                </p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-muted)] p-4 text-sm text-muted-foreground">
            No recent platform activity to show.
          </p>
        )
      ) : null}
    </AdminOverviewCard>
  );
}

"use client";

import { Mail } from "lucide-react";

import {
  usePlatformOperationsGetEmailDeliverySummary,
} from "@/lib/api/generated/platform-operations/platform-operations";
import {
  AdminCardError,
  AdminCardLoading,
  AdminMetric,
  AdminOverviewCard,
} from "@/features/portal/admin/portal-it-admin-shared";

export function PortalItAdminEmailCard() {
  const emailQuery = usePlatformOperationsGetEmailDeliverySummary({
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const summary = emailQuery.data?.data;

  return (
    <AdminOverviewCard
      className="lg:col-span-2"
      description="Delivery counts from the operational email queue."
      icon={Mail}
      title="Email delivery"
    >
      {emailQuery.isPending ? <AdminCardLoading lines={3} /> : null}
      {emailQuery.isError ? (
        <AdminCardError onRetry={() => void emailQuery.refetch()} />
      ) : null}
      {summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <AdminMetric label="Pending" value={summary.pending_count} />
          <AdminMetric label="Processing" value={summary.processing_count} />
          <AdminMetric label="Failed" value={summary.failed_count} />
          <AdminMetric label="Sent today" value={summary.sent_today} />
          <AdminMetric label="Cancelled" value={summary.cancelled_count} />
        </div>
      ) : null}
    </AdminOverviewCard>
  );
}

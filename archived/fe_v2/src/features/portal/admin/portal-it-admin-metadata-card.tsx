"use client";

import { PackageCheck } from "lucide-react";

import { useSystemMetadata } from "@/lib/api/generated/metadata/metadata";
import {
  AdminCardError,
  AdminCardLoading,
  AdminOverviewCard,
  formatAdminDate,
} from "@/features/portal/admin/portal-it-admin-shared";

export function PortalItAdminMetadataCard() {
  const metadataQuery = useSystemMetadata({
    query: {
      retry: false,
      staleTime: 5 * 60_000,
    },
  });
  const metadata = metadataQuery.data?.data;

  return (
    <AdminOverviewCard
      description="Release details reported by COMPASS."
      icon={PackageCheck}
      title="Build information"
    >
      {metadataQuery.isPending ? <AdminCardLoading lines={4} /> : null}
      {metadataQuery.isError ? (
        <AdminCardError onRetry={() => void metadataQuery.refetch()} />
      ) : null}
      {metadata ? (
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Version
            </dt>
            <dd className="mt-1 font-semibold">{metadata.version}</dd>
          </div>
          <div>
            <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Environment
            </dt>
            <dd className="mt-1 font-semibold">{metadata.environment}</dd>
          </div>
          <div>
            <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Build ID
            </dt>
            <dd className="mt-1 break-all font-mono text-xs font-semibold">
              {metadata.build_id}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Built
            </dt>
            <dd className="mt-1 font-semibold">{formatAdminDate(metadata.built_at)}</dd>
          </div>
        </dl>
      ) : null}
    </AdminOverviewCard>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { pageSheetWidth } from "@/components/ui/page-width";
import { Skeleton } from "@/components/ui/skeleton";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { CounselorInventoryRoster } from "@/features/inventory/counselor/inventory-roster";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import {
  formatInventoryDate,
  InventoryHeading,
  InventoryNotice,
  InventoryQueryError,
  InventoryStatus,
} from "@/features/inventory/inventory-shared";
import { inventoryErrorMessage } from "@/features/inventory/inventory-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  getInventoryGetMyCurrentQueryKey,
  getInventoryGetMyStatusQueryKey,
  getInventoryListMyHistoryQueryKey,
  useInventoryEnsureMyCurrent,
  useInventoryGetMyStatus,
  useInventoryListMyHistory,
} from "@/lib/api/generated/inventory/inventory";
import { InventoryStatusValue } from "@/lib/api/generated/model";

export function InventoryHome() {
  const { user } = usePortalSession();
  const access = getInventoryAccess(user);
  const searchParams = useSearchParams();
  const reopenedNotice = searchParams.get("notice") === "reopened";

  if (access.canViewRoster) {
    return (
      <div>
        {reopenedNotice ? (
          <div className="mb-5">
            <InventoryNotice tone="success">The Individual Inventory was reopened for Student correction.</InventoryNotice>
          </div>
        ) : null}
        <CounselorInventoryRoster />
      </div>
    );
  }
  if (access.canViewSelf) {
    return (
      <div className={pageSheetWidth}>
        <StudentInventoryHome />
      </div>
    );
  }

  return (
    <WorkspaceUnavailable title="Individual Inventory unavailable">
      This workspace is available to Students for their own annual record and to Counselors for their authorized roster.
    </WorkspaceUnavailable>
  );
}

function StudentInventoryHome() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const access = getInventoryAccess(user);
  const [startError, setStartError] = useState<string | null>(null);
  const status = useInventoryGetMyStatus({ query: { retry: false } });
  const history = useInventoryListMyHistory({ query: { retry: false } });
  const ensure = useInventoryEnsureMyCurrent();
  const current = status.data?.data;
  const records = history.data?.data.items ?? [];

  async function startInventory() {
    setStartError(null);
    try {
      const response = await ensure.mutateAsync();
      queryClient.setQueryData(getInventoryGetMyCurrentQueryKey(), response);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getInventoryListMyHistoryQueryKey() }),
      ]);
      router.push("/portal/inventory/current");
    } catch (error) {
      setStartError(inventoryErrorMessage(error, "A new Individual Inventory could not be started."));
    }
  }

  return (
    <section aria-label="Individual Inventory">
      <InventoryHeading
        title="Individual Inventory"
      />

      <Panel className="mt-5 max-w-4xl" aria-labelledby="inventory-current-heading">
        <PanelHeader title="Current Academic Year" titleId="inventory-current-heading" />
        {status.isPending ? (
          <div className="space-y-3 px-4 py-4 sm:px-5" aria-busy="true">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-16" />
            <p className="sr-only">Loading current Individual Inventory status…</p>
          </div>
        ) : status.isError ? (
          <div className="px-4 py-4 sm:px-5">
            <InventoryQueryError error={status.error} fallback="Current Individual Inventory status could not be loaded." onRetry={() => void status.refetch()} />
          </div>
        ) : current ? (
          <div className="px-4 py-4 sm:px-5">
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="font-heading text-lg font-semibold text-ink">{current.academic_year.label}</h3>
              <InventoryStatus status={current.status} correctionPending={current.correction_pending} missingLabel="Not started" />
            </div>

            {current.status === InventoryStatusValue.MISSING ? (
              <div className="mt-4 max-w-3xl">
                {!access.isCurrentStudent ? (
                  <p className="text-sm leading-6 text-muted">
                    Only current students can start an Individual Inventory for this year. Your earlier records remain available below.
                  </p>
                ) : access.canManageSelf ? (
                  <div className="mt-4">
                    {startError ? <div className="mb-3"><InventoryNotice tone="danger" role="alert">{startError}</InventoryNotice></div> : null}
                    <Button disabled={ensure.isPending} onClick={() => void startInventory()}>
                      {ensure.isPending ? "Starting…" : "Start Individual Inventory"}
                    </Button>
                  </div>
                ) : (
                  <p className="mt-3 text-sm leading-6 text-muted">
                    Starting a current-year Individual Inventory is not available for this account.
                  </p>
                )}
              </div>
            ) : current.status === InventoryStatusValue.DRAFT ? (
              <div className="mt-4">
                {current.correction_pending && current.latest_correction ? (
                  <div className="mb-4">
                    <InventoryNotice title="Correction requested" tone="warning">
                      <p className="whitespace-pre-wrap">{current.latest_correction.message}</p>
                      <p className="mt-2 text-xs text-muted">Requested {formatInventoryDate(current.latest_correction.requested_at)}</p>
                    </InventoryNotice>
                  </div>
                ) : null}
                {access.canManageSelf ? null : (
                  <p className="mb-4 text-sm leading-6 text-muted">This draft can be viewed but no longer changed.</p>
                )}
                <Link
                  href="/portal/inventory/current"
                  className={buttonVariants({ variant: access.canManageSelf ? "primary" : "secondary" })}
                >
                  {access.canManageSelf ? "Continue Individual Inventory" : "View saved Individual Inventory"}
                </Link>
              </div>
            ) : (
              <div className="mt-4">
                <p className="text-sm leading-6 text-muted">
                  Submitted {formatInventoryDate(current.submitted_at)}
                  {current.form_revision ? ` · ${current.form_revision.official_code} · Revision ${current.form_revision.official_revision}` : ""}
                </p>
                <Link
                  href="/portal/inventory/current"
                  className={buttonVariants({ variant: "secondary", className: "mt-4" })}
                >
                  View submitted Inventory
                </Link>
              </div>
            )}
          </div>
        ) : null}
      </Panel>

      <Panel className="mt-5 max-w-4xl" aria-labelledby="inventory-history-heading">
        <PanelHeader
          title="Annual history"
          titleId="inventory-history-heading"
        />
        {history.isPending ? (
          <div className="space-y-3 px-4 py-4 sm:px-5" aria-busy="true">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
            <p className="sr-only">Loading annual Individual Inventory history…</p>
          </div>
        ) : history.isError ? (
          <div className="px-4 py-4 sm:px-5">
            <InventoryQueryError error={history.error} fallback="Annual Individual Inventory history could not be loaded." onRetry={() => void history.refetch()} />
          </div>
        ) : records.length === 0 ? (
          <PanelMessage>
            {current?.status === InventoryStatusValue.MISSING
              ? "No Individual Inventory records yet."
              : "No earlier Individual Inventory records."}
          </PanelMessage>
        ) : (
          <ul className="divide-y divide-border">
            {records.map((record) => (
              <li key={record.id} className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                <div className="min-w-0">
                  <Link
                    href={`/portal/inventory/history/${record.id}`}
                    className="font-semibold text-ink hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    {record.academic_year.label}
                  </Link>
                  <p className="mt-1 text-xs text-muted">
                    {record.form_revision.official_code} · Revision {record.form_revision.official_revision}
                    {record.last_submitted_at ? ` · Last submitted ${formatInventoryDate(record.last_submitted_at)}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <InventoryStatus status={record.status} correctionPending={record.correction_pending} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </section>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
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
  if (access.canViewSelf) return <StudentInventoryHome />;

  return (
    <InventoryNotice title="Individual Inventory is unavailable" tone="warning">
      This workspace is available to Students for their own annual record and to Counselors for their authorized roster.
    </InventoryNotice>
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
        description="Your annual record for the Guidance and Counseling Office."
      />

      <section className="mt-7" aria-labelledby="inventory-current-heading">
        <h2 id="inventory-current-heading" className="font-heading text-xl font-semibold text-ink">Current Academic Year</h2>
        {status.isPending ? (
          <div className="mt-4 space-y-3" aria-busy="true">
            <div className="h-5 w-48 animate-pulse rounded bg-surface-muted" />
            <div className="h-16 animate-pulse rounded bg-surface-muted" />
            <p className="sr-only">Loading current Individual Inventory status…</p>
          </div>
        ) : status.isError ? (
          <div className="mt-4">
            <InventoryQueryError error={status.error} fallback="Current Individual Inventory status could not be loaded." onRetry={() => void status.refetch()} />
          </div>
        ) : current ? (
          <div className="mt-4 border-y border-border py-5">
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="font-heading text-lg font-semibold text-ink">{current.academic_year.label}</h3>
              <InventoryStatus status={current.status} correctionPending={current.correction_pending} />
            </div>

            {current.status === InventoryStatusValue.MISSING ? (
              <div className="mt-4 max-w-3xl">
                <p className="text-sm leading-6 text-muted">Complete one Individual Inventory for the current Academic Year.</p>
                {!access.isCurrentStudent ? (
                  <p className="mt-3 text-sm leading-6 text-muted">
                    A new current-year Individual Inventory can only be started while your Student lifecycle is current. Your annual history remains available below.
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
                <p className="text-sm leading-6 text-muted">
                  {access.canManageSelf
                    ? "Your saved progress is a draft. You can continue editing and save it before submission."
                    : "This annual record is a draft. Your current Student lifecycle does not allow further changes."}
                </p>
                <Link
                  href="/portal/inventory/current"
                  className="mt-4 inline-flex min-h-10 items-center rounded-md border border-brand px-4 py-2 text-sm font-semibold text-brand hover:bg-brand-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
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
                  className="mt-4 inline-flex min-h-10 items-center rounded-md border border-brand px-4 py-2 text-sm font-semibold text-brand hover:bg-brand-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  View submitted Inventory
                </Link>
              </div>
            )}
          </div>
        ) : null}
      </section>

      <section className="mt-9" aria-labelledby="inventory-history-heading">
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-3">
          <div>
            <h2 id="inventory-history-heading" className="font-heading text-xl font-semibold text-ink">Annual history</h2>
            <p className="mt-1 text-sm text-muted">Earlier Academic Years remain available as read-only records.</p>
          </div>
        </div>
        {history.isPending ? (
          <div className="mt-4 space-y-3" aria-busy="true">
            <div className="h-12 animate-pulse rounded bg-surface-muted" />
            <div className="h-12 animate-pulse rounded bg-surface-muted" />
            <p className="sr-only">Loading annual Individual Inventory history…</p>
          </div>
        ) : history.isError ? (
          <div className="mt-4">
            <InventoryQueryError error={history.error} fallback="Annual Individual Inventory history could not be loaded." onRetry={() => void history.refetch()} />
          </div>
        ) : records.length === 0 ? (
          <p className="py-6 text-sm text-muted">
            {current?.status === InventoryStatusValue.MISSING
              ? "No Individual Inventory records yet."
              : "No earlier Individual Inventory records."}
          </p>
        ) : (
          <ul className="divide-y divide-border border-b border-border">
            {records.map((record) => (
              <li key={record.id} className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
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
                  {record.correction_pending ? <span className="text-xs text-warning">Correction pending</span> : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

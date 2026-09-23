"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { InventoryEditor } from "@/features/inventory/editor/inventory-editor";
import { InventoryReadOnly } from "@/features/inventory/read-only/inventory-read-only";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { formatInventoryDate, InventoryHeading, InventoryNotice, InventoryQueryError, InventoryStatus } from "@/features/inventory/inventory-shared";
import { inventoryErrorMessage } from "@/features/inventory/inventory-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getInventoryGetMyCurrentQueryKey,
  getInventoryGetMyStatusQueryKey,
  getInventoryListMyHistoryQueryKey,
  useInventoryEnsureMyCurrent,
  useInventoryGetMyCurrent,
  useInventoryGetMyStatus,
} from "@/lib/api/generated/inventory/inventory";
import { InventoryStatusValue } from "@/lib/api/generated/model";
import { useQueryClient } from "@tanstack/react-query";

export function CurrentInventoryPage() {
  const { user } = usePortalSession();
  const access = getInventoryAccess(user);
  if (!access.canViewSelf) {
    return (
      <InventoryNotice title="Individual Inventory is unavailable" tone="warning">
        This current-record view is available only to Students with access to their own Individual Inventory.
      </InventoryNotice>
    );
  }
  return <StudentCurrentInventory />;
}

function StudentCurrentInventory() {
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const access = getInventoryAccess(user);
  const [startError, setStartError] = useState<string | null>(null);
  const status = useInventoryGetMyStatus({ query: { retry: false } });
  const value = status.data?.data;
  const record = useInventoryGetMyCurrent({
    query: {
      enabled: Boolean(value && value.status !== InventoryStatusValue.MISSING),
      retry: false,
    },
  });
  const ensure = useInventoryEnsureMyCurrent();

  async function start() {
    setStartError(null);
    try {
      const response = await ensure.mutateAsync();
      queryClient.setQueryData(getInventoryGetMyCurrentQueryKey(), response);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getInventoryListMyHistoryQueryKey() }),
      ]);
    } catch (error) {
      setStartError(inventoryErrorMessage(error, "A new Individual Inventory could not be started."));
      await queryClient.invalidateQueries({ queryKey: getInventoryGetMyStatusQueryKey() });
    }
  }

  if (status.isPending) {
    return (
      <section aria-busy="true" className="space-y-5">
        <InventoryHeading title="Individual Inventory" />
        <div className="h-7 w-48 animate-pulse rounded bg-surface-muted" />
        <div className="h-48 animate-pulse rounded bg-surface-muted" />
        <p className="sr-only">Checking current Individual Inventory status…</p>
      </section>
    );
  }

  if (status.isError) {
    return (
      <section className="space-y-5">
        <InventoryHeading title="Individual Inventory" />
        <InventoryQueryError error={status.error} fallback="Current Individual Inventory status could not be loaded." onRetry={() => void status.refetch()} />
      </section>
    );
  }

  if (value?.status === InventoryStatusValue.MISSING) {
    return (
      <section className="space-y-5">
        <InventoryHeading title="Individual Inventory" description={value.academic_year.label} />
        <InventoryNotice title="No current-year record yet" tone="neutral">
          Opening this page does not create an Individual Inventory. Start is an explicit action, and the record will be bound to the current Academic Year and active official Form Revision.
        </InventoryNotice>
        <div className="flex flex-wrap gap-3">
          <Link href="/portal/inventory" className="inline-flex min-h-10 items-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            Return to annual status
          </Link>
          {access.canManageSelf ? (
            <Button disabled={ensure.isPending} onClick={() => void start()}>
              {ensure.isPending ? "Starting…" : "Start Individual Inventory"}
            </Button>
          ) : (
            <p className="self-center text-sm text-muted">
              {access.isCurrentStudent
                ? "Starting a current-year Individual Inventory is not available for this account."
                : "A new current-year Individual Inventory can only be started while your Student lifecycle is current."}
            </p>
          )}
        </div>
        {startError ? <InventoryNotice tone="danger" role="alert">{startError}</InventoryNotice> : null}
      </section>
    );
  }

  if (record.isPending) {
    return (
      <section aria-busy="true" className="space-y-5">
        <InventoryHeading title="Individual Inventory" />
        <div className="h-8 w-56 animate-pulse rounded bg-surface-muted" />
        <div className="h-64 animate-pulse rounded bg-surface-muted" />
        <p className="sr-only">Loading current Individual Inventory…</p>
      </section>
    );
  }

  if (record.isError) {
    return (
      <section className="space-y-5">
        <InventoryHeading title="Individual Inventory" />
        <InventoryQueryError error={record.error} fallback="Current Individual Inventory could not be loaded." onRetry={() => void record.refetch()} />
      </section>
    );
  }

  const inventory = record.data.data;
  if (inventory.status === InventoryStatusValue.DRAFT && access.canManageSelf) {
    return <InventoryEditor key={inventory.id} inventory={inventory} />;
  }

  return (
    <section aria-label="Current Individual Inventory">
      <InventoryHeading
        title="Individual Inventory"
        description={`${inventory.academic_year.label} · ${inventory.form_revision.official_code} · Revision ${inventory.form_revision.official_revision}`}
      />
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <InventoryStatus status={inventory.status} correctionPending={inventory.correction_pending} />
        {inventory.submitted_at ? <span className="text-sm text-muted">Submitted {formatInventoryDate(inventory.submitted_at)}</span> : null}
      </div>
      {inventory.status === InventoryStatusValue.DRAFT ? (
        <div className="mt-5">
          <InventoryNotice title="Read-only annual record" tone="warning">
            Your Student lifecycle is not current, so this draft can no longer be changed or submitted. You can still read this annual record.
          </InventoryNotice>
        </div>
      ) : null}
      {inventory.correction_pending && inventory.latest_correction ? (
        <div className="mt-5">
          <InventoryNotice title="Correction requested" tone="warning">
            <p className="whitespace-pre-wrap">{inventory.latest_correction.message}</p>
            <p className="mt-2 text-xs text-muted">Requested {formatInventoryDate(inventory.latest_correction.requested_at)}</p>
          </InventoryNotice>
        </div>
      ) : null}
      <div className="mt-7">
        <InventoryReadOnly inventory={inventory} />
      </div>
    </section>
  );
}

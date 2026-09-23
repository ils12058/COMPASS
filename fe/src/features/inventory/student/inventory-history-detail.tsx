"use client";

import Link from "next/link";

import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { InventoryReadOnly } from "@/features/inventory/read-only/inventory-read-only";
import { formatInventoryDate, InventoryHeading, InventoryNotice, InventoryQueryError, InventoryStatus } from "@/features/inventory/inventory-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useInventoryGetMyHistoryItem } from "@/lib/api/generated/inventory/inventory";

export function InventoryHistoryDetail({ inventoryId }: { inventoryId: string }) {
  const { user } = usePortalSession();
  const access = getInventoryAccess(user);
  if (!access.canViewSelf) {
    return (
      <InventoryNotice title="Individual Inventory is unavailable" tone="warning">
        This historical record is available only to its Student through the self-service Inventory workspace.
      </InventoryNotice>
    );
  }
  return <StudentInventoryHistoryDetail inventoryId={inventoryId} />;
}

function StudentInventoryHistoryDetail({ inventoryId }: { inventoryId: string }) {
  const record = useInventoryGetMyHistoryItem(inventoryId, {
    query: { retry: false },
  });

  if (record.isPending) {
    return (
      <section aria-busy="true" className="space-y-5">
        <InventoryHeading title="Annual Individual Inventory" />
        <div className="h-8 w-56 animate-pulse rounded bg-surface-muted" />
        <div className="h-64 animate-pulse rounded bg-surface-muted" />
        <p className="sr-only">Loading annual Individual Inventory record…</p>
      </section>
    );
  }

  if (record.isError) {
    return (
      <section className="space-y-5">
        <InventoryHeading title="Annual Individual Inventory" />
        <InventoryQueryError error={record.error} fallback="This annual Individual Inventory could not be found or is not available to you." />
        <Link href="/portal/inventory" className="inline-flex min-h-10 items-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          Return to annual history
        </Link>
      </section>
    );
  }

  const inventory = record.data.data;
  return (
    <section aria-label="Historical Individual Inventory">
      <InventoryHeading
        title="Annual Individual Inventory"
        description={`${inventory.academic_year.label} · ${inventory.form_revision.official_code} · Revision ${inventory.form_revision.official_revision}`}
        action={
          <Link href="/portal/inventory" className="inline-flex min-h-10 items-center justify-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            Annual history
          </Link>
        }
      />
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <InventoryStatus status={inventory.status} correctionPending={inventory.correction_pending} />
        {inventory.submitted_at ? <span className="text-sm text-muted">Submitted {formatInventoryDate(inventory.submitted_at)}</span> : null}
      </div>
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

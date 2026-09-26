"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { InventoryReadOnly } from "@/features/inventory/read-only/inventory-read-only";
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
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import {
  getInventoryGetRecordQueryKey,
  getInventoryListStudentsQueryKey,
  getInventoryListStudentHistoryQueryKey,
  useInventoryGetRecord,
  useInventoryListStudentHistory,
  useInventoryReopenRecord,
} from "@/lib/api/generated/inventory/inventory";
import { InventoryStatusValue } from "@/lib/api/generated/model";
import { useQueryClient } from "@tanstack/react-query";

export function InventoryRecordDetail({ inventoryId }: { inventoryId: string }) {
  const { user } = usePortalSession();
  const access = getInventoryAccess(user);
  if (!access.canViewRoster) {
    return (
      <WorkspaceUnavailable title="Individual Inventory unavailable">
        Submitted Inventory detail is available only to Counselors with Individual Inventory review access.
      </WorkspaceUnavailable>
    );
  }
  return <CounselorInventoryRecordDetail inventoryId={inventoryId} />;
}

function CounselorInventoryRecordDetail({ inventoryId }: { inventoryId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const access = getInventoryAccess(user);
  const record = useInventoryGetRecord(inventoryId, { query: { retry: false } });
  const academicYears = useAcademicYearsList({
    query: {
      enabled: user.capabilities.includes("academic_years.view"),
      retry: false,
    },
  });
  const reopen = useInventoryReopenRecord();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [reopenOpen, setReopenOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reopenError, setReopenError] = useState<string | null>(null);
  const [reopenCompleted, setReopenCompleted] = useState(false);

  if (record.isPending) {
    return (
      <section aria-busy="true" className="space-y-5">
        <InventoryHeading title="Submitted Individual Inventory" />
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-64" />
        <p className="sr-only">Loading authorized submitted Individual Inventory…</p>
      </section>
    );
  }

  if (record.isError) {
    return (
      <section className="space-y-5">
        <InventoryHeading title="Submitted Individual Inventory" />
        <InventoryQueryError error={record.error} fallback="This Individual Inventory could not be found or is not available within your authorized scope." />
        <Link href="/portal/inventory" className="inline-flex min-h-10 items-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          Return to roster
        </Link>
      </section>
    );
  }

  const inventory = record.data.data;
  const years = academicYears.data?.data.items ?? [];
  const currentYear = years.find((year) => year.is_current);
  const isKnownHistorical = Boolean(currentYear && currentYear.id !== inventory.academic_year.id);
  const canReopen = access.canReopen &&
    inventory.status === InventoryStatusValue.SUBMITTED &&
    !isKnownHistorical;

  async function confirmReopen() {
    const instructions = reason.trim();
    if (!canReopen || !instructions || instructions.length > 1000 || reopen.isPending) return;
    setReopenError(null);
    try {
      await reopen.mutateAsync({ inventoryId, data: { reason: instructions } });
      queryClient.removeQueries({ queryKey: getInventoryGetRecordQueryKey(inventoryId) });
      setReopenCompleted(true);
      setReopenOpen(false);
      router.replace("/portal/inventory?notice=reopened");
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: getInventoryListStudentsQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getInventoryListStudentHistoryQueryKey(inventory.student.id) }),
      ]);
    } catch (error) {
      setReopenError(inventoryErrorMessage(error, "This Individual Inventory could not be reopened."));
    }
  }

  if (inventory.status !== InventoryStatusValue.SUBMITTED) {
    return (
      <section className="space-y-5">
        <InventoryHeading title="Submitted Individual Inventory" />
        <InventoryNotice title="Draft content is not available for Counselor review" tone="warning">
          This Individual Inventory is currently a draft and is not available for Counselor review.
        </InventoryNotice>
        <Link href="/portal/inventory" className="inline-flex min-h-10 items-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          Return to roster
        </Link>
      </section>
    );
  }

  if (reopenCompleted) {
    return (
      <InventoryNotice title="Inventory reopened" tone="success">
        The Student can now review the correction instructions and update the Individual Inventory.
      </InventoryNotice>
    );
  }

  return (
    <section aria-label="Counselor submitted Individual Inventory detail">
      <InventoryHeading
        title="Submitted Individual Inventory"
        description={`${inventory.academic_year.label} · ${inventory.form_revision.official_code} · Revision ${inventory.form_revision.official_revision}`}
        action={(
          <Link href="/portal/inventory" className="inline-flex min-h-10 items-center justify-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            Roster
          </Link>
        )}
      />
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <InventoryStatus status={inventory.status} correctionPending={inventory.correction_pending} />
        {inventory.submitted_at ? <span className="text-sm text-muted">Submitted {formatInventoryDate(inventory.submitted_at)}</span> : null}
        {inventory.last_submitted_at && inventory.last_submitted_at !== inventory.submitted_at ? (
          <span className="text-sm text-muted">Last submitted {formatInventoryDate(inventory.last_submitted_at)}</span>
        ) : null}
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <Button variant="secondary" onClick={() => setHistoryOpen((open) => !open)}>
          {historyOpen ? "Hide annual history" : "View annual Inventory history"}
        </Button>
        {canReopen ? (
          <Button variant="secondary" onClick={() => {
            setReopenError(null);
            setReopenOpen(true);
          }}>
            Reopen for correction
          </Button>
        ) : null}
      </div>

      {historyOpen ? (
        <div className="mt-5 border-y border-border py-5">
          <CounselorStudentInventoryHistory studentId={inventory.student.id} currentInventoryId={inventory.id} />
        </div>
      ) : null}

      <div className="mt-7">
        <InventoryReadOnly
          inventory={inventory}
          studentIdentity={{
            display_name: inventory.student.display_name,
            institutional_id: inventory.student.institutional_id,
          }}
        />
      </div>

      <AlertDialog open={reopenOpen} onOpenChange={(open) => {
        if (reopen.isPending) return;
        setReopenOpen(open);
      }}>
        <AlertDialogContent>
          <AlertDialogTitle>Reopen {inventory.student.display_name}&apos;s Individual Inventory for correction?</AlertDialogTitle>
          <AlertDialogDescription>
            The Student will be able to edit and resubmit this current-year Inventory. While it is reopened, its contents will no longer be available for Counselor review until the Student resubmits it.
          </AlertDialogDescription>
          <div className="mt-5">
            <Label htmlFor="inventory-reopen-instructions">
              Correction instructions <span aria-hidden="true" className="text-danger">*</span>
            </Label>
            <p id="inventory-reopen-help" className="mt-1 text-xs leading-5 text-muted">
              This message will be visible to the Student.
            </p>
            <Textarea
              id="inventory-reopen-instructions"
              value={reason}
              maxLength={1000}
              aria-required="true"
              aria-describedby="inventory-reopen-help inventory-reopen-count"
              rows={5}
              onChange={(event) => setReason(event.target.value)}
            />
            <p id="inventory-reopen-count" className="mt-1 text-right text-xs text-muted">
              {reason.length} / 1000 characters
            </p>
          </div>
          {reopenError ? <div className="mt-4"><InventoryNotice tone="danger" role="alert">{reopenError}</InventoryNotice></div> : null}
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={reopen.isPending}>Cancel</Button>
            </AlertDialogCancel>
            <Button
              disabled={!reason.trim() || reason.length > 1000 || reopen.isPending}
              onClick={() => void confirmReopen()}
            >
              {reopen.isPending ? "Reopening…" : "Reopen for correction"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

function CounselorStudentInventoryHistory({
  studentId,
  currentInventoryId,
}: {
  studentId: string;
  currentInventoryId: string;
}) {
  const history = useInventoryListStudentHistory(studentId, { query: { retry: false } });

  if (history.isPending) {
    return <p role="status" className="text-sm text-muted">Loading annual Student Inventory history…</p>;
  }
  if (history.isError) {
    return <InventoryQueryError error={history.error} fallback="Annual Student Inventory history could not be loaded." onRetry={() => void history.refetch()} />;
  }
  const items = history.data.data.items;
  if (!items.length) return <p className="text-sm text-muted">No annual Individual Inventory records were returned.</p>;

  return (
    <section aria-labelledby="counselor-inventory-history-heading">
      <h2 id="counselor-inventory-history-heading" className="font-heading text-lg font-semibold text-ink">Annual Student Inventory history</h2>
      <ul className="mt-3 divide-y divide-border border-y border-border">
        {items.map((item) => {
          const link = item.status === InventoryStatusValue.SUBMITTED;
          const identity = (
            <>
              {item.academic_year.label}{item.inventory_id === currentInventoryId ? " · Current record" : ""}
            </>
          );
          return (
            <li key={item.inventory_id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                {link ? (
                  <Link href={`/portal/inventory/records/${item.inventory_id}`} className="font-semibold text-ink hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                    {identity}
                  </Link>
                ) : <p className="font-semibold text-ink">{identity}</p>}
                <p className="mt-1 text-xs text-muted">
                  {item.program ? `${item.program.code} · ${item.program.name}` : "Program not provided"}
                  {item.year_level ? ` · Year ${item.year_level}` : ""}
                  {item.last_submitted_at ? ` · Last submitted ${formatInventoryDate(item.last_submitted_at)}` : ""}
                </p>
              </div>
              <InventoryStatus status={item.status} correctionPending={item.correction_pending} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

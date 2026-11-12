"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  caseErrorMessage,
  caseSessionRemovalReasons,
  isStaleCaseError,
  isUncertainCaseResult,
} from "@/features/counseling/cases/case-presentation";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  useCounselingLinkCaseSession,
  useCounselingListCaseSessionCandidates,
  useCounselingUnlinkCaseSession,
} from "@/lib/api/generated/counseling/counseling";
import type {
  CounselingCaseDetailResponse,
  CounselingCaseSessionRemovalReason,
  CounselingCaseSessionResponse,
} from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";

const unconfirmed = "Couldn't confirm whether the case changed. Close this and check the case before trying again.";

type CaseChange = {
  // The backend's confirmed case after the change.
  onChanged: (next: CounselingCaseDetailResponse, message: string) => void;
  // The case changed underneath the reader; the page reloads it and says so.
  onStale: () => void;
};

// Adds one of the Counselor's own recorded sessions with this Student to the case. Only sessions
// that are in no case are offered; nothing is chosen for the Counselor.
export function AddSessionDialog({
  open,
  onOpenChange,
  caseItem,
  onChanged,
  onStale,
}: CaseChange & {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  caseItem: CounselingCaseDetailResponse;
}) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);
  const candidates = useCounselingListCaseSessionCandidates(
    caseItem.id,
    { page, page_size: 10 },
    { query: { enabled: open, retry: false, staleTime: 0 } },
  );
  const link = useCounselingLinkCaseSession({ mutation: { retry: false } });
  const items = candidates.data?.data.items ?? [];

  function close(next: boolean) {
    if (link.isPending) return;
    if (!next) {
      setSelected("");
      setError(null);
      setPage(1);
    }
    onOpenChange(next);
  }

  async function add() {
    if (!selected || link.isPending) return;
    setError(null);
    try {
      const response = await link.mutateAsync({
        caseId: caseItem.id,
        data: { encounter_id: selected, expected_version: caseItem.version },
      });
      setSelected("");
      setPage(1);
      onOpenChange(false);
      onChanged(response.data, "Session added to this case.");
    } catch (caught) {
      if (isStaleCaseError(caught)) {
        setSelected("");
        setPage(1);
        onOpenChange(false);
        onStale();
        return;
      }
      setError(isUncertainCaseResult(caught) ? unconfirmed : caseErrorMessage(caught, "The session couldn't be added. Try again."));
      void candidates.refetch();
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent dismissible={!link.isPending} aria-busy={link.isPending}>
        <DialogTitle className="pr-10 font-heading text-xl font-semibold text-ink">Add a recorded session</DialogTitle>
        <DialogDescription className="mt-2 text-sm leading-6 text-muted">
          Your recorded sessions with {caseItem.student.display_name} that aren&apos;t in a case. Adding one doesn&apos;t change the session record.
        </DialogDescription>
        <div className="mt-4">
          {candidates.isPending ? (
            <div aria-busy="true" className="space-y-2"><span className="sr-only">Loading recorded sessions…</span><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /></div>
          ) : candidates.isError ? (
            <div role="alert"><p className="text-sm text-danger">{caseErrorMessage(candidates.error, "Couldn't load your recorded sessions.")}</p><Button variant="secondary" className="mt-3" onClick={() => void candidates.refetch()}>Retry</Button></div>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted">Every session you recorded with this Student is already in a case.</p>
          ) : (
            <>
              <ul className="divide-y divide-border rounded-sm border border-border" aria-label="Recorded sessions not in a case">
                {items.map((item) => (
                  <li key={item.encounter_id}>
                    <button
                      type="button"
                      aria-pressed={selected === item.encounter_id}
                      disabled={link.isPending}
                      onClick={() => { setSelected(item.encounter_id); setError(null); }}
                      className={`w-full px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus ${selected === item.encounter_id ? "bg-brand-wash" : "hover:bg-surface-subtle"}`}
                    >
                      <span className="block text-sm font-semibold text-ink">{formatCounselingDateTime(item.started_at)} – {formatCounselingDateTime(item.ended_at)}</span>
                      <span className="mt-1 block text-sm text-muted">{counselingEntryModeLabel(item.entry_mode)} · {counselingDeliveryModeLabel(item.delivery_mode)}{item.appointment ? ` · Appointment ${item.appointment.reference_code}` : ""}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <CanonicalPagination className="border-t-0 pb-0" label="Recorded session pages" page={candidates.data?.data.page ?? page} hasNext={candidates.data?.data.has_next ?? false} onPageChange={(next) => { setPage(next); setSelected(""); }} />
            </>
          )}
        </div>
        {error ? <p role="alert" className="mt-4 text-sm leading-6 text-danger">{error}</p> : null}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" disabled={link.isPending} onClick={() => close(false)}>Cancel</Button>
          <Button disabled={!selected || link.isPending} aria-busy={link.isPending} onClick={() => void add()}>{link.isPending ? "Adding session…" : "Add to case"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Corrects a wrong link. The session record, its author and any published summary are untouched,
// and the removed link stays in the case history.
export function RemoveSessionDialog({
  session,
  onClose,
  caseItem,
  onChanged,
  onStale,
}: CaseChange & {
  session: CounselingCaseSessionResponse | null;
  onClose: () => void;
  caseItem: CounselingCaseDetailResponse;
}) {
  const [reason, setReason] = useState<CounselingCaseSessionRemovalReason | "">("");
  const [error, setError] = useState<string | null>(null);
  const unlink = useCounselingUnlinkCaseSession({ mutation: { retry: false } });
  const removed = useRef(false);

  function close() {
    setReason("");
    setError(null);
    onClose();
  }

  async function remove() {
    if (!session || !reason || unlink.isPending) return;
    setError(null);
    try {
      const response = await unlink.mutateAsync({
        caseId: caseItem.id,
        encounterId: session.encounter_id,
        data: { reason, expected_version: caseItem.version },
      });
      removed.current = true;
      close();
      onChanged(response.data, "Session removed from this case.");
    } catch (caught) {
      if (isStaleCaseError(caught)) {
        close();
        onStale();
        return;
      }
      setError(isUncertainCaseResult(caught) ? unconfirmed : caseErrorMessage(caught, "The session couldn't be removed. Try again."));
    }
  }

  return (
    <ConsequentialActionDialog
      open={session !== null}
      title="Remove this session from the case?"
      confirmLabel="Remove from case"
      pendingLabel="Removing session…"
      pending={unlink.isPending}
      confirmDisabled={!reason}
      error={error}
      onOpenChange={(next) => { if (!next) close(); }}
      onConfirm={() => void remove()}
      onCloseAutoFocus={(event) => {
        if (removed.current) {
          event.preventDefault();
          focusHeading("case-sessions-heading");
          removed.current = false;
        }
      }}
      choices={
        <div className="grid gap-2">
          <Label htmlFor="case-session-removal-reason">Why it doesn&apos;t belong here</Label>
          <Select id="case-session-removal-reason" value={reason} disabled={unlink.isPending} onChange={(event) => { setReason(event.target.value as CounselingCaseSessionRemovalReason | ""); setError(null); }}>
            <option value="">Choose a reason</option>
            {caseSessionRemovalReasons.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </Select>
        </div>
      }
    >
      <p>
        The session of {session ? formatCounselingDateTime(session.started_at) : ""} will no longer count in this case. Its record, its author and any published Student Session Summary stay as they are.
      </p>
      <p>You can add it to the right case afterwards. This correction stays in the case history.</p>
    </ConsequentialActionDialog>
  );
}

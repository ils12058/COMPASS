"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { LoadingRegion } from "@/components/ui/loading-region";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { caseErrorMessage, isStaleCaseError, isUncertainCaseResult } from "./case-presentation";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import {
  useCounselingLinkCaseAppointment, useCounselingListCaseAppointmentCandidates,
  useCounselingUnlinkCaseAppointment,
} from "@/lib/api/generated/counseling/counseling";
import {
  CounselingCaseAppointmentRemovalReason,
  type CounselingCaseAppointmentResponse, type CounselingCaseDetailResponse,
} from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";

type CaseChange = {
  onChanged: (next: CounselingCaseDetailResponse, message: string) => void;
  onStale: () => void;
};
const unconfirmed = "Couldn't confirm whether the case changed. Close this and check the case before trying again.";

export function LinkAppointmentDialog({ open, onOpenChange, caseItem, onChanged, onStale }: CaseChange & {
  open: boolean; onOpenChange: (open: boolean) => void; caseItem: CounselingCaseDetailResponse;
}) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const candidates = useCounselingListCaseAppointmentCandidates(caseItem.id, { page, page_size: 10 }, {
    query: { enabled: open, retry: false, staleTime: 0 },
  });
  const mutation = useCounselingLinkCaseAppointment({ mutation: { retry: false } });
  const items = candidates.data?.data.items ?? [];
  function close(next: boolean) {
    if (mutation.isPending) return;
    if (!next) { setPage(1); setSelected(""); setError(null); setUncertain(false); }
    onOpenChange(next);
  }
  async function link() {
    if (!selected || mutation.isPending || uncertain) return;
    setError(null);
    try {
      const response = await mutation.mutateAsync({
        caseId: caseItem.id, data: { appointment_id: selected, expected_version: caseItem.version },
      });
      close(false);
      onChanged(response.data, "Appointment linked to this case.");
    } catch (caught) {
      if (isStaleCaseError(caught)) { close(false); onStale(); return; }
      const unknown = isUncertainCaseResult(caught);
      setUncertain(unknown);
      setError(unknown ? unconfirmed : caseErrorMessage(caught, "The appointment couldn't be linked. Try again."));
      if (!unknown) void candidates.refetch();
    }
  }
  return <Dialog open={open} onOpenChange={close}>
    <DialogContent dismissible={!mutation.isPending} aria-busy={mutation.isPending}>
      <DialogTitle className="pr-10 font-heading text-xl font-semibold">Link appointment</DialogTitle>
      <DialogDescription className="mt-2 text-sm text-muted">Scheduled Counseling Appointments for {caseItem.student.display_name} with this case&apos;s primary Counselor. Linking one does not change its schedule.</DialogDescription>
      <div className="mt-4">
        {candidates.isPending ? <LoadingRegion label="Loading appointments"><p>Loading appointments…</p></LoadingRegion>
          : candidates.isError ? <div role="alert"><p className="text-sm text-danger">{caseErrorMessage(candidates.error, "Couldn't load appointments.")}</p><Button variant="secondary" onClick={() => void candidates.refetch()}>Retry</Button></div>
          : items.length ? <>
            <Label htmlFor="case-appointment-choice">Appointment</Label>
            <Select id="case-appointment-choice" value={selected} disabled={mutation.isPending || uncertain} onChange={event => { setSelected(event.target.value); setError(null); }}>
              <option value="">Choose an appointment</option>{items.map(item => <option key={item.id} value={item.id}>{item.reference_code} · {formatCounselingDateTime(item.starts_at)}</option>)}
            </Select>
          </> : <p className="text-sm text-muted">No eligible scheduled appointments are available to link.</p>}
        {candidates.data ? <CanonicalPagination label="Appointment pages" page={candidates.data.data.page} hasNext={candidates.data.data.has_next} disabled={mutation.isPending || uncertain} onPageChange={next => { setPage(next); setSelected(""); }} /> : null}
      </div>
      {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <Button variant="secondary" disabled={mutation.isPending} onClick={() => close(false)}>Cancel</Button>
        <Button disabled={!selected || !items.some(item => item.id === selected) || candidates.isError || candidates.isFetching || mutation.isPending || uncertain} onClick={() => void link()}>{mutation.isPending ? "Linking appointment…" : "Link to case"}</Button>
      </div>
    </DialogContent>
  </Dialog>;
}

export function UnlinkAppointmentDialog({ link, onClose, caseItem, onChanged, onStale }: CaseChange & {
  link: CounselingCaseAppointmentResponse | null; onClose: () => void; caseItem: CounselingCaseDetailResponse;
}) {
  const [reason, setReason] = useState<CounselingCaseAppointmentRemovalReason | "">("");
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const mutation = useCounselingUnlinkCaseAppointment({ mutation: { retry: false } });
  const removed = useRef(false);
  function close() { setReason(""); setError(null); setUncertain(false); onClose(); }
  async function unlink() {
    if (!link || !reason || mutation.isPending || uncertain) return;
    setError(null);
    try {
      const response = await mutation.mutateAsync({
        caseId: caseItem.id, appointmentId: link.appointment_id,
        data: { reason, expected_version: caseItem.version },
      });
      removed.current = true;
      close();
      onChanged(response.data, "Appointment unlinked from this case.");
    } catch (caught) {
      if (isStaleCaseError(caught)) { close(); onStale(); return; }
      const unknown = isUncertainCaseResult(caught);
      setUncertain(unknown);
      setError(unknown ? unconfirmed : caseErrorMessage(caught, "The appointment couldn't be unlinked. Try again."));
    }
  }
  return <ConsequentialActionDialog open={link !== null} title="Unlink this appointment from the case?"
    confirmLabel="Unlink appointment" pendingLabel="Unlinking appointment…" pending={mutation.isPending}
    confirmDisabled={!reason || uncertain} error={error} onOpenChange={next => { if (!next) close(); }}
    onConfirm={() => void unlink()} onCloseAutoFocus={event => {
      if (removed.current) { event.preventDefault(); focusHeading("case-appointments-heading"); removed.current = false; }
    }} choices={<div className="grid gap-2">
      <Label htmlFor="case-appointment-removal-reason">Why it doesn&apos;t belong here</Label>
      <Select id="case-appointment-removal-reason" value={reason} disabled={mutation.isPending || uncertain} onChange={event => {
        const value = Object.values(CounselingCaseAppointmentRemovalReason).find(value => value === event.target.value);
        setReason(value ?? ""); setError(null);
      }}>
        <option value="">Choose a reason</option>
        <option value="BELONGS_TO_ANOTHER_CASE">It belongs to another case</option>
        <option value="NOT_PART_OF_THIS_CASE">It isn&apos;t part of this case</option>
        <option value="LINKED_BY_MISTAKE">It was linked by mistake</option>
      </Select>
    </div>}>
    <p>{link?.appointment?.reference_code ?? "The linked appointment"} will no longer appear as this case&apos;s next appointment. Its schedule and status stay as recorded.</p>
    <p>The removed link and its reason remain in the case&apos;s appointment history.</p>
  </ConsequentialActionDialog>;
}

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelBody } from "@/components/ui/panel";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import { useCounselingRecordCaseHandoffUnavailable } from "@/lib/api/generated/counseling/counseling";
import { CaseHandoffUnavailableReason, type CaseTransferDetailResponse } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { continuityError, continuityStale, enumChoice, transferHref } from "./continuity-presentation";

export const handoffExceptionLabels: Record<CaseHandoffUnavailableReason, string> = {
  OWNER_UNAVAILABLE: "Original Counselor unavailable",
  INFORMATION_NOT_OBTAINABLE: "Information cannot be obtained",
  IMPARTIALITY_CONCERN: "Handoff cannot appropriately be obtained",
};
export function TransferHandoffSection({ item, here, confirmed, onChanged, onStale }: {
  item: CaseTransferDetailResponse; here: string; confirmed: boolean;
  onChanged: () => Promise<unknown>; onStale: (message: string) => void;
}) {
  const mutation = useCounselingRecordCaseHandoffUnavailable({ mutation: { retry: false, gcTime: 0 } });
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<CaseHandoffUnavailableReason | "">("");
  const [version, setVersion] = useState(item.version);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const stale = !completed && version !== item.version;
  async function record() {
    if (!reason || mutation.isPending || !confirmed || stale) return;
    try {
      setError(null);
      await mutation.mutateAsync({ transferId: item.id, data: { reason, expected_transfer_version: version } });
      setCompleted(true);
      await onChanged();
    } catch (caught) {
      if (continuityStale(caught)) { setOpen(false); onStale(continuityError(caught)); await onChanged(); }
      else setError(continuityError(caught));
    }
  }
  return <Panel className="mt-5" aria-labelledby="transfer-handoff-heading">
    <PanelHeader title="Handoff" titleId="transfer-handoff-heading" />
    <PanelBody>
      {item.handoff ? <p className="text-sm">{item.handoff.state === "SUBMITTED" ? "Submitted · Immutable" : "Draft · Author only"} · {item.handoff.author.display_name}</p>
        : <Notice tone="warning">No handoff is available. {item.handoff_exception
          ? `${handoffExceptionLabels[item.handoff_exception.reason]} · Recorded by ${item.handoff_exception.recorded_by.display_name}`
          : item.handoff_required ? "A submitted handoff or Head exception is required before submission." : "This offer was submitted before the handoff requirement."}</Notice>}
      {item.handoff?.received_at ? <p className="mt-2 text-sm text-muted">Opened by {item.receiving_counselor.display_name} · {formatCounselingDateTime(item.handoff.received_at)}</p> : null}
      <div className="mt-3 flex flex-wrap gap-3">
        {item.can_read_handoff || item.can_write_handoff ? <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`${transferHref(item.id)}/handoff`, here)}>{item.handoff ? "Open handoff" : "Write handoff"}</Link> : null}
        {item.can_record_handoff_exception ? <Button variant="secondary" disabled={!confirmed} onClick={() => { setOpen(true); setVersion(item.version); setCompleted(false); setReason(""); setError(null); }}>Record handoff unavailable</Button> : null}
      </div>
      <ConsequentialActionDialog open={open} onOpenChange={setOpen} onCloseAutoFocus={event => { event.preventDefault(); focusHeading("transfer-handoff-heading"); }} title="Record handoff unavailable?" confirmLabel="Record exception" pendingLabel="Recording…" pending={mutation.isPending} confirmDisabled={!reason || stale || !confirmed} error={error}
        completed={completed ? { title: "Handoff exception recorded", children: "The preparer can now review and submit the available package." } : null}
        choices={<div className="grid gap-1"><Label htmlFor="case-handoff-exception-reason">Why is the handoff unavailable?</Label><Select id="case-handoff-exception-reason" value={reason} onChange={event => setReason(enumChoice(Object.values(CaseHandoffUnavailableReason), event.target.value) ?? "")}><option value="">Choose a reason</option>{Object.values(CaseHandoffUnavailableReason).map(value => <option key={value} value={value}>{handoffExceptionLabels[value]}</option>)}</Select></div>}
        onConfirm={() => void record()}>
        The receiver will see a missing-information warning. This records your decision without creating a clinical handoff or changing responsibility.
      </ConsequentialActionDialog>
    </PanelBody>
  </Panel>;
}

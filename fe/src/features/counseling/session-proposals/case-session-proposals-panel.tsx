"use client";

import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { appointmentStatusLabel } from "@/features/appointments/appointments-shared";
import { counselingDeliveryModeLabel, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import { useCounselingWithdrawSessionProposal } from "@/lib/api/generated/counseling/counseling";
import type { CounselingCaseDetailResponse, SessionProposalStaffResponse } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import {
  caseCallSlipHref,
  isStaleProposalError,
  isUncertainProposalResult,
  proposalErrorMessage,
  proposalStateLabel,
  proposeSessionHref,
  purposeLabel,
} from "./session-proposal-presentation";

const callSlipStateLabels: Record<string, string> = { ACTIVE: "Active", COMPLETED: "Interview ended", VOIDED: "Voided" };

export function CaseSessionProposalsPanel({ item, returnTo, confirmed, onChanged, onStale }: {
  item: CounselingCaseDetailResponse;
  returnTo: string;
  confirmed: boolean;
  onChanged: (message: string) => void;
  onStale: () => void;
}) {
  const [withdrawing, setWithdrawing] = useState<SessionProposalStaffResponse | null>(null);
  const proposals = item.session_proposals ?? [];
  const canPropose = confirmed && item.status === "ACTIVE" && item.can_propose_session;
  const open = proposals.some((proposal) => proposal.state === "PENDING");
  return <Panel className="mt-5" aria-labelledby="case-session-proposals-heading">
    <PanelHeader
      title="Session proposals"
      titleId="case-session-proposals-heading"
      actions={canPropose && !open ? <Link className={buttonVariants({ variant: "secondary" })} href={proposeSessionHref(item.id, returnTo)}>Propose session</Link> : undefined}
    />
    {proposals.length ? <ul className="divide-y divide-border">
      {proposals.map((proposal) => <li key={proposal.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-4 sm:px-5">
        <div className="min-w-0 flex-1 text-sm">
          <p className="font-semibold text-ink">{purposeLabel(proposal.purpose)} · {proposalStateLabel(proposal.state)}</p>
          <ul className="mt-1 grid gap-0.5">
            {proposal.options.map((option) => <li key={option.id} className={option.id === proposal.accepted_option_id ? "font-semibold text-ink" : "text-muted"}>
              {formatCounselingDateTime(option.starts_at)} · {counselingDeliveryModeLabel(option.delivery_mode)}{option.id === proposal.accepted_option_id ? " · Accepted" : ""}
            </li>)}
          </ul>
          {proposal.appointment ? <p className="mt-1">Appointment <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`/portal/appointments/${proposal.appointment.id}`, returnTo)}>{proposal.appointment.reference_code}</Link> · {appointmentStatusLabel(proposal.appointment.status)}</p> : null}
          {proposal.call_slip ? <p className="mt-1">Call Slip <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`/portal/call-slips/${proposal.call_slip.id}`, returnTo)}>{callSlipStateLabels[proposal.call_slip.state] ?? proposal.call_slip.state}</Link></p>
            : proposal.call_slip_requested && proposal.state === "PENDING" ? <p className="mt-1 text-muted">Call Slip to issue after an In person time is accepted</p> : null}
          <p className="mt-1 text-muted">
            Proposed by {proposal.proposed_by.display_name} · {formatCounselingDateTime(proposal.created_at)}
            {proposal.state === "PENDING" ? ` · Open until ${formatCounselingDateTime(proposal.expires_at)}` : proposal.decided_at ? ` · ${proposalStateLabel(proposal.state)} ${formatCounselingDateTime(proposal.decided_at)}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {confirmed && proposal.can_issue_call_slip && proposal.appointment ? <Link
            className={buttonVariants({ variant: proposal.call_slip_requested ? "primary" : "secondary" })}
            href={caseCallSlipHref({ studentId: proposal.student.id, caseId: item.id, appointmentId: proposal.appointment.id, reportAt: proposal.appointment.starts_at, returnTo })}
          >Issue Call Slip</Link> : null}
          {proposal.can_withdraw ? <Button variant="secondary" disabled={!confirmed} aria-label={`Withdraw the proposal sent ${formatCounselingDateTime(proposal.created_at)}`} onClick={() => setWithdrawing(proposal)}>Withdraw</Button> : null}
        </div>
      </li>)}
    </ul> : <PanelMessage>No sessions have been proposed in this case.</PanelMessage>}
    <WithdrawProposalDialog proposal={withdrawing} studentName={item.student.display_name} onClose={() => setWithdrawing(null)} onChanged={onChanged} onStale={onStale} />
  </Panel>;
}

function WithdrawProposalDialog({ proposal, studentName, onClose, onChanged, onStale }: {
  proposal: SessionProposalStaffResponse | null;
  studentName: string;
  onClose: () => void;
  onChanged: (message: string) => void;
  onStale: () => void;
}) {
  const mutation = useCounselingWithdrawSessionProposal({ mutation: { retry: false } });
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  function close() { setError(null); setUncertain(false); onClose(); }
  async function withdraw() {
    if (!proposal || mutation.isPending || uncertain) return;
    setError(null);
    try {
      await mutation.mutateAsync({ proposalId: proposal.id, data: { expected_version: proposal.version } });
      close();
      onChanged("Proposal withdrawn.");
    } catch (caught) {
      if (isStaleProposalError(caught)) { close(); onStale(); return; }
      const unknown = isUncertainProposalResult(caught);
      setUncertain(unknown);
      setError(unknown ? "Couldn't confirm whether the proposal was withdrawn. Close this and check the case." : proposalErrorMessage(caught, "The proposal couldn't be withdrawn. Try again."));
    }
  }
  return <ConsequentialActionDialog
    open={proposal !== null}
    title="Withdraw this session proposal?"
    confirmLabel="Withdraw proposal"
    pendingLabel="Withdrawing…"
    variant="danger"
    pending={mutation.isPending}
    confirmDisabled={uncertain}
    error={error}
    onOpenChange={(next) => { if (!next) close(); }}
    onConfirm={() => void withdraw()}
    onCloseAutoFocus={(event) => { event.preventDefault(); focusHeading("case-session-proposals-heading"); }}
  >
    <p>{studentName} can no longer accept these times. Nothing was booked from this proposal.</p>
  </ConsequentialActionDialog>;
}

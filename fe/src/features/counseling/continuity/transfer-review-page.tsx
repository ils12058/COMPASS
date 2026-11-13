"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Panel, PanelBody, PanelHeader, PanelSection, RecordSummary } from "@/components/ui/panel";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { withWorkflowReturn, portalReturnHref, workflowBackLabel } from "@/features/portal/workflow-navigation";
import { CounselingPageHeading, CounselingQueryError, CounselingUnavailable, EncounterDetailSkeleton, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import {
  useCounselingGetCaseTransfer,
  useCounselingSubmitCaseTransfer, useCounselingAuthorizeCaseTransfer,
  useCounselingAcceptCaseTransfer, useCounselingDeclineCaseTransfer, useCounselingCancelCaseTransfer,
  getCounselingGetCaseQueryKey, getCounselingListMyCasesQueryKey,
} from "@/lib/api/generated/counseling/counseling";
import { CaseArrangementDecisionReason, type CaseTransferDetailResponse } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import { TransferHandoffSection } from "./transfer-handoff-section";
import { arrangementLabel, authorizationLabel, continuityError, continuityReasonLabels, continuityStale, decisionReasonLabels, enumChoice, taskDispositionLabels, appointmentDispositionLabels, transferHref, transferPrepareHref } from "./continuity-presentation";

type Decision = "submit" | "authorize" | "accept" | "decline" | "cancel";
const actionLabels: Record<Decision, string> = { submit: "Submit transfer", authorize: "Authorize transfer", accept: "Accept transfer", decline: "Decline transfer", cancel: "Cancel transfer" };
const pendingLabels: Record<Decision, string> = { submit: "Submitting…", authorize: "Authorizing…", accept: "Accepting…", decline: "Declining…", cancel: "Cancelling…" };

function TransferReview({ item, confirmed, onChanged, onStale, here }: {
  item: CaseTransferDetailResponse; confirmed: boolean; onChanged: () => Promise<unknown>;
  onStale: (message: string) => void; here: string;
}) {
  const reopening = item.purpose === "REOPEN";
  const labels = { ...actionLabels, accept: reopening ? "Accept and reopen case" : actionLabels.accept };
  const submit = useCounselingSubmitCaseTransfer({ mutation: { retry: false } });
  const authorize = useCounselingAuthorizeCaseTransfer({ mutation: { retry: false } });
  const accept = useCounselingAcceptCaseTransfer({ mutation: { retry: false } });
  const decline = useCounselingDeclineCaseTransfer({ mutation: { retry: false } });
  const cancel = useCounselingCancelCaseTransfer({ mutation: { retry: false } });
  const pending = submit.isPending || authorize.isPending || accept.isPending || decline.isPending || cancel.isPending;
  const [decision, setDecision] = useState<Decision | null>(null);
  const [version, setVersion] = useState(item.version);
  const [reason, setReason] = useState<CaseArrangementDecisionReason | "">("");
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState<CaseTransferDetailResponse | null>(null);
  const openedVersion = useRef(item.version);
  useEffect(() => {
    if (openedVersion.current !== item.version) {
      openedVersion.current = item.version;
      if (decision && !pending && !completed) {
        onStale("This arrangement changed. Review the latest details before acting.");
      }
    }
  }, [item.version, decision, pending, completed, onStale]);
  const stale = decision !== null && version !== item.version && !completed;

  function start(action: Decision) { setVersion(item.version); setDecision(action); setReason(""); setError(null); setCompleted(null); }
  async function confirm() {
    if (!decision || pending || stale || !confirmed) return;
    try {
      setError(null);
      const data = { expected_version: version };
      const response = decision === "submit" ? await submit.mutateAsync({ transferId: item.id, data })
        : decision === "authorize" ? await authorize.mutateAsync({ transferId: item.id, data })
        : decision === "accept" ? await accept.mutateAsync({ transferId: item.id, data })
        : decision === "decline" && reason ? await decline.mutateAsync({ transferId: item.id, data: { ...data, reason } })
        : decision === "cancel" && reason ? await cancel.mutateAsync({ transferId: item.id, data: { ...data, reason } }) : null;
      if (!response) return;
      setCompleted(response.data);
      await onChanged();
    } catch (caught) {
      const message = continuityError(caught, "This decision couldn't be completed. Review the arrangement and try again.");
      if (continuityStale(caught)) { setDecision(null); onStale(message); await onChanged(); }
      else setError(message);
    }
  }
  const needsReason = decision === "decline" || decision === "cancel";
  return <>
    <Panel aria-labelledby="transfer-review-heading">
      <RecordSummary title={item.reference_code} titleId="transfer-review-heading" status={arrangementLabel(item)} facts={[
        { label: "Case", value: item.case.reference_code }, { label: "Case status", value: item.case.status === "CLOSED" ? "Closed" : "Active" }, { label: "Student", value: item.case.student.display_name },
        { label: "Primary counselor", value: item.case.primary_counselor.display_name },
        { label: "Receiving counselor", value: item.receiving_counselor.display_name },
        { label: "Prepared by", value: item.prepared_by.display_name }, { label: "Reason", value: continuityReasonLabels[item.reason] },
        { label: "Review until", value: item.review_expires_at ? formatCounselingDateTime(item.review_expires_at) : "After authorization" },
      ]} />
      {item.authorization_route ? <PanelSection title="Authorization" titleId="transfer-authority-heading"><p className="text-sm">{authorizationLabel(item.authorization_route)}</p>{item.authorized_by ? <p className="mt-1 text-sm text-muted">{item.authorized_by.display_name} · {item.authorized_at ? formatCounselingDateTime(item.authorized_at) : ""}</p> : null}</PanelSection> : null}
      {item.tasks.length || item.appointments.length ? <>
        <PanelSection title="Pending actions" titleId="review-task-plan-heading">
          {item.tasks.length ? <ul className="divide-y divide-border">{item.tasks.map((task, index) => <li key={task.task_id} className="py-3 first:pt-0 text-sm">
            <p className="font-semibold">{task.title ?? `Counseling action ${index + 1}`}</p><p className="mt-1">{taskDispositionLabels[task.disposition]} · {task.assignee.display_name}</p><p className="mt-1 text-muted">Due {formatCounselingDateTime(task.due_at)}{task.successor_due_at ? ` · New action due ${formatCounselingDateTime(task.successor_due_at)}` : ""}</p>
            {task.record_accessible ? <Link className="mt-1 inline-block font-semibold text-brand underline" href={withWorkflowReturn(`/portal/follow-ups/${task.task_id}`, here)}>Open action</Link> : null}
          </li>)}</ul> : <p className="text-sm text-muted">No pending case actions.</p>}
        </PanelSection>
        <PanelSection title="Appointments" titleId="review-appointment-plan-heading">
          {item.appointments.length ? <ul className="divide-y divide-border">{item.appointments.map(appointment => <li key={appointment.link_id} className="py-3 first:pt-0 text-sm"><p className="font-semibold">{appointment.reference_code}</p><p className="mt-1">{appointmentDispositionLabels[appointment.disposition]}</p><p className="mt-1 text-muted">{formatCounselingDateTime(appointment.starts_at)} · {appointment.provider.display_name}</p>{appointment.record_accessible ? <Link className="mt-1 inline-block font-semibold text-brand underline" href={withWorkflowReturn(`/portal/appointments/${appointment.appointment_id}`, here)}>Open Appointment actions</Link> : null}</li>)}</ul> : <p className="text-sm text-muted">No upcoming linked appointments.</p>}
        </PanelSection>
      </> : null}
      <PanelSection title="Student communication" titleId="review-communication-heading"><p className="text-sm">{item.student_communication === "YES" ? `Informed ${item.student_informed_at ? formatCounselingDateTime(item.student_informed_at) : ""}` : item.student_communication === "DEFERRED" ? "Informing deferred" : "Not informed"} · Recorded by {item.communication_recorded_by.display_name}</p>{item.communication_responsible ? <p className="mt-1 text-sm text-muted">Communication action: {item.communication_responsible.display_name}</p> : null}</PanelSection>
    </Panel>
    {!reopening ? <TransferHandoffSection item={item} here={here} confirmed={confirmed} onChanged={onChanged} onStale={onStale} /> : <Notice className="mt-5">This is a Closed case for the same episode. Acceptance reopens it with reason “Further support needed”. After-closure actions keep their existing owners.</Notice>}
    {item.needs_new_arrangement ? <Notice role="status" className="mt-5" tone="warning">{item.decision_reason ? decisionReasonLabels[item.decision_reason] : "The review ended."} The owner is unchanged; another arrangement is needed.</Notice> : null}
    {item.state === "ACCEPTED" ? <Notice role="status" className="mt-5">The case is now the responsibility of {item.receiving_counselor.display_name}.{reopening ? " The case is Active again; previous closure history and action owners are retained." : " Acceptance does not complete any action or endorse a handoff."}</Notice> : null}
    {item.can_edit || item.can_open_case || item.can_submit || item.can_authorize || item.can_accept || item.can_decline || item.can_cancel ? <Panel className="mt-5" aria-labelledby="transfer-decisions-heading"><PanelHeader title="Next step" titleId="transfer-decisions-heading" /><PanelBody>
      <div className="flex flex-wrap gap-3">
        {item.can_edit ? <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`${transferPrepareHref(item.case.id)}?edit=${encodeURIComponent(item.id)}${reopening ? "&purpose=REOPEN" : ""}`, here)}>Edit transfer plan</Link> : null}
        {([['submit', item.can_submit], ['authorize', item.can_authorize], ['accept', item.can_accept], ['decline', item.can_decline], ['cancel', item.can_cancel]] as const).map(([action, available]) => available ? <Button key={action} disabled={!confirmed} variant={action === "cancel" || action === "decline" ? "secondary" : "primary"} onClick={() => start(action)}>{labels[action]}</Button> : null)}
        {item.can_open_case ? <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`/portal/counseling/cases/${item.case.id}`, here)}>Open case {item.case.reference_code}</Link> : null}
      </div>
    </PanelBody></Panel> : null}
    <Panel className="mt-5" aria-labelledby="transfer-history-heading"><PanelHeader title="Continuity history" titleId="transfer-history-heading" /><ol className="divide-y divide-border">{item.history.map(event => <li key={event.id} className="px-4 py-3 text-sm sm:px-5"><p className="capitalize">{event.kind} · {event.actor.display_name}</p><p className="mt-1 text-xs text-muted">{formatCounselingDateTime(event.occurred_at)}{event.authorization_route ? ` · ${authorizationLabel(event.authorization_route)}` : ""}</p></li>)}</ol></Panel>
    <ConsequentialActionDialog open={Boolean(decision) && !stale} title={`${decision ? labels[decision] : "Review transfer"}?`} confirmLabel={decision ? labels[decision] : "Review transfer"} pendingLabel={decision ? pendingLabels[decision] : "Saving…"} pending={pending} confirmDisabled={!confirmed || (needsReason && !reason)} error={error} variant={needsReason ? "danger" : "primary"} onOpenChange={open => { if (!open) { setDecision(null); setCompleted(null); } }} onConfirm={() => void confirm()} onCloseAutoFocus={event => { event.preventDefault(); focusHeading("transfer-review-heading"); }} completed={completed ? { title: `${decision ? labels[decision] : "Transfer"} completed`, children: <p>{arrangementLabel(completed)}. {completed.state === "ACCEPTED" ? `${completed.receiving_counselor.display_name} is now the primary Counselor.` : "Primary responsibility stays unchanged until acceptance."}</p> } : null} choices={needsReason ? <div className="grid gap-1"><Label htmlFor="transfer-decision-reason">Reason for this decision</Label><Select id="transfer-decision-reason" value={reason} onChange={event => setReason(enumChoice(Object.values(CaseArrangementDecisionReason), event.target.value) ?? "")}><option value="">Choose a reason</option>{Object.values(CaseArrangementDecisionReason).filter(value => value !== "REVIEW_WINDOW_ENDED").map(value => <option key={value} value={value}>{decisionReasonLabels[value]}</option>)}</Select></div> : undefined}>
      <p>{item.reference_code} · {item.case.reference_code} · {item.receiving_counselor.display_name}</p>
      <p>{decision === "accept" ? reopening ? "Acceptance immediately changes primary responsibility and reopens this Closed case for the same episode. After-closure actions keep their existing owners. Historical sources and message audiences keep their own access rules." : "Acceptance immediately changes primary responsibility and applies the reviewed task dispositions. Historical sources and message audiences keep their own access rules." : decision === "authorize" ? "This authorizes a seven-day receiving-Counselor review. The case stays with its current owner until acceptance." : decision === "submit" ? "The next actor receives this scoped plan for review. Changes invalidate prior authorization." : "This ends the arrangement and leaves the case with its current owner. Another arrangement will be needed."}</p>
    </ConsequentialActionDialog>
  </>;
}

export function TransferReviewPage({ transferId }: { transferId: string }) {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const client = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const allowed = ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"].includes(user.role) && user.capabilities.includes("counseling.continuity.view");
  const query = useCounselingGetCaseTransfer(transferId, { query: { enabled: allowed, retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: "always", refetchOnReconnect: "always", refetchInterval: 15_000 } });
  const item = query.data?.data;
  const back = portalReturnHref(params.get("return_to"), item?.can_open_case ? `/portal/counseling/cases/${item.case.id}` : "/portal/work");
  const here = withWorkflowReturn(transferHref(transferId), back);
  const refetch = query.refetch;
  useEffect(() => {
    if (!item?.review_expires_at || item.state !== "AUTHORIZED") return;
    const delay = Math.max(1, new Date(item.review_expires_at).getTime() - Date.now());
    const timer = window.setTimeout(() => { void refetch(); }, Math.min(delay, 2_147_483_647));
    return () => window.clearTimeout(timer);
  }, [item?.review_expires_at, item?.state, refetch]);
  if (!allowed) return <CounselingUnavailable title="Transfer review" />;
  const heading = <CounselingPageHeading title="Transfer review" back={<Link href={back} className={pageBackLinkClass}>{workflowBackLabel(back)}</Link>} />;
  if (query.isPending) return <>{heading}<EncounterDetailSkeleton /></>;
  if (query.isError || !item) return <>{heading}<CounselingQueryError message={continuityError(query.error, "Couldn't confirm this transfer review. Confidential information has been hidden.")} onRetry={() => void query.refetch()} /></>;
  async function changed() {
    await Promise.all([query.refetch(), client.invalidateQueries({ queryKey: getCounselingGetCaseQueryKey(item!.case.id) }), client.invalidateQueries({ queryKey: getCounselingListMyCasesQueryKey() }), client.invalidateQueries({ queryKey: ["/api/v1/work"] })]);
  }
  return <>{heading}{notice ? <Notice role="status" className="mb-5" tone="warning">{notice}</Notice> : null}<TransferReview key={`${user.id}:${transferId}`} item={item} here={here} confirmed={!query.isError} onChanged={changed} onStale={setNotice} /></>;
}

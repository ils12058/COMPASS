"use client";

import { useState } from "react";
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
  useCounselingGetCaseCoverage, useCounselingSubmitCaseCoverage, useCounselingAuthorizeCaseCoverage,
  useCounselingAcceptCaseCoverage, useCounselingDeclineCaseCoverage, useCounselingCancelCaseCoverage, useCounselingRevokeCaseCoverage,
  getCounselingGetCaseQueryKey,
} from "@/lib/api/generated/counseling/counseling";
import { CaseArrangementDecisionReason, type CaseCoverageDetailResponse } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import { authorizationLabel, continuityError, continuityReasonLabels, continuityStale, coverageHref, coveragePrepareHref, coverageStateLabel, decisionReasonLabels, enumChoice, returnPlanLabels } from "./continuity-presentation";

type Decision = "submit" | "authorize" | "accept" | "decline" | "cancel" | "revoke";
const actionLabels: Record<Decision, string> = { submit: "Submit coverage", authorize: "Authorize coverage", accept: "Accept coverage", decline: "Decline coverage", cancel: "Cancel coverage", revoke: "End coverage now" };
const pendingLabels: Record<Decision, string> = { submit: "Submitting…", authorize: "Authorizing…", accept: "Accepting…", decline: "Declining…", cancel: "Cancelling…", revoke: "Ending coverage…" };
const explanations: Record<Decision, string> = {
  submit: "The next actor receives this coverage plan for review. Changing it later needs a fresh review.",
  authorize: "This starts a review of up to seven days by the covering Counselor. Nothing changes until they accept.",
  accept: "You will cover the selected actions during the approved period. The primary Counselor stays responsible for the case.",
  decline: "The primary Counselor keeps all work. Another arrangement will be needed.",
  cancel: "This ends the arrangement before it takes effect. The primary Counselor keeps all work.",
  revoke: "Coverage ends now. Unfinished delegated actions return to the primary Counselor; nothing is completed or cancelled.",
};
const needsReason = (decision: Decision | null) => decision === "decline" || decision === "cancel" || decision === "revoke";

function CoverageReview({ item, onChanged, onStale, here }: { item: CaseCoverageDetailResponse; onChanged: () => Promise<unknown>; onStale: (message: string) => void; here: string }) {
  const submit = useCounselingSubmitCaseCoverage({ mutation: { retry: false } });
  const authorize = useCounselingAuthorizeCaseCoverage({ mutation: { retry: false } });
  const accept = useCounselingAcceptCaseCoverage({ mutation: { retry: false } });
  const decline = useCounselingDeclineCaseCoverage({ mutation: { retry: false } });
  const cancel = useCounselingCancelCaseCoverage({ mutation: { retry: false } });
  const revoke = useCounselingRevokeCaseCoverage({ mutation: { retry: false } });
  const pending = [submit, authorize, accept, decline, cancel, revoke].some(mutation => mutation.isPending);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [version, setVersion] = useState(item.version);
  const [reason, setReason] = useState<CaseArrangementDecisionReason | "">("");
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState<CaseCoverageDetailResponse | null>(null);

  function start(action: Decision) { setVersion(item.version); setDecision(action); setReason(""); setError(null); setCompleted(null); }
  async function confirm() {
    if (!decision || pending) return;
    try {
      setError(null);
      const data = { expected_version: version };
      const coverageId = item.id;
      const response = decision === "submit" ? await submit.mutateAsync({ coverageId, data })
        : decision === "authorize" ? await authorize.mutateAsync({ coverageId, data })
        : decision === "accept" ? await accept.mutateAsync({ coverageId, data })
        : !reason ? null
        : decision === "decline" ? await decline.mutateAsync({ coverageId, data: { ...data, reason } })
        : decision === "cancel" ? await cancel.mutateAsync({ coverageId, data: { ...data, reason } })
        : await revoke.mutateAsync({ coverageId, data: { ...data, reason } });
      if (!response) return;
      setCompleted(response.data);
      await onChanged();
    } catch (caught) {
      const message = continuityError(caught, "This decision couldn't be completed. Review the coverage and try again.");
      if (continuityStale(caught)) { setDecision(null); onStale(message); await onChanged(); }
      else setError(message);
    }
  }
  const actions = ([["submit", item.can_submit], ["authorize", item.can_authorize], ["accept", item.can_accept], ["decline", item.can_decline], ["cancel", item.can_cancel], ["revoke", item.can_revoke]] as const).filter(([, available]) => available);
  return <>
    <Panel aria-labelledby="coverage-review-heading">
      <RecordSummary title={item.reference_code} titleId="coverage-review-heading" status={coverageStateLabel(item, formatCounselingDateTime)} facts={[
        { label: "Case", value: item.case.reference_code }, { label: "Student", value: item.case.student.display_name },
        { label: "Primary counselor", value: `${item.primary_counselor.display_name} (stays responsible)` },
        { label: "Covering counselor", value: item.receiving_counselor.display_name },
        { label: "Period", value: `${formatCounselingDateTime(item.starts_at)} – ${formatCounselingDateTime(item.expires_at)}` },
        { label: "Prepared by", value: item.prepared_by.display_name }, { label: "Reason", value: continuityReasonLabels[item.reason] },
        { label: "Review until", value: item.review_expires_at ? formatCounselingDateTime(item.review_expires_at) : "After authorization" },
      ]} />
      {item.authorization_route ? <PanelSection title="Authorization" titleId="coverage-authority-heading"><p className="text-sm">{authorizationLabel(item.authorization_route)}</p>{item.authorized_by ? <p className="mt-1 text-sm text-muted">{item.authorized_by.display_name} · {item.authorized_at ? formatCounselingDateTime(item.authorized_at) : ""}</p> : null}</PanelSection> : null}
      <PanelSection title="Delegated actions" titleId="coverage-task-plan-heading">
        {item.tasks.length ? <ul className="divide-y divide-border">{item.tasks.map((task, index) => <li key={task.task_id} className="py-3 first:pt-0 text-sm">
          <p className="font-semibold">{task.title ?? `Counseling action ${index + 1}`}</p>
          <p className="mt-1">{returnPlanLabels[task.return_plan]} · {task.assigned_counselor.display_name}</p>
          <p className="mt-1 text-muted">Due {formatCounselingDateTime(task.due_at)}{task.returned_at ? ` · Returned ${formatCounselingDateTime(task.returned_at)}${task.returned_by ? ` by ${task.returned_by.display_name}` : ""}` : ""}</p>
          {task.recovery_required ? <p className="mt-1 text-warning">The primary Counselor can no longer take this action back. It needs authorized recovery.</p> : null}
          {task.record_accessible ? <Link className="mt-1 inline-block font-semibold text-brand underline" href={withWorkflowReturn(`/portal/follow-ups/${task.task_id}`, here)}>Open action</Link> : null}
        </li>)}</ul> : <p className="text-sm text-muted">No actions are delegated.</p>}
      </PanelSection>
      <PanelSection title="Student communication" titleId="coverage-communication-review-heading"><p className="text-sm">{item.student_communication === "YES" ? `Informed ${item.student_informed_at ? formatCounselingDateTime(item.student_informed_at) : ""}` : item.student_communication === "DEFERRED" ? "Informing deferred" : "Not informed"} · Recorded by {item.communication_recorded_by.display_name}</p>{item.communication_responsible ? <p className="mt-1 text-sm text-muted">Communication action: {item.communication_responsible.display_name}</p> : null}</PanelSection>
    </Panel>
    {item.needs_new_arrangement ? <Notice role="status" className="mt-5" tone="warning">{item.decision_reason ? decisionReasonLabels[item.decision_reason] : "The review ended."} The primary Counselor keeps the work; another arrangement is needed.</Notice> : null}
    {item.can_edit || item.can_open_case || actions.length ? <Panel className="mt-5" aria-labelledby="coverage-decisions-heading"><PanelHeader title="Next step" titleId="coverage-decisions-heading" /><PanelBody>
      <div className="flex flex-wrap gap-3">
        {item.can_edit ? <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`${coveragePrepareHref(item.case.id)}?edit=${encodeURIComponent(item.id)}`, here)}>Edit coverage plan</Link> : null}
        {actions.map(([action]) => <Button key={action} variant={needsReason(action) ? "secondary" : "primary"} onClick={() => start(action)}>{actionLabels[action]}</Button>)}
        {item.can_open_case ? <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`/portal/counseling/cases/${item.case.id}`, here)}>Open case {item.case.reference_code}</Link> : null}
      </div>
    </PanelBody></Panel> : null}
    <Panel className="mt-5" aria-labelledby="coverage-history-heading"><PanelHeader title="Coverage history" titleId="coverage-history-heading" /><ol className="divide-y divide-border">{item.history.map(event => <li key={event.id} className="px-4 py-3 text-sm sm:px-5"><p className="capitalize">{event.kind} · {event.actor.display_name}</p><p className="mt-1 text-xs text-muted">{formatCounselingDateTime(event.occurred_at)}{event.authorization_route ? ` · ${authorizationLabel(event.authorization_route)}` : ""}</p></li>)}</ol></Panel>
    <ConsequentialActionDialog open={Boolean(decision)} title={`${decision ? actionLabels[decision] : "Review coverage"}?`} confirmLabel={decision ? actionLabels[decision] : "Confirm"} pendingLabel={decision ? pendingLabels[decision] : "Saving…"} pending={pending} confirmDisabled={needsReason(decision) && !reason} error={error} variant={needsReason(decision) ? "danger" : "primary"} onOpenChange={open => { if (!open) { setDecision(null); setCompleted(null); } }} onConfirm={() => void confirm()} onCloseAutoFocus={event => { event.preventDefault(); focusHeading("coverage-review-heading"); }} completed={completed ? { title: `${decision ? actionLabels[decision] : "Coverage"} completed`, children: <p>{coverageStateLabel(completed, formatCounselingDateTime)}.</p> } : null} choices={needsReason(decision) ? <div className="grid gap-1"><Label htmlFor="coverage-decision-reason">Reason for this decision</Label><Select id="coverage-decision-reason" value={reason} onChange={event => setReason(enumChoice(Object.values(CaseArrangementDecisionReason), event.target.value) ?? "")}><option value="">Choose a reason</option>{Object.values(CaseArrangementDecisionReason).filter(value => value !== "REVIEW_WINDOW_ENDED").map(value => <option key={value} value={value}>{decisionReasonLabels[value]}</option>)}</Select></div> : undefined}>
      <p>{item.reference_code} · {item.case.reference_code} · {item.receiving_counselor.display_name}</p>
      <p>{decision ? explanations[decision] : ""}</p>
    </ConsequentialActionDialog>
  </>;
}

export function CoverageReviewPage({ coverageId }: { coverageId: string }) {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const client = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const allowed = ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"].includes(user.role) && user.capabilities.includes("counseling.continuity.view");
  const query = useCounselingGetCaseCoverage(coverageId, { query: { enabled: allowed, retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: "always", refetchInterval: 15_000 } });
  const item = query.data?.data;
  const back = portalReturnHref(params.get("return_to"), item?.can_open_case ? `/portal/counseling/cases/${item.case.id}` : "/portal/work");
  const here = withWorkflowReturn(coverageHref(coverageId), back);
  if (!allowed) return <CounselingUnavailable title="Coverage review" />;
  const heading = <CounselingPageHeading title="Coverage review" back={<Link href={back} className={pageBackLinkClass}>{workflowBackLabel(back)}</Link>} />;
  if (query.isPending) return <>{heading}<EncounterDetailSkeleton /></>;
  if (query.isError || !item) return <>{heading}<CounselingQueryError message={continuityError(query.error, "Couldn't confirm this coverage. Confidential information has been hidden.")} onRetry={() => void query.refetch()} /></>;
  async function changed() {
    await Promise.all([query.refetch(), client.invalidateQueries({ queryKey: getCounselingGetCaseQueryKey(item!.case.id) }), client.invalidateQueries({ queryKey: ["/api/v1/work"] })]);
  }
  return <>{heading}{notice ? <Notice role="status" className="mb-5" tone="warning">{notice}</Notice> : null}<CoverageReview key={`${user.id}:${coverageId}`} item={item} here={here} onChanged={changed} onStale={setNotice} /></>;
}

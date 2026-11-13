"use client";

import { useState, type FormEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelBody, PanelSection, PanelFooter } from "@/components/ui/panel";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { CounselingPageHeading, CounselingQueryError, CounselingUnavailable, EncounterDetailSkeleton, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { withWorkflowReturn, portalReturnHref } from "@/features/portal/workflow-navigation";
import { invalidateFollowups } from "@/features/guidance-followups/followups-data";
import { coverageHref, transferHref, enumChoice } from "@/features/counseling/continuity/continuity-presentation";
import { getCounselingListMyCasesQueryKey, useCounselingGetCaseClosureContext, useCounselingCloseCase, useCounselingReopenCase } from "@/lib/api/generated/counseling/counseling";
import { CaseClosureReason, CaseClosureOutcome, CaseReopenReason, type CaseClosureContextResponse, type CounselingCaseDetailResponse } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import { AfterClosureTask } from "@/features/guidance-followups/after-closure-action";
import { useProtectedCase } from "./use-protected-case";
import { caseHref, openCaseHref } from "./case-presentation";
import { closureReasonLabels, closureReasonOptions, closureOutcomeLabels, reopenReasonLabels, closureBlockerLabels, closureSummary, closureNoteError, closureError, closureRequiresReview } from "./closure-presentation";

const textLink = "font-semibold text-brand underline underline-offset-4";

function OutstandingReview({ context, item, here, refresh, onTaskSaved }: { context: CaseClosureContextResponse; item: CounselingCaseDetailResponse; here: string; refresh: () => Promise<unknown>; onTaskSaved: (next: CounselingCaseDetailResponse) => Promise<unknown> }) {
  return <>
    <PanelHeader title="1. Outstanding work" titleId="close-outstanding-heading" actions={<Button type="button" variant="secondary" onClick={() => void refresh()}>Refresh work</Button>} />
    <PanelBody>
      {context.blockers.length ? <Notice tone="warning"><p>Resolve the blocking work before closing:</p><ul className="mt-2 list-inside list-disc">{context.blockers.map(kind => <li key={kind}>{closureBlockerLabels[kind]}</li>)}</ul></Notice> : <p className="text-sm">No outstanding work blocks closure.</p>}
      <p className="mt-3 text-sm text-muted">Closure does not complete, cancel or unlink work. Open each workflow to handle it, or designate an administrative action to remain after closure.</p>
    </PanelBody>
    <PanelSection title="Transfers" titleId="closure-transfers-heading"><ul className="space-y-2 text-sm">{context.transfers.map(transfer => <li key={transfer.id}><Link className={textLink} href={withWorkflowReturn(transferHref(transfer.id), here)}>{transfer.reference_code} · Review or cancel transfer</Link></li>)}</ul>{!context.transfers.length ? <p className="text-sm text-muted">No pending transfer.</p> : null}</PanelSection>
    <PanelSection title="Coverage and delegated actions" titleId="closure-coverages-heading"><ul className="space-y-2 text-sm">{context.coverages.map(coverage => <li key={coverage.id}><Link className={textLink} href={withWorkflowReturn(coverageHref(coverage.id), here)}>{coverage.reference_code} · Review or end coverage</Link></li>)}{context.delegated_task_ids.map(id => <li key={id}><Link className={textLink} href={withWorkflowReturn(`/portal/follow-ups/${id}`, here)}>Review delegated action</Link></li>)}</ul>{!context.coverages.length && !context.delegated_task_ids.length ? <p className="text-sm text-muted">No coverage or delegated action awaits resolution.</p> : null}</PanelSection>
    <PanelSection title="Upcoming Appointments" titleId="closure-appointments-heading"><ul className="space-y-2 text-sm">{context.appointments.map(appointment => <li key={appointment.id}><Link className={textLink} href={withWorkflowReturn(`/portal/appointments/${appointment.id}`, here)}>{appointment.reference_code} · Open Appointment actions</Link><p className="mt-1">{formatCounselingDateTime(appointment.starts_at)}</p></li>)}</ul>{context.appointments.length ? <Link className={`${textLink} mt-3 inline-block text-sm`} href={withWorkflowReturn(caseHref(item.id), here)}>Review case links to unlink an Appointment</Link> : <p className="text-sm text-muted">No upcoming linked Appointment.</p>}</PanelSection>
    <PanelSection title="Pending actions" titleId="closure-tasks-heading"><ul className="divide-y divide-border">{context.tasks.map(task => <AfterClosureTask key={task.id} task={task} item={item} context={context} here={here} onSaved={onTaskSaved} />)}</ul>{!context.tasks.length ? <p className="text-sm text-muted">No pending case action.</p> : null}</PanelSection>
  </>;
}

function ClosureForm({ item, context, reopening, here, back, refresh }: { item: CounselingCaseDetailResponse; context?: CaseClosureContextResponse; reopening: boolean; here: string; back: string; refresh: () => Promise<unknown> }) {
  const router = useRouter();
  const client = useQueryClient();
  const close = useCounselingCloseCase({ mutation: { retry: false } });
  const reopen = useCounselingReopenCase({ mutation: { retry: false } });
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [reason, setReason] = useState<CaseClosureReason>("PLANNED_SUPPORT_CONCLUDED");
  const [outcome, setOutcome] = useState<CaseClosureOutcome>("NOT_ASSESSED");
  const [reopenReason, setReopenReason] = useState<CaseReopenReason>("FURTHER_SUPPORT_NEEDED");
  const [note, setNote] = useState("");
  const [version, setVersion] = useState(item.version);
  const [error, setError] = useState<string | null>(null);
  const [reviewNotice, setReviewNotice] = useState<string | null>(null);
  const [completed, setCompleted] = useState<CounselingCaseDetailResponse | null>(null);
  const [dirty, setDirty] = useState(false);
  const pending = close.isPending || reopen.isPending;
  const stale = item.version !== version || (context && context.version !== version);
  const blocked = !reopening && Boolean(context?.blockers.length);
  const canAct = reopening ? item.can_reopen : item.status === "ACTIVE" && item.can_manage;
  useUnsavedChangesGuard({ dirty: dirty && !completed, message: "Leave this case action and discard unsaved details?" });

  async function confirm() {
    if (pending || stale || blocked || !canAct) return;
    setError(null);
    try {
      const response = reopening ? await reopen.mutateAsync({ caseId: item.id, data: { expected_version: version, reason: reopenReason } }) : await close.mutateAsync({ caseId: item.id, data: { expected_version: version, reason, outcome, note: note || null } });
      setCompleted(response.data);
      setDirty(false);
      setNote("");
      await Promise.all([client.invalidateQueries({ queryKey: getCounselingListMyCasesQueryKey() }), invalidateFollowups(client)]);
    } catch (caught) {
      if (closureRequiresReview(caught)) { setStep(1); setReviewNotice(closureError(caught)); await refresh(); focusHeading("closure-form-heading"); }
      else setError(closureError(caught));
    }
  }
  function reviewReason(event: FormEvent) {
    event.preventDefault();
    const invalid = reopening ? null : closureNoteError(reason, note);
    if (invalid) { setError(invalid); return; }
    setError(null);
    setStep(3);
  }
  const currentClosure = item.closure;
  return <>
    {reviewNotice ? <Notice role="status" tone="warning" className="mb-5">{reviewNotice}</Notice> : null}
    {stale && !completed ? <Notice tone="warning" role="alert" className="mb-5" action={<Button type="button" variant="secondary" onClick={() => { setVersion(item.version); setStep(1); setReviewNotice(null); }}>I have reviewed the latest case</Button>}>The case changed. Your details are kept; review the current case and outstanding work before confirming.</Notice> : null}
    {!canAct && !completed ? <Notice tone="warning" className="mb-5">{reopening ? "Only the eligible current primary Counselor can reopen this Closed case." : "This case cannot be closed by your account now."}</Notice> : null}
    <Panel aria-labelledby="closure-form-heading">
      <PanelHeader title={`${item.reference_code} · ${item.student.display_name}`} titleId="closure-form-heading" description={`Primary counselor: ${item.primary_counselor.display_name}`} />
      {step === 1 ? <>
        {reopening ? <PanelSection title="1. Review the episode" titleId="reopen-review-heading"><p className="text-sm">This reopens the same case for the same episode.</p><p className="mt-2 text-sm">If this is a different concern, open a new case instead.</p><Link className={`${textLink} mt-2 inline-block text-sm`} href={withWorkflowReturn(openCaseHref({ origin: "INTAKE", studentId: item.student.id }), here)}>Open new case for this Student</Link>{currentClosure ? <p className="mt-4 text-sm">Closed {formatCounselingDateTime(currentClosure.closed_at)} · {closureReasonLabels[currentClosure.reason]} · {currentClosure.closed_by.display_name}</p> : null}<p className="mt-3 text-sm text-muted">Closure history, sessions and existing action owners are retained.</p></PanelSection> : context ? <OutstandingReview context={context} item={item} here={here} refresh={refresh} onTaskSaved={async next => { setVersion(next.version); await refresh(); }} /> : null}
        <PanelFooter><Button type="button" disabled={blocked || stale || !canAct || !context && !reopening} onClick={() => { setStep(2); requestAnimationFrame(() => focusHeading("closure-reason-heading")); }}>Next: {reopening ? "reopening reason" : "closure details"}</Button></PanelFooter>
      </> : <form onSubmit={reviewReason} onChange={() => setDirty(true)}>
        <PanelSection title={reopening ? "2. Reopening reason" : "2. Reason and outcome"} titleId="closure-reason-heading">
          {reopening ? <div className="grid gap-1"><Label htmlFor="case-reopen-reason">Reopening reason</Label><Select id="case-reopen-reason" value={reopenReason} onChange={event => { const value = enumChoice(Object.values(CaseReopenReason), event.target.value); if (value) setReopenReason(value); }}>{Object.values(CaseReopenReason).map(value => <option key={value} value={value}>{reopenReasonLabels[value]}</option>)}</Select></div> : <>
            <div className="grid gap-4 sm:grid-cols-2"><div className="grid gap-1"><Label htmlFor="case-close-reason">Closure reason</Label><Select id="case-close-reason" aria-describedby="case-close-reason-help" value={reason} onChange={event => { const value = enumChoice(Object.values(CaseClosureReason), event.target.value); if (value) setReason(value); }}>{Object.values(CaseClosureReason).map(value => <option key={value} value={value}>{closureReasonOptions[value]}</option>)}</Select><p id="case-close-reason-help" className="text-sm text-muted">{closureReasonLabels[reason]}</p></div><div className="grid gap-1"><Label htmlFor="case-close-outcome">Outcome</Label><Select id="case-close-outcome" value={outcome} onChange={event => { const value = enumChoice(Object.values(CaseClosureOutcome), event.target.value); if (value) setOutcome(value); }}>{Object.values(CaseClosureOutcome).map(value => <option key={value} value={value}>{closureOutcomeLabels[value]}</option>)}</Select></div></div>
            <div className="mt-4 grid gap-1"><Label htmlFor="case-close-note">Confidential closure note{reason === "CONTACT_NOT_REESTABLISHED" ? " (required)" : " (optional)"}</Label><Textarea id="case-close-note" rows={5} maxLength={4000} value={note} aria-describedby="case-close-note-help" onChange={event => setNote(event.target.value)} /><p id="case-close-note-help" className="text-sm text-muted">Only the current case owner can read this note. {reason === "CONTACT_NOT_REESTABLISHED" ? "Describe documented contact attempts in at least 20 characters. " : ""}At most 4,000 characters.</p></div>
          </>}
          {error && step !== 3 ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
        </PanelSection>
        <PanelFooter><div className="flex flex-wrap gap-3"><Button type="button" variant="secondary" onClick={() => { setStep(1); requestAnimationFrame(() => focusHeading("closure-form-heading")); }}>Back to review</Button><Button type="submit" disabled={stale || blocked || !canAct}>Review {reopening ? "reopening" : "closure"}</Button></div></PanelFooter>
      </form>}
    </Panel>
    <ConsequentialActionDialog open={step === 3 && (!stale || Boolean(completed))} title={reopening ? "3. Reopen this case?" : "3. Close this case?"} confirmLabel={reopening ? "Reopen case" : "Close case"} pendingLabel={reopening ? "Reopening case…" : "Closing case…"} pending={pending} confirmDisabled={stale || blocked || !canAct} error={error} onConfirm={() => void confirm()} onOpenChange={open => { if (!open) { if (completed) router.push(back); else setStep(2); } }} onCloseAutoFocus={event => { event.preventDefault(); if (!completed) focusHeading("closure-reason-heading"); }} completed={completed ? { title: reopening ? "Case reopened" : "Case closed", children: <p>{reopening ? "The same case is Active again. Previous closure history is retained." : "The case is Closed. Its sessions, links and existing actions are retained."}</p> } : null}>
      <p>{item.reference_code} · {item.student.display_name}</p>
      <p>{reopening ? reopenReasonLabels[reopenReason] : closureSummary(reason, outcome)}</p>
      <p>{reopening ? "If this is a different concern, open a new case instead." : "The case becomes read-only until its eligible current primary Counselor reopens it. Administrative Referral closure remains independent."}</p>
    </ConsequentialActionDialog>
  </>;
}

export function CaseClosurePage({ caseId, reopening = false }: { caseId: string; reopening?: boolean }) {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const pathname = usePathname();
  const back = portalReturnHref(params.get("return_to"), caseHref(caseId));
  const here = `${pathname}${params.size ? `?${params}` : ""}`;
  const access = getCounselingAccess(user);
  const allowed = access.isCounselor && access.canViewAssigned;
  const query = useProtectedCase(caseId, allowed);
  const context = useCounselingGetCaseClosureContext(caseId, { query: { enabled: allowed && !reopening, retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: "always", refetchOnReconnect: "always" } });
  const heading = <CounselingPageHeading title={reopening ? "Reopen case" : "Close case"} back={<Link className={pageBackLinkClass} href={back}>Back to case</Link>} />;
  if (!allowed) return <CounselingUnavailable title={reopening ? "Reopen case" : "Close case"} />;
  if (query.privacy.blocked) return <>{heading}<CounselingQueryError message={closureError(query.failure, "Protected case details have been cleared. Check access again to continue.")} onRetry={() => { query.privacy.resume(); if (!reopening) void context.refetch(); }} /></>;
  if (query.isPending || !reopening && context.isPending) return <>{heading}<EncounterDetailSkeleton /></>;
  if (query.isError || !query.data || !reopening && (context.isError || !context.data)) return <>{heading}<CounselingQueryError message={closureError(query.error ?? context.error, "This case action couldn't be confirmed. Check access and try again.")} onRetry={() => { void query.refetch(); if (!reopening) void context.refetch(); }} /></>;
  async function refresh() { await Promise.all([query.refetch(), !reopening ? context.refetch() : Promise.resolve()]); }
  return <>{heading}<ClosureForm key={`${user.id}:${caseId}:${reopening}`} item={query.data.data} context={context.data?.data} reopening={reopening} here={here} back={back} refresh={refresh} /></>;
}

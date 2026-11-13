"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelSection, PanelFooter } from "@/components/ui/panel";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { CounselorAboutButton } from "@/features/counselor-about/counselor-about-dialog";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { portalReturnHref, withWorkflowReturn, workflowBackLabel } from "@/features/portal/workflow-navigation";
import { CounselingPageHeading, CounselingQueryError, CounselingUnavailable, EncounterDetailSkeleton, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import {
  useCounselingGetCaseCoverageContext, useCounselingGetCaseCoverage,
  useCounselingPrepareCaseCoverage, useCounselingUpdateCaseCoverage,
  getCounselingGetCaseQueryKey,
} from "@/lib/api/generated/counseling/counseling";
import {
  CaseContinuityReason, CaseOfficePreparationReason, CaseStudentCommunication, CaseCommunicationDeferral, CaseCoverageReturnPlan,
  type CaseCoverageContextResponse, type CaseCoverageDetailResponse, type CaseCoveragePrepareRequest,
} from "@/lib/api/generated/model";
import { institutionalDateTimeInputToISO, isoToInstitutionalDateTimeInput } from "@/lib/institutional-time";
import { authorizationLabel, continuityError, continuityReasonLabels, coverageHref, coverageIntervalError, coverageTaskInputs, enumChoice, returnPlanLabels, returnPlanOptionLabels, type CoverageTaskChoice } from "./continuity-presentation";

function CoverageForm({ context, existing, returnTo }: { context: CaseCoverageContextResponse; existing?: CaseCoverageDetailResponse; returnTo: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const create = useCounselingPrepareCaseCoverage({ mutation: { retry: false } });
  const update = useCounselingUpdateCaseCoverage({ mutation: { retry: false } });
  const pending = create.isPending || update.isPending;
  const [receiver, setReceiver] = useState(existing?.receiving_counselor.id ?? "");
  const [reason, setReason] = useState<CaseContinuityReason>(existing?.reason ?? "PLANNED_ABSENCE");
  const [officeReason, setOfficeReason] = useState<CaseOfficePreparationReason | "">(existing?.office_preparation_reason ?? "");
  const [starts, setStarts] = useState(existing ? isoToInstitutionalDateTimeInput(existing.starts_at) ?? "" : "");
  const [ends, setEnds] = useState(existing ? isoToInstitutionalDateTimeInput(existing.expires_at) ?? "" : "");
  const [tasks, setTasks] = useState<Record<string, CoverageTaskChoice>>(() => Object.fromEntries(existing?.tasks.map(task => [task.task_id, { selected: true, plan: task.return_plan }]) ?? []));
  const [communication, setCommunication] = useState<CaseStudentCommunication>(existing?.student_communication ?? "NO");
  const [informedAt, setInformedAt] = useState(existing?.student_informed_at ? isoToInstitutionalDateTimeInput(existing.student_informed_at) ?? "" : "");
  const [deferral, setDeferral] = useState<CaseCommunicationDeferral | "">(existing?.communication_deferral_reason ?? "");
  const [nextAction, setNextAction] = useState("");
  const [nextDue, setNextDue] = useState("");
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useUnsavedChangesGuard({ dirty, message: "Leave this coverage preparation and discard unsaved changes?" });
  const option = context.receiver_options.find(item => item.person.id === receiver);
  const blocked = option?.blocked_reason;
  const existingCommunication = communication === "DEFERRED" && existing?.communication_task_id;

  async function save(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    setError(null);
    const startISO = institutionalDateTimeInputToISO(starts);
    const endISO = institutionalDateTimeInputToISO(ends);
    const intervalError = coverageIntervalError(startISO, endISO);
    if (!receiver || blocked) { setError(blocked ?? "Choose the covering Counselor."); return; }
    if (context.office_prepared && !officeReason) { setError("Explain why the office is preparing this coverage."); return; }
    if (intervalError) { setError(intervalError); return; }
    const data: CaseCoveragePrepareRequest = {
      expected_case_version: context.case.version, receiving_counselor_id: receiver, reason,
      starts_at: startISO!, expires_at: endISO!, tasks: coverageTaskInputs(context, tasks), student_communication: communication,
      ...(officeReason ? { office_preparation_reason: officeReason } : {}),
      ...(communication === "YES" ? { student_informed_at: institutionalDateTimeInputToISO(informedAt) } : {}),
      ...(communication === "DEFERRED" && deferral ? { communication_deferral_reason: deferral, ...(!existingCommunication ? { communication_next_action: nextAction, communication_due_at: institutionalDateTimeInputToISO(nextDue) } : {}) } : {}),
    };
    try {
      const response = existing
        ? await update.mutateAsync({ coverageId: existing.id, data: { ...data, expected_version: existing.version } })
        : await create.mutateAsync({ caseId: context.case.id, data });
      setDirty(false);
      await client.invalidateQueries({ queryKey: getCounselingGetCaseQueryKey(context.case.id) });
      router.push(withWorkflowReturn(coverageHref(response.data.id), returnTo));
    } catch (caught) {
      setError(continuityError(caught));
    }
  }

  return <form onSubmit={event => void save(event)} onChange={() => setDirty(true)} noValidate>
    <Panel aria-labelledby="coverage-form-heading">
      <PanelHeader title={`${context.case.reference_code} · ${context.case.student.display_name}`} titleId="coverage-form-heading" description={`${context.case.primary_counselor.display_name} stays the primary Counselor throughout the coverage.`} />
      <PanelSection title="1. Covering counselor and period" titleId="coverage-receiver-heading">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1"><Label htmlFor="coverage-receiver">Covering counselor</Label><Select id="coverage-receiver" required value={receiver} disabled={pending} onChange={event => setReceiver(event.target.value)}><option value="">Choose a Counselor</option>{context.receiver_options.map(item => <option key={item.person.id} value={item.person.id}>{item.person.display_name}</option>)}</Select>{option ? <CounselorAboutButton counselorId={option.person.id} counselorName={option.person.display_name} className="justify-self-start" /> : null}</div>
          <div className="grid gap-1"><Label htmlFor="coverage-reason">Neutral reason</Label><Select id="coverage-reason" value={reason} disabled={pending} onChange={event => { const value = enumChoice(Object.values(CaseContinuityReason), event.target.value); if (value) setReason(value); }}>{Object.values(CaseContinuityReason).map(value => <option key={value} value={value}>{continuityReasonLabels[value]}</option>)}</Select></div>
          <div className="grid gap-1"><Label htmlFor="coverage-starts">Starts (Philippine Time)</Label><Input id="coverage-starts" type="datetime-local" required value={starts} disabled={pending} onChange={event => setStarts(event.target.value)} /></div>
          <div className="grid gap-1"><Label htmlFor="coverage-ends">Ends (Philippine Time)</Label><Input id="coverage-ends" type="datetime-local" required value={ends} disabled={pending} onChange={event => setEnds(event.target.value)} /></div>
          {context.office_prepared ? <div className="grid gap-1 sm:col-span-2"><Label htmlFor="coverage-office-preparation">Why is the office preparing this?</Label><Select id="coverage-office-preparation" required value={officeReason} disabled={pending} onChange={event => setOfficeReason(enumChoice(Object.values(CaseOfficePreparationReason), event.target.value) ?? "")}><option value="">Choose a reason</option><option value="OWNER_UNAVAILABLE">Primary Counselor unavailable</option><option value="IMPARTIALITY_CONCERN">Potential impartiality concern</option></Select></div> : null}
        </div>
        <p className="mt-3 text-sm text-muted">Coverage lasts at most 30 days and starts at most 14 days ahead. To extend it, arrange a new coverage.</p>
        {blocked ? <Notice role="alert" tone="warning" className="mt-4">{blocked} The case stays with its current primary Counselor.</Notice> : option?.authorization_route ? <p className="mt-3 text-sm text-muted">{authorizationLabel(option.authorization_route)}</p> : null}
      </PanelSection>
      <PanelSection title="2. Actions to delegate" titleId="coverage-tasks-heading">
        <p className="mb-3 text-sm text-muted">Only the actions you select are delegated. Unfinished delegated actions return to the primary Counselor when coverage ends; nothing is completed or cancelled automatically.</p>
        {context.tasks.length ? <ul className="divide-y divide-border">{context.tasks.map((task, index) => {
          const choice = tasks[task.task_id] ?? { selected: false, plan: "RETURN_TO_PRIMARY" as CaseCoverageReturnPlan };
          const label = task.title ?? `Counseling action ${index + 1}`;
          return <li key={task.task_id} className="py-3 first:pt-0 text-sm">
            <div className="flex items-start gap-3">
              <input id={`coverage-task-${task.task_id}`} type="checkbox" className="mt-1 size-4" checked={choice.selected} disabled={!task.can_delegate || pending} onChange={event => setTasks(current => ({ ...current, [task.task_id]: { ...choice, selected: event.target.checked } }))} />
              <div className="min-w-0 flex-1">
                <label htmlFor={`coverage-task-${task.task_id}`} className="font-semibold">{label}</label>
                <p className="mt-1 text-muted">Due {formatCounselingDateTime(task.due_at)} · {task.assignee.display_name}</p>
                {task.blocked_reason ? <p className="mt-1 text-warning">{task.blocked_reason}</p> : null}
                {choice.selected ? <div className="mt-2 grid grid-cols-1 gap-1 sm:max-w-md"><Label htmlFor={`coverage-plan-${task.task_id}`}>Return plan for {label}</Label><Select id={`coverage-plan-${task.task_id}`} className="w-full min-w-0 max-w-full" value={choice.plan} disabled={pending} onChange={event => { const plan = enumChoice(Object.values(CaseCoverageReturnPlan), event.target.value); if (plan) setTasks(current => ({ ...current, [task.task_id]: { ...choice, plan } })); }}>{Object.values(CaseCoverageReturnPlan).map(value => <option key={value} value={value}>{returnPlanOptionLabels[value]}</option>)}</Select><p className="text-xs text-muted">{returnPlanLabels[choice.plan]}.</p></div> : null}
              </div>
            </div>
          </li>;
        })}</ul> : <p className="text-sm text-muted">No pending case actions. Coverage can still be arranged without delegating actions.</p>}
      </PanelSection>
      <PanelSection title="3. Student communication" titleId="coverage-communication-heading">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1"><Label htmlFor="coverage-student-communication">Has the Student been informed?</Label><Select id="coverage-student-communication" value={communication} disabled={pending} onChange={event => { const value = enumChoice(Object.values(CaseStudentCommunication), event.target.value); if (value) setCommunication(value); }}><option value="YES">Yes</option><option value="NO">No</option><option value="DEFERRED">Deferred</option></Select></div>
          {communication === "YES" ? <div className="grid gap-1"><Label htmlFor="coverage-informed-at">When informed (Philippine Time)</Label><Input id="coverage-informed-at" type="datetime-local" required value={informedAt} disabled={pending} onChange={event => setInformedAt(event.target.value)} /></div> : null}
          {communication === "DEFERRED" ? <>
            <div className="grid gap-1"><Label htmlFor="coverage-deferral">Why informing is deferred</Label><Select id="coverage-deferral" required value={deferral} disabled={pending} onChange={event => setDeferral(enumChoice(Object.values(CaseCommunicationDeferral), event.target.value) ?? "")}><option value="">Choose a reason</option><option value="STUDENT_UNAVAILABLE">Student unavailable</option><option value="CONTACT_PENDING">Contact pending</option><option value="SUPPORT_TIMING">Timing of support</option></Select></div>
            {existingCommunication ? <p className="text-sm sm:col-span-2">The recorded communication action remains with {existing?.communication_responsible?.display_name}.</p> : <>
              <div className="grid gap-1"><Label htmlFor="coverage-next-action">Next action to inform the Student</Label><Input id="coverage-next-action" required maxLength={120} value={nextAction} disabled={pending} onChange={event => setNextAction(event.target.value)} /></div>
              <div className="grid gap-1"><Label htmlFor="coverage-next-due">Communication deadline (Philippine Time)</Label><Input id="coverage-next-due" required type="datetime-local" value={nextDue} disabled={pending} onChange={event => setNextDue(event.target.value)} /></div>
            </>}
          </> : null}
        </div>
        <p className="mt-3 text-sm text-muted">COMPASS sends no message to the Student.</p>
      </PanelSection>
      <PanelFooter>
        <Button type="submit" disabled={pending || Boolean(blocked)} aria-busy={pending}>{pending ? "Saving coverage plan…" : "Save coverage plan"}</Button>
        {error ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : null}
      </PanelFooter>
    </Panel>
  </form>;
}

export function CoveragePreparePage({ caseId }: { caseId: string }) {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const editId = params.get("edit") ?? "";
  const back = portalReturnHref(params.get("return_to"), `/portal/counseling/cases/${caseId}`);
  const allowed = ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"].includes(user.role) && user.capabilities.includes("counseling.continuity.request");
  const existing = useCounselingGetCaseCoverage(editId, { query: { enabled: allowed && Boolean(editId), retry: false, gcTime: 0, staleTime: 0 } });
  const query = useCounselingGetCaseCoverageContext(caseId, { query: { enabled: allowed && (!editId || existing.data?.data.can_edit === true), retry: false, gcTime: 0, staleTime: 0 } });
  if (!allowed) return <CounselingUnavailable title="Arrange coverage" />;
  const heading = <CounselingPageHeading title="Arrange temporary coverage" back={<Link href={back} className={pageBackLinkClass}>{workflowBackLabel(back)}</Link>} />;
  const unavailable = <>{heading}<CounselingQueryError message={continuityError(query.error ?? existing.error, "Coverage preparation isn't available. Check access and try again.")} onRetry={() => { void query.refetch(); if (editId) void existing.refetch(); }} /></>;
  if (editId && existing.isPending) return <>{heading}<EncounterDetailSkeleton /></>;
  if (editId && (existing.isError || !existing.data?.data.can_edit)) return unavailable;
  if (query.isPending) return <>{heading}<EncounterDetailSkeleton /></>;
  if (query.isError || !query.data) return unavailable;
  return <>{heading}<CoverageForm key={`${user.id}:${editId}`} context={query.data.data} existing={existing.data?.data} returnTo={back} /></>;
}

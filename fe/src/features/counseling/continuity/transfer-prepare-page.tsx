"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { keepPreviousData, useQueryClient } from "@tanstack/react-query";
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
import { CounselingPageHeading, CounselingQueryError, CounselingUnavailable, EncounterDetailSkeleton } from "@/features/counseling/counseling-shared";
import {
  useCounselingGetCaseTransferContext, useCounselingGetCaseTransfer,
  useCounselingPrepareCaseTransfer, useCounselingUpdateCaseTransfer,
  getCounselingGetCaseQueryKey, getCounselingListMyCasesQueryKey,
} from "@/lib/api/generated/counseling/counseling";
import {
  CaseContinuityReason, CaseOfficePreparationReason, CaseStudentCommunication, CaseCommunicationDeferral,
  type CaseTransferContextResponse, type CaseTransferDetailResponse, type CaseTransferPrepareRequest,
} from "@/lib/api/generated/model";
import { institutionalDateTimeInputToISO, isoToInstitutionalDateTimeInput } from "@/lib/institutional-time";
import { authorizationLabel, continuityError, continuityReasonLabels, enumChoice, transferHref } from "./continuity-presentation";
import { TransferWorkFields, type TaskChoice, type AppointmentChoice } from "./transfer-work-fields";
import { HandoffFields, emptyHandoff, handoffLength } from "./handoff-fields";
import { useCoveragePrivacy } from "@/features/counseling/coverage/use-coverage-privacy";

function TransferForm({ context, existing, reason, setReason, confirmed, returnTo, refresh }: {
  context: CaseTransferContextResponse;
  existing?: CaseTransferDetailResponse;
  reason: CaseContinuityReason;
  setReason: (value: CaseContinuityReason) => void;
  confirmed: boolean;
  returnTo: string;
  refresh: () => Promise<unknown>;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const create = useCounselingPrepareCaseTransfer({ mutation: { retry: false } });
  const update = useCounselingUpdateCaseTransfer({ mutation: { retry: false } });
  const pending = create.isPending || update.isPending;
  const reopening = context.purpose === "REOPEN";
  const [receiver, setReceiver] = useState(existing?.receiving_counselor.id ?? "");
  const [officeReason, setOfficeReason] = useState<CaseOfficePreparationReason | "">(existing?.office_preparation_reason ?? "");
  const [tasks, setTasks] = useState<Record<string, TaskChoice>>(() => Object.fromEntries(existing?.tasks.map(task => [task.task_id, { disposition: task.disposition, title: task.successor_title ?? "", due: task.successor_due_at ? isoToInstitutionalDateTimeInput(task.successor_due_at) ?? "" : "" }]) ?? []));
  const [appointments, setAppointments] = useState<Record<string, AppointmentChoice>>(() => Object.fromEntries(existing?.appointments.map(appointment => [appointment.link_id, { disposition: appointment.disposition, retention: appointment.retention_reason ?? "" }]) ?? []));
  const [communication, setCommunication] = useState<CaseStudentCommunication>(existing?.student_communication ?? "NO");
  const [informedAt, setInformedAt] = useState(existing?.student_informed_at ? isoToInstitutionalDateTimeInput(existing.student_informed_at) ?? "" : "");
  const [deferral, setDeferral] = useState<CaseCommunicationDeferral | "">(existing?.communication_deferral_reason ?? "");
  const [communicationTitle, setCommunicationTitle] = useState("");
  const [communicationDue, setCommunicationDue] = useState("");
  const [handoff, setHandoff] = useState(emptyHandoff);
  const [caseVersion, setCaseVersion] = useState(context.case.version);
  const [offerVersion, setOfferVersion] = useState(existing?.version);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CaseTransferDetailResponse | null>(null);
  useUnsavedChangesGuard({ dirty: dirty && !result, message: "Leave this transfer preparation and discard unsaved changes?" });
  const stale = context.case.version !== caseVersion || existing?.version !== offerVersion;
  const option = context.receiver_options.find(item => item.person.id === receiver);
  const blocked = option?.blocked_reason;
  const existingCommunication = communication === "DEFERRED" && existing?.communication_task_id;

  async function save(event: FormEvent) {
    event.preventDefault();
    if (pending || stale || result || !confirmed) return;
    setError(null);
    const taskInputs: CaseTransferPrepareRequest["tasks"] = [];
    for (const task of context.tasks) {
      const choice = tasks[task.task_id];
      if (!choice?.disposition || !task.allowed_dispositions.includes(choice.disposition)) { setError("Choose an available disposition for every pending action."); return; }
      const due = choice.disposition === "HAND_OVER_AS_NEW" ? institutionalDateTimeInputToISO(choice.due) : null;
      if (choice.disposition === "HAND_OVER_AS_NEW" && (!choice.title.trim() || !due)) { setError("Every successor needs a new title and deadline."); return; }
      taskInputs.push({ task_id: task.task_id, expected_version: task.version, disposition: choice.disposition, ...(choice.disposition === "HAND_OVER_AS_NEW" ? { successor_title: choice.title, successor_due_at: due } : {}) });
    }
    const appointmentInputs: CaseTransferPrepareRequest["appointments"] = [];
    for (const appointment of context.appointments) {
      const choice = appointments[appointment.link_id];
      if (!choice?.disposition || (choice.disposition === "RETAIN_WITH_PROVIDER" && !choice.retention)) { setError("Choose a plan for every upcoming Appointment, including a reason for retaining its provider."); return; }
      appointmentInputs.push({ link_id: appointment.link_id, disposition: choice.disposition, ...(choice.disposition === "RETAIN_WITH_PROVIDER" && choice.retention ? { retention_reason: choice.retention } : {}) });
    }
    if (!receiver || blocked || (context.office_prepared && !officeReason)) { setError(blocked ?? "Choose the receiver and explain office preparation when required."); return; }
    if (handoffLength(handoff) > 12000) { setError("The handoff narrative may contain at most 12,000 characters across all sections."); return; }
    const data: CaseTransferPrepareRequest = {
      expected_case_version: caseVersion, receiving_counselor_id: receiver, reason,
      ...(reopening ? { purpose: "REOPEN" } : {}),
      tasks: taskInputs, appointments: appointmentInputs, student_communication: communication,
      ...(!reopening && !context.office_prepared && Object.values(handoff).some(text => text.trim()) ? { handoff_sections: handoff } : {}),
      ...(officeReason ? { office_preparation_reason: officeReason } : {}),
      ...(communication === "YES" ? { student_informed_at: institutionalDateTimeInputToISO(informedAt) } : {}),
      ...(communication === "DEFERRED" && deferral ? { communication_deferral_reason: deferral, ...(!existingCommunication ? { communication_next_action: communicationTitle, communication_due_at: institutionalDateTimeInputToISO(communicationDue) } : {}) } : {}),
    };
    try {
      const response = existing
        ? await update.mutateAsync({ transferId: existing.id, data: { ...data, expected_version: offerVersion ?? existing.version } })
        : await create.mutateAsync({ caseId: context.case.id, data });
      setResult(response.data);
      setDirty(false);
      await Promise.all([client.invalidateQueries({ queryKey: getCounselingGetCaseQueryKey(context.case.id) }), client.invalidateQueries({ queryKey: getCounselingListMyCasesQueryKey() })]);
      router.push(withWorkflowReturn(transferHref(response.data.id), returnTo));
    } catch (caught) {
      setError(continuityError(caught));
      await refresh();
    }
  }

  if (result) return <Notice role="status" action={<Link className="font-semibold text-brand underline" href={withWorkflowReturn(transferHref(result.id), returnTo)}>Review transfer</Link>}>Transfer plan saved. Review and submit it to the next actor.</Notice>;
  return <form onSubmit={event => void save(event)} onChange={() => setDirty(true)}>
    {stale ? <Notice role="alert" className="mb-5" tone="warning" action={<Button type="button" variant="secondary" onClick={() => { setCaseVersion(context.case.version); setOfferVersion(existing?.version); setError(null); }}>I have reviewed the latest work</Button>}>The case or arrangement changed. Your input is kept; review the current actions and appointments before saving.</Notice> : null}
    <Panel aria-labelledby="transfer-form-heading">
      <PanelHeader title={`${context.case.reference_code} · ${context.case.student.display_name}`} titleId="transfer-form-heading" description={`Primary counselor: ${context.case.primary_counselor.display_name}`} />
      {reopening ? <PanelSection title="Closed case for reopening" titleId="transfer-reopening-heading"><p className="text-sm">Acceptance moves responsibility to the receiving Counselor and reopens the same episode with reason “Further support needed”. Existing after-closure action owners stay unchanged.</p><p className="mt-2 text-sm text-muted">The office prepares this only when the current owner is unavailable. Independent Head authorization is required.</p></PanelSection> : null}
      <PanelSection title="1. Receiver and reason" titleId="transfer-receiver-heading">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1"><Label htmlFor="transfer-receiver">Receiving counselor</Label><Select id="transfer-receiver" required value={receiver} onChange={event => setReceiver(event.target.value)}><option value="">Choose a Counselor</option>{context.receiver_options.map(item => <option key={item.person.id} value={item.person.id}>{item.person.display_name}</option>)}</Select>{option ? <CounselorAboutButton counselorId={option.person.id} counselorName={option.person.display_name} className="justify-self-start" /> : null}</div>
          <div className="grid gap-1"><Label htmlFor="transfer-reason">Neutral reason</Label><Select id="transfer-reason" value={reason} onChange={event => { const value = enumChoice(Object.values(CaseContinuityReason), event.target.value); if (value) setReason(value); }}>{Object.values(CaseContinuityReason).map(value => <option key={value} value={value}>{continuityReasonLabels[value]}</option>)}</Select></div>
          {context.office_prepared ? <div className="grid gap-1 sm:col-span-2"><Label htmlFor="office-preparation">Why is the office preparing this?</Label><Select id="office-preparation" required value={officeReason} onChange={event => setOfficeReason(enumChoice(Object.values(CaseOfficePreparationReason), event.target.value) ?? "")}><option value="">Choose a reason</option><option value="OWNER_UNAVAILABLE">Owner unavailable</option>{!reopening ? <option value="IMPARTIALITY_CONCERN">Impartiality concern</option> : null}</Select></div> : null}
        </div>
        {blocked ? <Notice role="alert" tone="warning" className="mt-4">{blocked} The case stays with its current primary Counselor.</Notice> : option?.authorization_route ? <p className="mt-3 text-sm text-muted">{authorizationLabel(option.authorization_route)}</p> : null}
      </PanelSection>
      {!reopening ? <TransferWorkFields context={context} tasks={tasks} appointments={appointments} changeTask={(id, choice) => { setTasks(current => ({ ...current, [id]: choice })); setDirty(true); }} changeAppointment={(id, choice) => { setAppointments(current => ({ ...current, [id]: choice })); setDirty(true); }} returnTo={returnTo} /> : null}
      {!reopening ? <PanelSection title="4. Handoff" titleId="transfer-form-handoff-heading">
        {context.office_prepared ? <p className="text-sm">The Head must record why a clinical handoff is unavailable before this transfer can be submitted.</p> : <>
          <p className="mb-4 text-sm text-muted">Save a structured draft here or write it from the review page. Submit the handoff before submitting the transfer. The selected action and Appointment plans are saved as read-only work.</p>
          {existing?.handoff?.state === "SUBMITTED" ? <p className="mb-4 text-sm text-warning">Changing the plan requires a new handoff. The previous submitted snapshot remains immutable.</p> : null}
          <HandoffFields value={handoff} onChange={setHandoff} disabled={pending} />
        </>}
      </PanelSection> : null}
      <PanelSection title={reopening ? "2. Student communication" : "5. Student communication"} titleId="transfer-communication-heading">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1"><Label htmlFor="student-communication">Has the Student been informed?</Label><Select id="student-communication" value={communication} onChange={event => { const value = enumChoice(Object.values(CaseStudentCommunication), event.target.value); if (value) setCommunication(value); }}><option value="YES">Yes</option><option value="NO">No</option>{!reopening ? <option value="DEFERRED">Deferred</option> : null}</Select></div>
          {communication === "YES" ? <div className="grid gap-1"><Label htmlFor="student-informed-at">When informed (Philippine Time)</Label><Input id="student-informed-at" type="datetime-local" required value={informedAt} onChange={event => setInformedAt(event.target.value)} /></div> : null}
          {communication === "DEFERRED" ? <>
            <div className="grid gap-1"><Label htmlFor="deferral-reason">Why informing is deferred</Label><Select id="deferral-reason" required value={deferral} onChange={event => setDeferral(enumChoice(Object.values(CaseCommunicationDeferral), event.target.value) ?? "")}><option value="">Choose a reason</option><option value="STUDENT_UNAVAILABLE">Student unavailable</option><option value="CONTACT_PENDING">Contact pending</option><option value="SUPPORT_TIMING">Timing of support</option></Select></div>
            {existingCommunication ? <p className="text-sm sm:col-span-2">The recorded communication action remains with {existing?.communication_responsible?.display_name}. Change it through Follow-ups before reviewing a new plan.</p> : <>
              <div className="grid gap-1"><Label htmlFor="communication-title">Next action to inform the Student</Label><Input id="communication-title" required maxLength={120} value={communicationTitle} onChange={event => setCommunicationTitle(event.target.value)} /></div>
              <div className="grid gap-1"><Label htmlFor="communication-due">Communication deadline (Philippine Time)</Label><Input id="communication-due" required type="datetime-local" value={communicationDue} onChange={event => setCommunicationDue(event.target.value)} /></div>
              <p className="text-sm text-muted sm:col-span-2">{context.case.primary_counselor.display_name} handles the case action while pending; it follows the case on acceptance.</p>
            </>}
          </> : null}
        </div>
        <p className="mt-3 text-sm text-muted">Your identity records who entered this communication status. COMPASS sends no message to the Student.</p>
      </PanelSection>
      <PanelSection title="6. Review and save" titleId="transfer-save-heading"><p className="text-sm">Responsibility changes only when the receiving Counselor accepts. Saving this plan starts no transfer; the review page provides the submission step.</p></PanelSection>
      <PanelFooter>
        <Button type="submit" disabled={pending || stale || !confirmed || Boolean(blocked)}>{pending ? "Saving transfer plan…" : "Save transfer plan"}</Button>
        {error ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : null}
      </PanelFooter>
    </Panel>
  </form>;
}

export function TransferPreparePage({ caseId }: { caseId: string }) {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const editId = params.get("edit") ?? "";
  const requestedPurpose = params.get("purpose") === "REOPEN" ? "REOPEN" : undefined;
  const privacy = useCoveragePrivacy(user.id, editId || caseId);
  const back = portalReturnHref(params.get("return_to"), `/portal/counseling/cases/${caseId}`);
  const [reasonChoice, setReasonChoice] = useState<{ editId: string; reason: CaseContinuityReason } | null>(null);
  const allowed = ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"].includes(user.role) && user.capabilities.includes("counseling.continuity.request");
  const existing = useCounselingGetCaseTransfer(editId, { query: { enabled: allowed && Boolean(editId), retry: false, gcTime: 0, staleTime: 0 } });
  const reason = reasonChoice?.editId === editId ? reasonChoice.reason : existing.data?.data.reason ?? "SERVICE_RESPONSIBILITY_CHANGE";
  const purpose = existing.data?.data.purpose ?? requestedPurpose;
  const query = useCounselingGetCaseTransferContext(caseId, { reason, ...(purpose ? { purpose } : {}) }, { query: { enabled: allowed && (!editId || existing.data?.data.can_edit === true), retry: false, gcTime: 0, staleTime: 0, placeholderData: keepPreviousData, refetchOnWindowFocus: "always", refetchOnReconnect: "always" } });
  if (!allowed) return <CounselingUnavailable title="Transfer case" />;
  const heading = <CounselingPageHeading title={purpose === "REOPEN" ? "Transfer to reopen case" : "Transfer case"} back={<Link href={back} className={pageBackLinkClass}>{workflowBackLabel(back)}</Link>} />;
  if (privacy.blocked) return <>{heading}<Notice tone="warning" action={<Button variant="secondary" onClick={() => { privacy.resume(); void query.refetch(); }}>Check preparation access</Button>}>Protected preparation text has been cleared. Check access again to continue.</Notice></>;
  const unavailable = <>{heading}<CounselingQueryError message={continuityError(query.error ?? existing.error, "The transfer preparation isn't available. Check access and try again.")} onRetry={() => { void query.refetch(); if (editId) void existing.refetch(); }} /></>;
  if (editId && existing.isPending) return <>{heading}<EncounterDetailSkeleton /></>;
  if (editId && (existing.isError || !existing.data?.data.can_edit)) return unavailable;
  if (query.isPending) return <>{heading}<EncounterDetailSkeleton /></>;
  if (query.isError || !query.data) return unavailable;
  return <>{heading}<TransferForm key={`${user.id}:${editId}:${privacy.generation}`} context={query.data.data} existing={existing.data?.data} reason={reason} setReason={value => setReasonChoice({ editId, reason: value })} confirmed={!query.isPlaceholderData} returnTo={back} refresh={() => Promise.all([query.refetch(), editId ? existing.refetch() : Promise.resolve()])} /></>;
}

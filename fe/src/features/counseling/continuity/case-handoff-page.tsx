"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/ui/notice";
import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Panel, PanelHeader, PanelBody, PanelSection, PanelFooter } from "@/components/ui/panel";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { portalReturnHref, workflowBackLabel } from "@/features/portal/workflow-navigation";
import { useCoveragePrivacy } from "@/features/counseling/coverage/use-coverage-privacy";
import { requestSessionRevalidation } from "@/lib/auth/session-revalidation";
import { isAuthorityError, isSessionEndedError } from "@/features/freshness/query-freshness";
import { CounselingQueryError, CounselingUnavailable, EncounterDetailSkeleton, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import * as api from "@/lib/api/generated/counseling/counseling";
import type { CaseHandoffBodyResponse, CaseHandoffSections, CaseTransferDetailResponse } from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";
import { HandoffFields, emptyHandoff, handoffLength, handoffSectionLabels } from "./handoff-fields";
import { continuityError, continuityStale, transferHref, taskDispositionLabels, appointmentDispositionLabels } from "./continuity-presentation";

type Privacy = ReturnType<typeof useCoveragePrivacy>;

function HandoffEditor({ item, body, onChanged, onSaved }: {
  item: CaseTransferDetailResponse; body?: CaseHandoffBodyResponse;
  onChanged: () => Promise<unknown>; onSaved: (message: string) => void;
}) {
  const save = api.useCounselingSaveCaseHandoff({ mutation: { retry: false, gcTime: 0 } });
  const submit = api.useCounselingSubmitCaseHandoff({ mutation: { retry: false, gcTime: 0 } });
  const [baseline, setBaseline] = useState(body);
  const [sections, setSections] = useState<CaseHandoffSections>(body?.sections ?? emptyHandoff);
  const [initialVersion, setInitialVersion] = useState(item.version);
  const [open, setOpen] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const pending = save.isPending || submit.isPending;
  const dirty = JSON.stringify(sections) !== JSON.stringify(baseline?.sections ?? emptyHandoff);
  const version = baseline?.transfer_version ?? initialVersion;
  const stale = conflict || version !== item.version || Boolean(body && baseline && body.version !== baseline.version);
  useUnsavedChangesGuard({ dirty: dirty && !completed, message: "Leave this handoff and discard unsaved text?" });

  async function write(event?: FormEvent) {
    event?.preventDefault();
    if (pending || stale || handoffLength(sections) > 12000) return;
    try {
      setError(null);
      const response = await save.mutateAsync({ transferId: item.id, data: { sections, expected_transfer_version: version, expected_handoff_version: baseline?.version ?? null } });
      setBaseline(response.data);
      await onChanged();
      onSaved("Handoff draft saved.");
    } catch (caught) {
      setError(continuityError(caught));
      if (continuityStale(caught)) { setConflict(true); await onChanged(); }
    }
  }
  async function lock() {
    if (!baseline || dirty || pending || stale) return;
    try {
      setError(null);
      await submit.mutateAsync({ transferId: item.id, data: { expected_transfer_version: version, expected_handoff_version: baseline.version } });
      setCompleted(true);
    } catch (caught) {
      if (continuityStale(caught)) { setOpen(false); setConflict(true); await onChanged(); }
      setError(continuityError(caught));
    }
  }
  return <>
    <form onSubmit={event => void write(event)}>
      <Panel aria-labelledby="case-handoff-editor-heading"><PanelHeader title="Draft handoff" titleId="case-handoff-editor-heading" description={`Receiving counselor: ${item.receiving_counselor.display_name}`} />
        <PanelBody><HandoffFields value={sections} onChange={setSections} disabled={pending || completed} />
          {stale ? <Notice className="mt-4" tone="warning">The saved handoff or plan changed. Your text is kept. Review the current saved version before another attempt.
            {body ? <details className="mt-3"><summary>Current saved handoff</summary>{Object.entries(handoffSectionLabels).map(([key, label]) => <div key={key} className="mt-3"><p className="font-semibold">{label}</p><p className="whitespace-pre-wrap break-words">{body.sections[key as keyof CaseHandoffSections]}</p></div>)}</details> : null}
            <Button className="mt-3" type="button" variant="secondary" onClick={() => { setBaseline(body); setInitialVersion(item.version); setConflict(false); }}>Use current saved version</Button>
          </Notice> : null}
          {error && !open ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
        </PanelBody>
        <PanelFooter><Button type="submit" disabled={pending || stale || !dirty || handoffLength(sections) > 12000}>{save.isPending ? "Saving handoff…" : "Save handoff draft"}</Button><Button type="button" variant="secondary" disabled={!baseline || dirty || pending || stale || !sections.context_and_purpose.trim() || !sections.receiver_next_steps.trim()} onClick={() => { setOpen(true); setError(null); }}>Submit handoff</Button></PanelFooter>
      </Panel>
    </form>
    <ConsequentialActionDialog open={open} onOpenChange={value => { setOpen(value); if (!value && completed) void onChanged(); }} onCloseAutoFocus={event => { event.preventDefault(); focusHeading("case-handoff-page-heading"); }} title="Submit handoff?" confirmLabel="Submit handoff" pendingLabel="Submitting…" pending={submit.isPending} confirmDisabled={dirty || stale} error={error} onConfirm={() => void lock()}
      completed={completed ? { title: "Handoff submitted", children: "The snapshot is immutable. Review the transfer and submit it separately; later information belongs in an attributed addendum." } : null}>
      Submission locks this narrative and the reviewed work snapshot for {item.receiving_counselor.display_name}. It remains confidential and does not accept the case or complete any task.
    </ConsequentialActionDialog>
  </>;
}

function HandoffWork({ body }: { body: CaseHandoffBodyResponse }) {
  return <Panel aria-labelledby="handoff-work-heading" className="mt-5"><PanelHeader title="Reviewed work" titleId="handoff-work-heading" description="Saved with the handoff; task and Appointment actions remain separate." />
    <PanelSection title="Pending actions" titleId="handoff-action-heading">{body.work.tasks.length ? <ul className="divide-y divide-border">{body.work.tasks.map((task, index) => <li className="py-3 first:pt-0 text-sm" key={task.task_id}><p className="font-semibold">Counseling action {index + 1} · {taskDispositionLabels[task.disposition]}</p><p>{task.responsible.display_name} · Due {formatCounselingDateTime(task.due_at)}</p></li>)}</ul> : <p className="text-sm text-muted">No pending actions in the reviewed plan.</p>}</PanelSection>
    <PanelSection title="Appointments" titleId="handoff-appointment-heading">{body.work.appointments.length ? <ul className="divide-y divide-border">{body.work.appointments.map(appointment => <li className="py-3 first:pt-0 text-sm" key={appointment.appointment_id}><p className="font-semibold">{appointment.reference_code} · {appointmentDispositionLabels[appointment.disposition]}</p><p>{appointment.responsible.display_name} · {formatCounselingDateTime(appointment.starts_at)}</p></li>)}</ul> : <p className="text-sm text-muted">No upcoming appointments in the reviewed plan.</p>}</PanelSection>
  </Panel>;
}

function AddendumForm({ item, body, onChanged }: { item: CaseTransferDetailResponse; body: CaseHandoffBodyResponse; onChanged: () => Promise<unknown> }) {
  const mutation = api.useCounselingAddCaseHandoffAddendum({ mutation: { retry: false, gcTime: 0 } });
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(item.version);
  const [completed, setCompleted] = useState(false);
  useUnsavedChangesGuard({ dirty: Boolean(text) && !completed, message: "Leave this handoff and discard the unsaved addendum?" });
  async function add() {
    if (mutation.isPending || version !== item.version) return;
    try {
      setError(null);
      await mutation.mutateAsync({ handoffId: body.id, data: { expected_transfer_version: version, content: text } });
      setCompleted(true); setText("");
    } catch (caught) { setError(continuityError(caught)); if (continuityStale(caught)) { setOpen(false); await onChanged(); } }
  }
  return <Panel className="mt-5"><PanelHeader title="Add new information" /><PanelBody><Label htmlFor="case-handoff-addendum">Attributed addendum</Label><Textarea id="case-handoff-addendum" rows={5} value={text} onChange={event => setText(event.target.value)} disabled={mutation.isPending} aria-invalid={text.length > 12000} />
    {error && !open ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}</PanelBody><PanelFooter><Button disabled={!text.trim() || text.length > 12000} onClick={() => { setVersion(item.version); setCompleted(false); setOpen(true); }}>Add addendum</Button></PanelFooter>
    <ConsequentialActionDialog open={open} onOpenChange={value => { setOpen(value); if (!value && completed) void onChanged(); }} title="Add handoff addendum?" confirmLabel="Add addendum" pendingLabel="Adding…" pending={mutation.isPending} confirmDisabled={version !== item.version} error={error} onConfirm={() => void add()} completed={completed ? { title: "Handoff addendum recorded", children: "The new information is attributed and dated. The submitted snapshot is unchanged." } : null}>This adds immutable information under your name. A pending transfer needs fresh submission and authorization after this change.</ConsequentialActionDialog>
  </Panel>;
}

function HandoffWorkspace({ item, privacy, onChanged }: { item: CaseTransferDetailResponse; privacy: Privacy; onChanged: () => Promise<unknown> }) {
  const [page, setPage] = useState(1);
  const status = useActionStatus();
  const params = { addenda_page: page };
  const query = useQuery({ queryKey: [...privacy.prefix, privacy.generation, ...api.getCounselingGetCaseHandoffQueryKey(item.handoff?.id ?? "", params)], gcTime: 0, staleTime: 0, retry: false, networkMode: "always", refetchInterval: 15000, refetchOnWindowFocus: "always", refetchOnReconnect: "always", enabled: Boolean(item.handoff && item.can_read_handoff) && !privacy.blocked,
    queryFn: async ({ signal }) => {
      const generation = privacy.barrier.current();
      try {
        if (!item.handoff || !navigator.onLine || document.visibilityState !== "visible") throw new Error("Protected access needs another check.");
        const response = await api.counselingGetCaseHandoff(item.handoff.id, params, { signal });
        privacy.barrier.assertCurrent(generation, signal);
        if (!navigator.onLine || document.visibilityState !== "visible") throw new Error("Protected access needs another check.");
        return response;
      } catch (caught) {
        if (!signal.aborted && generation === privacy.barrier.current()) {
          if (isSessionEndedError(caught)) requestSessionRevalidation("session");
          else if (isAuthorityError(caught)) requestSessionRevalidation("authority");
          privacy.clear();
        }
        throw caught;
      }
    },
  });
  const body = query.data?.data;
  const refresh = () => Promise.all([onChanged(), item.handoff ? query.refetch() : Promise.resolve()]);
  if (item.handoff && query.isPending) return <EncounterDetailSkeleton />;
  if (query.isError) return <CounselingQueryError message={continuityError(query.error)} onRetry={() => void refresh()} />;
  return <>
    {body?.state === "SUBMITTED" ? <Panel aria-labelledby="submitted-handoff-heading"><PanelHeader title="Submitted handoff" titleId="submitted-handoff-heading" description={`${body.author.display_name} · ${body.submitted_at ? formatCounselingDateTime(body.submitted_at) : ""}`} />
      <PanelBody><p className="mb-4 text-sm text-muted">Opening records receipt. Acceptance remains a separate decision.</p>{Object.entries(handoffSectionLabels).map(([key, label]) => <section key={key} className="mt-5 first:mt-0"><h3 className="text-sm font-semibold text-brand">{label}</h3><p className="mt-2 whitespace-pre-wrap break-words text-sm">{body.sections[key as keyof CaseHandoffSections] || "Not supplied"}</p></section>)}</PanelBody>
    </Panel> : <HandoffEditor item={item} body={body} onChanged={refresh} onSaved={status.show} />}
    {body ? <HandoffWork body={body} /> : null}
    {body?.state === "SUBMITTED" ? <Panel className="mt-5"><PanelHeader title="Addenda" /><PanelBody>{body.addenda.length ? <ol className="divide-y divide-border">{body.addenda.map(addition => <li className="py-4 first:pt-0" key={addition.id}><p className="text-sm font-semibold">{addition.author.display_name} · {formatCounselingDateTime(addition.created_at)}</p><p className="mt-2 whitespace-pre-wrap break-words text-sm">{addition.content}</p></li>)}</ol> : <p className="text-sm text-muted">No addenda recorded.</p>}<div className="mt-3 flex flex-wrap gap-3">{page > 1 ? <Button variant="secondary" onClick={() => setPage(page - 1)}>Previous addenda</Button> : null}{body.addenda_has_next ? <Button variant="secondary" onClick={() => setPage(page + 1)}>Older addenda</Button> : null}</div></PanelBody></Panel> : null}
    {body?.can_addendum ? <AddendumForm item={item} body={body} onChanged={refresh} /> : null}
    <ActionStatus status={status.status} onDismiss={status.dismiss} />
  </>;
}

export function CaseHandoffPage({ transferId }: { transferId: string }) {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const client = useQueryClient();
  const privacy = useCoveragePrivacy(user.id, transferId);
  const allowed = user.role === "COUNSELOR" && user.capabilities.includes("counseling.continuity.view");
  const query = api.useCounselingGetCaseTransfer(transferId, { query: { enabled: allowed && !privacy.blocked, retry: false, gcTime: 0, staleTime: 0, refetchInterval: 15000, refetchOnWindowFocus: "always", refetchOnReconnect: "always" } });
  const item = query.data?.data;
  const back = portalReturnHref(params.get("return_to"), transferHref(transferId));
  const heading = <PageHeader title="Case handoff" headingId="case-handoff-page-heading" back={<Link className={pageBackLinkClass} href={back}>{workflowBackLabel(back)}</Link>} />;
  if (!allowed) return <CounselingUnavailable title="Case handoff" />;
  if (privacy.blocked) return <>{heading}<Notice tone="warning" action={<Button variant="secondary" onClick={() => { privacy.resume(); void query.refetch(); }}>Check handoff access</Button>}>Protected handoff text has been cleared. Check access again to continue.</Notice></>;
  if (query.isPending) return <>{heading}<EncounterDetailSkeleton /></>;
  if (query.isError || !item) return <>{heading}<CounselingQueryError message={continuityError(query.error)} onRetry={() => void query.refetch()} /></>;
  if (!item.can_read_handoff && !item.can_write_handoff) return <>{heading}<Notice tone="warning">This protected handoff is unavailable to this account or the review has ended.</Notice></>;
  async function changed() { await Promise.all([query.refetch(), client.invalidateQueries({ queryKey: ["/api/v1/work"] })]); }
  return <>{heading}<HandoffWorkspace key={`${user.id}:${transferId}:${privacy.generation}`} item={item} privacy={privacy} onChanged={changed} /></>;
}

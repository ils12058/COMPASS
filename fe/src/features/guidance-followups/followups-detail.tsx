"use client";

import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelSection, PanelFooter } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { stepUpRequirement, type StepUpRequirement } from "@/features/account/security/step-up";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { useGuidanceFollowupsHistory, useGuidanceFollowupsGet, useGuidanceFollowupsEligibleAssignees, guidanceFollowupsUpdate, guidanceFollowupsReassign, guidanceFollowupsRecordActivity, guidanceFollowupsComplete, guidanceFollowupsCancel, getGuidanceFollowupsListQueryKey, getGuidanceFollowupsGetQueryKey } from "@/lib/api/generated/guidance-followups/guidance-followups";
import { Category, type FollowUpDetail } from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/errors";
import { formatInstitutionalDateTime, isoToInstitutionalDateTimeInput, institutionalDateTimeInputToISO } from "@/lib/institutional-time";
import { followupAccess, FollowupRestricted, FollowupFailure, followupError, categoryLabel, statusLabel, sourceDestination } from "./followups-shared";

type Action = "edit" | "reschedule" | "reassign" | "activity" | "complete" | "cancel";
const actionLabel: Record<Action, string> = { edit: "Edit follow-up", reschedule: "Reschedule", reassign: "Reassign", activity: "Record activity", complete: "Complete follow-up", cancel: "Cancel follow-up" };
export function FollowupsDetail({ id }: { id: string }) {
  const { user } = usePortalSession();
  const access = followupAccess(user);
  const query = useGuidanceFollowupsGet(id, { query: { enabled: access.view, retry: false, refetchOnWindowFocus: true } });
  const [action, setAction] = useState<Action | null>(null);
  const item = query.data?.data;
  if (!access.view) return <FollowupRestricted />;
  if (query.isPending) return <p role="status">Loading follow-up…</p>;
  if (!item || (query.error instanceof CompassApiError && [403, 404].includes(query.error.status))) return <FollowupFailure error={query.error} retry={() => void query.refetch()} />;
  return <>
    {query.isError ? <p role="alert">The latest details could not be confirmed. <Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button></p> : null}
    <PageHeader title="Guidance follow-up" description={item.student_name} back={<Link href="/portal/follow-ups" className={pageBackLinkClass}>Back to Follow-Ups</Link>} meta={<span className="text-sm font-semibold">{statusLabel(item.status)}{item.overdue ? " · Overdue" : ""}</span>} />
    <Panel>
      <PanelSection title="Follow-up details" titleId="followup-facts"><dl className="grid gap-4 sm:grid-cols-2">
        <div><dt className="text-sm text-muted">Category</dt><dd>{categoryLabel(item.category)}</dd></div><div><dt className="text-sm text-muted">Responsible staff member</dt><dd>{item.assigned_to_name}</dd></div>
        <div><dt className="text-sm text-muted">Due date (Philippine Time)</dt><dd>{formatInstitutionalDateTime(item.due_at)}</dd></div><div><dt className="text-sm text-muted">Access</dt><dd>{item.visibility === "COUNSELOR_CONFIDENTIAL" ? "Counselor-confidential" : "Operational coordination"}</dd></div>
      </dl></PanelSection>
      <PanelSection title="Description" titleId="followup-description"><p className="whitespace-pre-wrap break-words">{item.description || "No description recorded."}</p></PanelSection>
      {item.source ? <PanelSection title="Related record" titleId="followup-source"><Link className="font-semibold text-brand underline" href={sourceDestination(item.source)}>Open related record</Link><p className="mt-2 text-sm text-muted">The related record keeps its own access rules and status.</p></PanelSection> : item.source_unavailable ? <PanelSection title="Related record" titleId="followup-source"><p>The related record is no longer available to your account. This follow-up keeps its own status.</p></PanelSection> : null}
      {item.status === "COMPLETED" ? <PanelSection title="Completion" titleId="followup-completion"><p className="whitespace-pre-wrap break-words">{item.outcome}</p><p className="mt-2 text-sm text-muted">Completed by {item.completed_by_name} · {item.completed_at ? formatInstitutionalDateTime(item.completed_at) : ""}</p></PanelSection> : item.status === "CANCELLED" ? <PanelSection title="Cancellation" titleId="followup-cancellation"><p>Cancelled by {item.cancelled_by_name} · {item.cancelled_at ? formatInstitutionalDateTime(item.cancelled_at) : ""}</p></PanelSection> : null}
    </Panel>
    {access.manage && item.status === "PENDING" ? <Panel className="mt-5"><PanelHeader title="Follow-up actions" />{action ? <FollowupActionForm item={item} confirmed={!query.isError && !query.isFetching} action={action} onClose={() => setAction(null)} /> : <div className="flex flex-wrap gap-2 p-5">{(Object.keys(actionLabel) as Action[]).map(value => <Button key={value} variant={value === "complete" ? "primary" : "secondary"} disabled={query.isFetching} onClick={() => setAction(value)}>{actionLabel[value]}</Button>)}</div>}</Panel> : null}
    <FollowupHistory item={item} />
  </>;
}

function FollowupActionForm({ item, action, onClose, confirmed }: { item: FollowUpDetail; confirmed: boolean; action: Action; onClose: () => void }) {
  const router = useRouter();
  const client = useQueryClient();
  const [text, setText] = useState(action === "edit" ? item.description ?? "" : "");
  const [due, setDue] = useState(isoToInstitutionalDateTimeInput(item.due_at));
  const [category, setCategory] = useState(item.category);
  const [assignee, setAssignee] = useState("");
  const [staffPage, setStaffPage] = useState(1);
  const [version, setVersion] = useState(item.version);
  const [review, setReview] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState<StepUpRequirement | null>(null);
  const assignees = useGuidanceFollowupsEligibleAssignees({ student_id: item.student_id, category: item.category, source_kind: item.source?.kind, source_id: item.source?.id, page: staffPage }, { query: { enabled: action === "reassign", retry: false } });
  const mutation = useMutation({ mutationFn: async () => {
    const common = { expected_version: version };
    if (action === "edit") return guidanceFollowupsUpdate(item.id, { ...common, category, description: text });
    if (action === "reschedule") {
      const at = institutionalDateTimeInputToISO(due);
      if (!at) throw new Error("Choose a valid due date.");
      return guidanceFollowupsUpdate(item.id, { ...common, due_at: at });
    }
    if (action === "reassign") return guidanceFollowupsReassign(item.id, { ...common, assigned_to_id: assignee });
    if (action === "activity") return guidanceFollowupsRecordActivity(item.id, { ...common, remarks: text });
    if (action === "complete") return guidanceFollowupsComplete(item.id, { ...common, outcome: text });
    return guidanceFollowupsCancel(item.id, { ...common, reason: text });
  } });
  useUnsavedChangesGuard({ dirty: !mutation.isSuccess && Boolean(text || assignee || due !== isoToInstitutionalDateTimeInput(item.due_at)), message: "Your follow-up changes have not been saved." });
  async function save() {
    setError(null);
    try {
      const result = await mutation.mutateAsync();
      await Promise.all([client.invalidateQueries({ queryKey: getGuidanceFollowupsListQueryKey() }), invalidateGuidanceWork(client)]);
      if (action === "reassign" && result.data.assigned_to_id !== item.assigned_to_id) router.push("/portal/follow-ups");
      else { client.setQueryData(getGuidanceFollowupsGetQueryKey(item.id), result); onClose(); }
    } catch (caught) {
      setReview(false);
      const requirement = stepUpRequirement(caught);
      if (requirement) { setStepUp(requirement); return; }
      if (caught instanceof CompassApiError && caught.status === 409) {
        setConflict(true);
        await client.invalidateQueries({ queryKey: getGuidanceFollowupsGetQueryKey(item.id) });
      }
      setError(followupError(caught));
    }
  }
  const consequential = ["complete", "cancel", "reassign"].includes(action);
  function submit(event: FormEvent) { event.preventDefault(); if (consequential) setReview(true); else void save(); }
  return <>
    <form onSubmit={submit}>
      <div className="space-y-4 p-5"><h3 className="font-semibold">{actionLabel[action]}</h3>
        {action === "edit" ? <><Label htmlFor="followup-edit-category">Category</Label><Select id="followup-edit-category" value={category} onChange={event => setCategory(event.target.value as Category)} disabled={mutation.isPending}>{(item.visibility === "COUNSELOR_CONFIDENTIAL" || item.source?.kind === "REFERRAL" ? [item.category] : [Category.ADMINISTRATIVE, Category.STUDENT_CONTACT, Category.REFERRAL_ACTION]).map(value => <option key={value} value={value}>{categoryLabel(value)}</option>)}</Select></> : null}
        {action === "reschedule" ? <><Label htmlFor="followup-new-due">New due date and time (Philippine Time)</Label><Input id="followup-new-due" type="datetime-local" value={due} required disabled={mutation.isPending} onChange={event => setDue(event.target.value)} /></> : action === "reassign" ? <>
          <Label htmlFor="followup-new-assignee">Responsible staff member</Label><Select id="followup-new-assignee" value={assignee} required disabled={mutation.isPending || assignees.isFetching} onChange={event => setAssignee(event.target.value)}><option value="">Choose a staff member</option>{assignees.data?.data.items.filter(row => row.id !== item.assigned_to_id).map(row => <option key={row.id} value={row.id}>{row.display_name}</option>)}</Select>
          {assignees.isError ? <FollowupFailure error={assignees.error} retry={() => void assignees.refetch()} /> : null}
          {assignees.data ? <CanonicalPagination page={assignees.data.data.page} hasNext={assignees.data.data.has_next} onPageChange={setStaffPage} /> : null}
        </> : <><Label htmlFor="followup-action-text">{action === "edit" ? "Description" : action === "complete" ? "Completion outcome" : action === "cancel" ? "Cancellation reason" : "Activity remarks"}</Label><Textarea id="followup-action-text" maxLength={4000} value={text} required={action !== "edit"} disabled={mutation.isPending} onChange={event => setText(event.target.value)} /></>}
        {error ? <p role="alert">{error}</p> : null}
        {conflict ? <div className="space-y-2 border border-border p-3"><p>Latest saved version: {item.version}. Due {formatInstitutionalDateTime(item.due_at)}. Assigned to {item.assigned_to_name}. {statusLabel(item.status)}.</p><p className="whitespace-pre-wrap break-words">Saved description: {item.description || "None"}</p><Button variant="secondary" disabled={item.status !== "PENDING" || !confirmed} onClick={() => { setVersion(item.version); setConflict(false); setError(null); }}>I reviewed the latest details</Button></div> : null}
      </div>
      <PanelFooter><Button type="submit" disabled={mutation.isPending || conflict || !confirmed}>{mutation.isPending ? "Saving follow-up…" : consequential ? `Review ${actionLabel[action].toLowerCase()}` : "Save changes"}</Button><Button variant="secondary" disabled={mutation.isPending} onClick={onClose}>Close</Button></PanelFooter>
    </form>
    <ConsequentialActionDialog open={review} title={`${actionLabel[action]}?`} confirmLabel={actionLabel[action]} pendingLabel="Saving follow-up…" pending={mutation.isPending} error={null} variant={action === "cancel" ? "danger" : "primary"} onOpenChange={setReview} onConfirm={() => void save()}>
      <p>{action === "reassign" ? "Responsibility transfers to the selected staff member. You may lose access after reassignment." : action === "complete" ? "This follow-up will be completed with the outcome you recorded." : "This follow-up will be cancelled with the reason you recorded."} Related Counseling records, Referrals and Appointments keep their own status.</p>
    </ConsequentialActionDialog>
    <StepUpDialog open={Boolean(stepUp)} requirement={stepUp ?? "verify"} onOpenChange={open => { if (!open) setStepUp(null); }} />
  </>;
}

function FollowupHistory({ item }: { item: FollowUpDetail }) {
  const [page, setPage] = useState(1);
  const query = useGuidanceFollowupsHistory(item.id, { page }, { query: { enabled: page > 1, retry: false } });
  const events = page === 1 ? item.events : query.data?.data.items ?? [];
  const hasNext = page === 1 ? item.events_has_next : query.data?.data.has_next ?? false;
  if (page > 1 && query.isError) return <FollowupFailure error={query.error} retry={() => void query.refetch()} />;
  return (    <Panel className="mt-5"><PanelHeader title="Activity history" /><ol className="divide-y divide-border px-5">{events.map(event => <li key={event.id} className="py-3"><p className="font-semibold">{({ CREATED: "Created", UPDATED: "Updated", REASSIGNED: "Reassigned", ACTIVITY_RECORDED: "Activity recorded", COMPLETED: "Completed", CANCELLED: "Cancelled" }[event.kind] ?? "Updated")} · {event.actor_name}</p><p className="text-sm text-muted">{formatInstitutionalDateTime(event.created_at)}</p>{event.new_due_at && event.new_due_at !== event.old_due_at ? <p className="text-sm">Due {formatInstitutionalDateTime(event.new_due_at)}</p> : null}{event.remarks ? <p className="mt-2 whitespace-pre-wrap break-words">{event.remarks}</p> : null}</li>)}</ol><div className="px-5"><CanonicalPagination page={page} hasNext={hasNext && page < 100} onPageChange={setPage} /></div></Panel>);
}

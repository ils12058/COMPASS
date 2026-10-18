"use client";

import { invalidateFollowups } from "./followups-data";
import { useFollowupsFreshness, followupQueryFreshness } from "./followups-data";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useRouter } from "next/navigation";
import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { Check, ChevronDown, ClipboardPenLine } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelSection, PanelFooter } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { PageAction, PageActionGroup } from "@/components/ui/page-action";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { useGuidanceFollowupsHistory, useGuidanceFollowupsGet, useGuidanceFollowupsEligibleAssignees, guidanceFollowupsUpdate, guidanceFollowupsReassign, guidanceFollowupsRecordActivity, guidanceFollowupsComplete, guidanceFollowupsCancel, getGuidanceFollowupsGetQueryKey } from "@/lib/api/generated/guidance-followups/guidance-followups";
import { Category, type FollowUpDetail } from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/errors";
import { formatInstitutionalDateTime, isoToInstitutionalDateTimeInput, institutionalDateTimeInputToISO } from "@/lib/institutional-time";
import { followupAccess, FollowupRestricted, FollowupFailure, followupError, categoryLabel, statusLabel, sourceDestination } from "./followups-shared";

type Action = "edit" | "reschedule" | "reassign" | "activity" | "complete" | "cancel";
const actionLabel: Record<Action, string> = { edit: "Edit task details", reschedule: "Change due date", reassign: "Reassign", activity: "Record activity", complete: "Mark complete", cancel: "Cancel follow-up" };
export function FollowupsDetail({ id }: { id: string }) {
  const { user } = usePortalSession();
  const access = followupAccess(user);
  useFollowupsFreshness(access.view);
  const query = useGuidanceFollowupsGet(id, { query: { ...followupQueryFreshness, enabled: access.view, retry: false, refetchOnWindowFocus: "always" } });
  const [action, setAction] = useState<Action | null>(null);
  const statusRef = useRef<HTMLSpanElement | null>(null);
  const moreActionsRef = useRef<HTMLButtonElement | null>(null);
  const actionTriggerRef = useRef<HTMLButtonElement | null>(null);
  const restoreActionFocusRef = useRef(false);
  const item = query.data?.data;
  const cancellation = item?.events.find(event => event.kind === "CANCELLED");
  useLayoutEffect(() => {
    if (action !== null || !restoreActionFocusRef.current) return;
    const trigger = actionTriggerRef.current;
    if (trigger?.isConnected && !trigger.disabled) trigger.focus();
    else statusRef.current?.focus();
    restoreActionFocusRef.current = false;
  }, [action]);
  function beginAction(next: Action, trigger: HTMLButtonElement | null) {
    actionTriggerRef.current = trigger;
    setAction(next);
  }
  function closeAction() {
    restoreActionFocusRef.current = true;
    setAction(null);
  }
  if (!access.view) return <FollowupRestricted />;
  if (query.isPending) return <p role="status">Loading follow-up…</p>;
  if (!item || (query.error instanceof CompassApiError && [403, 404].includes(query.error.status))) return <FollowupFailure error={query.error} retry={() => void query.refetch()} />;
  return <>
    {query.isError ? <p role="alert">The latest details could not be confirmed. <Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button></p> : null}
    <PageHeader title="Follow-Up" description={item.student_name} back={<Link href="/portal/follow-ups" className={pageBackLinkClass}>Back to Follow-Ups</Link>} meta={<span ref={statusRef} tabIndex={-1} className="text-sm font-semibold">{statusLabel(item.status)}{item.overdue && item.status === "PENDING" ? " · Overdue" : ""}</span>} />
    <Panel>
      <PanelSection title="What needs to be done?" titleId="followup-description" description={categoryLabel(item.category)}>
        <p className="whitespace-pre-wrap break-words">{item.description || "No description recorded."}</p>
      </PanelSection>
      <PanelSection title="Current status and due date" titleId="followup-status-due">
        <dl className="grid gap-4 sm:grid-cols-2">
          <div><dt className="text-sm text-muted">Status</dt><dd>{statusLabel(item.status)}{item.overdue && item.status === "PENDING" ? " · Overdue" : ""}</dd></div>
          <div><dt className="text-sm text-muted">Due date and time (Philippine Time)</dt><dd>{formatInstitutionalDateTime(item.due_at)}</dd></div>
        </dl>
      </PanelSection>
      <PanelSection title="Responsible staff member" titleId="followup-assignee">
        <p>{item.assigned_to_name}</p>
      </PanelSection>
      {item.status === "COMPLETED" ? <PanelSection title="Completion outcome" titleId="followup-completion"><p className="whitespace-pre-wrap break-words">{item.outcome}</p><p className="mt-2 text-sm text-muted">Completed by {item.completed_by_name} · {item.completed_at ? formatInstitutionalDateTime(item.completed_at) : ""}</p></PanelSection> : item.status === "CANCELLED" ? <PanelSection title="Cancellation details" titleId="followup-cancellation">
        <p>Cancelled by {item.cancelled_by_name} · {item.cancelled_at ? formatInstitutionalDateTime(item.cancelled_at) : ""}</p>
        {cancellation?.remarks ? <p className="mt-2 whitespace-pre-wrap break-words">{cancellation.remarks}</p> : null}
      </PanelSection> : null}
    </Panel>
    {access.manage && item.status === "PENDING" ? <Panel className="mt-5"><PanelHeader title="Next actions" /><div className="space-y-4 p-5">
      <PageActionGroup aria-label="Primary follow-up actions">
        <PageAction icon={ClipboardPenLine} label="Record activity" variant="secondary" disabled={query.isFetching || Boolean(action)} onClick={event => beginAction("activity", event.currentTarget)} />
        <PageAction icon={Check} label="Mark complete" disabled={query.isFetching || Boolean(action)} onClick={event => beginAction("complete", event.currentTarget)} />
      </PageActionGroup>
      <DropdownMenu>
        <DropdownMenuTrigger asChild><Button ref={moreActionsRef} variant="secondary" disabled={query.isFetching || Boolean(action)}>More actions <ChevronDown aria-hidden="true" size={16} /></Button></DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuLabel className="text-xs font-semibold text-muted">Manage this follow-up</DropdownMenuLabel>
          <DropdownMenuItem onSelect={() => beginAction("edit", moreActionsRef.current)}>Edit task details</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => beginAction("reschedule", moreActionsRef.current)}>Change due date</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => beginAction("reassign", moreActionsRef.current)}>Reassign</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-danger focus:bg-danger/10 focus:text-danger" onSelect={() => beginAction("cancel", moreActionsRef.current)}>Cancel follow-up</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {action ? <FollowupActionForm item={item} confirmed={!query.isError && !query.isFetching} action={action} onClose={closeAction} /> : null}
    </div></Panel> : null}
    <FollowupHistory item={item} />
    <Panel className="mt-5">
      <PanelHeader title="Related record and additional information" />
      <PanelSection title="Access" titleId="followup-access"><p>{item.visibility === "COUNSELOR_CONFIDENTIAL" ? "Counselor-confidential" : "Operational coordination"}</p></PanelSection>
      {item.source ? <PanelSection title="Related record" titleId="followup-source"><Link className="font-semibold text-brand underline underline-offset-4" href={sourceDestination(item.source)}>Open related record</Link><p className="mt-2 text-sm text-muted">This follow-up has its own status. The related record keeps its own access rules and progress.</p></PanelSection> : item.source_unavailable ? <PanelSection title="Related record" titleId="followup-source"><p>The related record is no longer available to your account. This follow-up keeps its own status.</p></PanelSection> : <PanelSection title="Related record" titleId="followup-source"><p>This follow-up was created independently and is not linked to another Guidance record.</p></PanelSection>}
    </Panel>
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
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [review, setReview] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const continuation = useStepUpContinuation();
  const assignees = useGuidanceFollowupsEligibleAssignees({ student_id: item.student_id, category: item.category, source_kind: item.source?.kind, source_id: item.source?.id, page: staffPage }, { query: { ...followupQueryFreshness, enabled: action === "reassign", retry: false } });
  const mutation = useMutation({ mutationFn: async () => {
    const common = { expected_version: version };
    const options = { headers: { "Idempotency-Key": requestKey } };
    if (action === "edit") return guidanceFollowupsUpdate(item.id, { ...common, category, description: text }, options);
    if (action === "reschedule") {
      const at = institutionalDateTimeInputToISO(due);
      if (!at) throw new Error("Choose a valid due date.");
      return guidanceFollowupsUpdate(item.id, { ...common, due_at: at }, options);
    }
    if (action === "reassign") return guidanceFollowupsReassign(item.id, { ...common, assigned_to_id: assignee }, options);
    if (action === "activity") return guidanceFollowupsRecordActivity(item.id, { ...common, remarks: text }, options);
    if (action === "complete") return guidanceFollowupsComplete(item.id, { ...common, outcome: text }, options);
    return guidanceFollowupsCancel(item.id, { ...common, reason: text }, options);
  } });
  useUnsavedChangesGuard({ dirty: !mutation.isSuccess && Boolean(text || assignee || due !== isoToInstitutionalDateTimeInput(item.due_at)), message: "Your follow-up changes have not been saved." });
  async function save() {
    setError(null);
    const result = await continuation.run(() => mutation.mutateAsync(), {
      onStepUpRequired: () => setReview(false),
      onFailure: (caught) => {
      if (caught instanceof CompassApiError && caught.status === 409) {
        setConflict(true);
        void client.invalidateQueries({ queryKey: getGuidanceFollowupsGetQueryKey(item.id) });
      }
      setError(followupError(caught));
      },
    });
    if (!result) return;
    await invalidateFollowups(client);
    if (action === "reassign" && result.data.assigned_to_id !== item.assigned_to_id) router.push("/portal/follow-ups");
    else { client.setQueryData(getGuidanceFollowupsGetQueryKey(item.id), result); onClose(); }
  }
  const consequential = ["complete", "cancel", "reassign"].includes(action);
  function submit(event: FormEvent) { event.preventDefault(); if (consequential) setReview(true); else void save(); }
  return <>
    <form onSubmit={submit}>
      <div className="space-y-4 p-5"><h3 className="font-semibold">{actionLabel[action]}</h3>
        {action === "edit" ? <><Label htmlFor="followup-edit-category">Category</Label><Select id="followup-edit-category" value={category} onChange={event => { setCategory(event.target.value as Category); setRequestKey(crypto.randomUUID()); }} disabled={mutation.isPending}>{(item.visibility === "COUNSELOR_CONFIDENTIAL" || item.source?.kind === "REFERRAL" ? [item.category] : [Category.ADMINISTRATIVE, Category.STUDENT_CONTACT, Category.REFERRAL_ACTION]).map(value => <option key={value} value={value}>{categoryLabel(value)}</option>)}</Select></> : null}
        {action === "reschedule" ? <><Label htmlFor="followup-new-due">New due date and time (Philippine Time)</Label><Input id="followup-new-due" type="datetime-local" value={due} required disabled={mutation.isPending} onChange={event => { setDue(event.target.value); setRequestKey(crypto.randomUUID()); }} /></> : action === "reassign" ? <>
          <Label htmlFor="followup-new-assignee">Responsible staff member</Label><Select id="followup-new-assignee" value={assignee} required disabled={mutation.isPending || assignees.isFetching} onChange={event => { setAssignee(event.target.value); setRequestKey(crypto.randomUUID()); }}><option value="">Choose a staff member</option>{assignees.data?.data.items.filter(row => row.id !== item.assigned_to_id).map(row => <option key={row.id} value={row.id}>{row.display_name}</option>)}</Select>
          {assignees.isError ? <FollowupFailure error={assignees.error} retry={() => void assignees.refetch()} /> : null}
          {assignees.data ? <CanonicalPagination page={assignees.data.data.page} hasNext={assignees.data.data.has_next} onPageChange={setStaffPage} /> : null}
        </> : <><Label htmlFor="followup-action-text">{action === "edit" ? "Task description" : action === "complete" ? "Completion outcome" : action === "cancel" ? "Cancellation reason" : "Activity or update"}</Label><Textarea id="followup-action-text" maxLength={4000} value={text} required={action !== "edit"} disabled={mutation.isPending} onChange={event => { setText(event.target.value); setRequestKey(crypto.randomUUID()); }} />{action === "activity" ? <p className="text-sm text-muted">Record an action or update. This follow-up will remain Pending.</p> : action === "complete" ? <p className="text-sm text-muted">Record what was accomplished, then mark this follow-up as completed.</p> : null}</>}
        {error ? <p role="alert">{error}</p> : continuation.notice ? <p role="status" className="text-sm text-muted">{continuation.notice}</p> : null}
        {conflict ? <div className="space-y-2 border border-border p-3"><p>Latest saved version: {item.version}. Due {formatInstitutionalDateTime(item.due_at)}. Assigned to {item.assigned_to_name}. {statusLabel(item.status)}.</p><p className="whitespace-pre-wrap break-words">Saved description: {item.description || "None"}</p><Button variant="secondary" disabled={item.status !== "PENDING" || !confirmed} onClick={() => { setVersion(item.version); setRequestKey(crypto.randomUUID()); setConflict(false); setError(null); }}>I reviewed the latest details</Button></div> : null}
      </div>
      <PanelFooter><Button type="submit" disabled={mutation.isPending || conflict || !confirmed}>{mutation.isPending ? "Saving follow-up…" : consequential ? `Review ${actionLabel[action].toLowerCase()}` : "Save changes"}</Button><Button variant="secondary" disabled={mutation.isPending} onClick={onClose}>Close</Button></PanelFooter>
    </form>
    <ConsequentialActionDialog open={review} title={`${actionLabel[action]}?`} confirmLabel={actionLabel[action]} pendingLabel="Saving follow-up…" pending={mutation.isPending} error={null} variant={action === "cancel" ? "danger" : "primary"} onOpenChange={setReview} onConfirm={() => void save()}>
      <p>{action === "reassign" ? "Responsibility transfers to the selected staff member. You may lose access after reassignment." : action === "complete" ? "This follow-up will be completed with the outcome you recorded." : "This follow-up will be cancelled with the reason you recorded."} Related Counseling records, Referrals and Appointments keep their own status.</p>
    </ConsequentialActionDialog>
    <StepUpDialog open={continuation.open} requirement={continuation.requirement} onOpenChange={(open) => { continuation.setOpen(open); if (!open) setError(null); }} isContinuing={continuation.isContinuing} onVerified={continuation.continueAfterVerification} />
  </>;
}

function FollowupHistory({ item }: { item: FollowUpDetail }) {
  const [page, setPage] = useState(1);
  const query = useGuidanceFollowupsHistory(item.id, { page }, { query: { ...followupQueryFreshness, enabled: page > 1, retry: false } });
  const events = page === 1 ? item.events : query.data?.data.items ?? [];
  const hasNext = page === 1 ? item.events_has_next : query.data?.data.has_next ?? false;
  if (page > 1 && query.isError) return <FollowupFailure error={query.error} retry={() => void query.refetch()} />;
  return <Panel className="mt-5"><PanelHeader title="Activity history" description="Events are listed in the order they happened." />{events.length ? <ol className="divide-y divide-border px-5">{events.map(event => {
    const dueChanged = event.kind === "UPDATED" && event.old_due_at && event.new_due_at && event.old_due_at !== event.new_due_at;
    const title = dueChanged ? "Due date changed" : ({ CREATED: "Created", UPDATED: "Updated", REASSIGNED: "Reassigned", ACTIVITY_RECORDED: "Activity recorded", COMPLETED: "Completed", CANCELLED: "Cancelled" }[event.kind] ?? "Updated");
    return <li key={event.id} className="py-3"><p className="font-semibold">{title} · {event.actor_name}</p><p className="text-sm text-muted">{formatInstitutionalDateTime(event.created_at)}</p>{event.new_due_at && event.new_due_at !== event.old_due_at ? <p className="text-sm">Due {formatInstitutionalDateTime(event.new_due_at)}</p> : null}{event.remarks ? <p className="mt-2 whitespace-pre-wrap break-words">{event.remarks}</p> : null}</li>;
  })}</ol> : <p className="p-5 text-sm text-muted">No activity has been recorded yet.</p>}<div className="px-5"><CanonicalPagination page={page} hasNext={hasNext && page < 100} onPageChange={setPage} /></div></Panel>;
}

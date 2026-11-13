"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { stepUpRequirement, type StepUpRequirement } from "@/features/account/security/step-up";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { enumChoice } from "@/features/counseling/continuity/continuity-presentation";
import { closureError, closureRequiresReview } from "@/features/counseling/cases/closure-presentation";
import { useGuidanceFollowupsEligibleAssignees } from "@/lib/api/generated/guidance-followups/guidance-followups";
import { useCounselingDesignateCaseTaskAfterClosure } from "@/lib/api/generated/counseling/counseling";
import { SourceKind, type CaseClosureTask, type CaseClosureContextResponse, type CounselingCaseDetailResponse } from "@/lib/api/generated/model";
import { institutionalDateTimeInputToISO, isoToInstitutionalDateTimeInput } from "@/lib/institutional-time";
import { focusHeading } from "@/lib/focus-heading";

const textLink = "font-semibold text-brand underline underline-offset-4";

export function AfterClosureTask({ task, item, context, here, onSaved }: { task: CaseClosureTask; item: CounselingCaseDetailResponse; context: CaseClosureContextResponse; here: string; onSaved: (next: CounselingCaseDetailResponse) => Promise<unknown> }) {
  const [editing, setEditing] = useState(false);
  const [owner, setOwner] = useState(task.assigned_to_id);
  const [due, setDue] = useState(isoToInstitutionalDateTimeInput(task.due_at) ?? "");
  const [administrative, setAdministrative] = useState(false);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [requirement, setRequirement] = useState<StepUpRequirement>("verify");
  const mutation = useCounselingDesignateCaseTaskAfterClosure({ mutation: { retry: false } });
  const assignees = useGuidanceFollowupsEligibleAssignees({ student_id: task.student_id, category: "COUNSELING", case_id: item.id, source_kind: enumChoice(Object.values(SourceKind), task.source_kind ?? ""), source_id: task.source_id ?? undefined, page }, { query: { enabled: editing, retry: false } });
  useUnsavedChangesGuard({ dirty: editing && (administrative || owner !== task.assigned_to_id || due !== isoToInstitutionalDateTimeInput(task.due_at)), message: "Leave this after-closure action plan and discard unsaved changes?" });
  async function save(event: FormEvent) {
    event.preventDefault();
    if (mutation.isPending) return;
    const dueAt = institutionalDateTimeInputToISO(due);
    if (!administrative || !owner || !dueAt) { setError("Confirm an administrative action and choose its owner and due date."); return; }
    setError(null);
    try {
      const response = await mutation.mutateAsync({ caseId: item.id, taskId: task.id, data: { expected_version: context.version, expected_task_version: task.version, administrative_action: true, assigned_to_id: owner, due_at: dueAt } });
      setEditing(false);
      setAdministrative(false);
      await onSaved(response.data);
      focusHeading("close-outstanding-heading");
    } catch (caught) {
      const nextRequirement = stepUpRequirement(caught);
      if (nextRequirement) { setRequirement(nextRequirement); setStepUpOpen(true); }
      else { setError(closureError(caught)); if (closureRequiresReview(caught)) await onSaved(item); }
    }
  }
  return <li className="py-4 text-sm">
    <p className="break-words font-semibold">{task.title ?? "Counseling action"}</p>
    <p className="mt-1">{task.assigned_to_name} · Due {formatCounselingDateTime(task.due_at)}{task.post_closure_designated_at ? " · After closure" : ""}</p>
    <div className="mt-2 flex flex-wrap items-center gap-3">
      <Link className={textLink} href={withWorkflowReturn(`/portal/follow-ups/${task.id}`, here)}>Complete or cancel action</Link>
      {task.can_designate && !editing ? <Button type="button" variant="secondary" onClick={() => setEditing(true)}>{task.post_closure_designated_at ? "Edit after-closure plan" : "Keep after closure"}</Button> : null}
    </div>
    {editing ? <form onSubmit={event => void save(event)} className="mt-4 grid gap-3">
      <label className="flex items-start gap-2"><input className="mt-1 h-4 w-4 accent-brand" type="checkbox" checked={administrative} required disabled={mutation.isPending} onChange={event => setAdministrative(event.target.checked)} /><span>This is an administrative action to keep after closure.</span></label>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1"><Label htmlFor={`closure-owner-${task.id}`}>Owner after closure</Label><Select id={`closure-owner-${task.id}`} required value={owner} disabled={mutation.isPending || assignees.isFetching} onChange={event => setOwner(event.target.value)}><option value={task.assigned_to_id}>{task.assigned_to_name}</option>{assignees.data?.data.items.filter(person => person.id !== task.assigned_to_id).map(person => <option key={person.id} value={person.id}>{person.display_name}</option>)}</Select>{assignees.isError ? <p role="alert">Owner options couldn&apos;t be confirmed. <Button type="button" variant="quiet" onClick={() => void assignees.refetch()}>Retry</Button></p> : null}{assignees.data ? <CanonicalPagination page={assignees.data.data.page} hasNext={assignees.data.data.has_next} onPageChange={setPage} /> : null}</div>
        <div className="grid gap-1"><Label htmlFor={`closure-due-${task.id}`}>Due (Philippine Time)</Label><Input id={`closure-due-${task.id}`} type="datetime-local" required value={due} disabled={mutation.isPending} onChange={event => setDue(event.target.value)} /></div>
      </div>
      {error ? <p role="alert" className="text-danger">{error}</p> : null}
      <div className="flex flex-wrap gap-2"><Button type="submit" disabled={mutation.isPending || assignees.isFetching || assignees.isError}>{mutation.isPending ? "Saving after-closure plan…" : "Save after-closure plan"}</Button><Button type="button" variant="secondary" disabled={mutation.isPending} onClick={() => { setEditing(false); setAdministrative(false); }}>Cancel plan</Button></div>
    </form> : null}
    <StepUpDialog open={stepUpOpen} requirement={requirement} onOpenChange={setStepUpOpen} onVerified={() => { setStepUpOpen(false); setError("Authenticator verified. Review and save the after-closure plan again."); }} />
  </li>;
}


"use client";

import { invalidateFollowups } from "./followups-data";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useSearchParams, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelSection, PanelFooter } from "@/components/ui/panel";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { stepUpRequirement, type StepUpRequirement } from "@/features/account/security/step-up";
import { guidanceFollowupsCreate, useGuidanceFollowupsGetContext, useGuidanceFollowupsEligibleStudents, useGuidanceFollowupsEligibleAssignees } from "@/lib/api/generated/guidance-followups/guidance-followups";
import { CompassApiError } from "@/lib/api/errors";
import { Category, SourceKind, type FollowUpCreate, type SourceContext } from "@/lib/api/generated/model";
import { institutionalDateTimeInputToISO } from "@/lib/institutional-time";
import { followupAccess, FollowupRestricted, FollowupFailure, followupError, categoryLabel } from "./followups-shared";

export function FollowupsCreate() {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const sourceKind = params.get("source_kind");
  const sourceId = params.get("source_id");
  const initialStudentId = params.get("student_id") ?? undefined;
  const initialStudentName = params.get("student_name") ?? undefined;
  const hasSource = Boolean(sourceKind || sourceId);
  const validSource = Object.values(SourceKind).includes(sourceKind as SourceKind) && Boolean(sourceId);
  const context = useGuidanceFollowupsGetContext({ source_kind: sourceKind as SourceKind, source_id: sourceId ?? "" }, { query: { enabled: followupAccess(user).manage && hasSource && validSource, retry: false } });
  if (!followupAccess(user).manage) return <FollowupRestricted />;
  if (hasSource && !validSource) return <FollowupFailure error={null} />;
  if (hasSource && context.isPending) return <p role="status">Checking the related record…</p>;
  if (hasSource && (context.isError || !context.data?.data.can_create)) return <FollowupFailure error={context.error} />;
  return <CreateForm source={hasSource ? context.data?.data : undefined} initialStudentId={initialStudentId} initialStudentName={initialStudentName} />;
}

type Source = SourceContext;
function CreateForm({ source, initialStudentId, initialStudentName }: { source?: Source; initialStudentId?: string; initialStudentName?: string }) {
  const { user } = usePortalSession();
  const router = useRouter();
  const client = useQueryClient();
  const [studentId, setStudentId] = useState(source?.student_id ?? initialStudentId ?? "");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [assigneePage, setAssigneePage] = useState(1);
  const [category, setCategory] = useState<Category>(source?.category ?? Category.ADMINISTRATIVE);
  const [assignee, setAssignee] = useState("");
  const [due, setDue] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState<StepUpRequirement | null>(null);
  const [submission, setSubmission] = useState<{ data: FollowUpCreate; key: string } | null>(null);
  const create = useMutation({ mutationFn: (value: { data: FollowUpCreate; key: string }) => guidanceFollowupsCreate(value.data, { headers: { "Idempotency-Key": value.key } }) });
  const students = useGuidanceFollowupsEligibleStudents({ search, page }, { query: { enabled: !source } });
  const assignees = useGuidanceFollowupsEligibleAssignees({ student_id: studentId, category, source_kind: source?.source_kind, source_id: source?.source_id, page: assigneePage }, { query: { enabled: Boolean(studentId), retry: false } });
  useUnsavedChangesGuard({ dirty: !create.isSuccess && Boolean(description || due || studentId && !source), message: "Your follow-up has not been saved." });
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(null);
    const dueAt = institutionalDateTimeInputToISO(due);
    if (!studentId || !assignee || !dueAt) { setError("Choose a Student, responsible staff member and due date."); return; }
    const value = submission ?? { key: crypto.randomUUID(), data: { student_id: studentId, assigned_to_id: assignee, category, due_at: dueAt, description: description || null, source_kind: source?.source_kind, source_id: source?.source_id } };
    setSubmission(value);
    try {
      const response = await create.mutateAsync(value);
      await invalidateFollowups(client);
      router.push(response.data.assigned_to_id === user.id ? `/portal/follow-ups/${response.data.id}` : "/portal/follow-ups");
    } catch (caught) {
      const requirement = stepUpRequirement(caught);
      if (requirement) { setStepUp(requirement); setSubmission(null); }
      else { if (caught instanceof CompassApiError && caught.status === 422) setSubmission(null); setError(followupError(caught)); }
    }
  }
  return <>
    <PageHeader title="Create follow-up" description="An internal Guidance follow-up. Students do not receive these notifications." back={<Link className={pageBackLinkClass} href="/portal/follow-ups">Back to Follow-Ups</Link>} />
    <form onSubmit={event => void submit(event)}><Panel>
      <PanelSection title="Student and purpose" titleId="followup-purpose">
        {source ? <p>{source.student_name} · Related record verified. {source.visibility === "COUNSELOR_CONFIDENTIAL" ? "Counselor-confidential" : "Operational coordination"}.</p> : <>
          <Label htmlFor="followup-student-search">Find a Student</Label><Input id="followup-student-search" value={search} disabled={Boolean(submission)} onChange={event => { setSearch(event.target.value); setPage(1); setStudentId(""); setAssignee(""); }} />
          {students.isPending ? <p role="status">Loading Students…</p> : students.isError ? <FollowupFailure error={students.error} retry={() => void students.refetch()} /> : <>
            <Label htmlFor="followup-student">Student</Label><Select id="followup-student" required value={studentId} disabled={Boolean(submission)} onChange={event => { setStudentId(event.target.value); setAssignee(""); setAssigneePage(1); }}>
              <option value="">Choose a Student</option>
              {studentId && !students.data?.data.items.some(row => row.id === studentId) ? (
                <option value={studentId}>{initialStudentName || `Selected Student (${studentId.slice(0, 8)}…)`}</option>
              ) : null}
              {students.data?.data.items.map(row => <option key={row.id} value={row.id}>{row.display_name}{row.institutional_id ? ` · ${row.institutional_id}` : ""}</option>)}
            </Select>
            {students.data ? <CanonicalPagination page={students.data.data.page} hasNext={students.data.data.has_next} onPageChange={page => { setPage(page); setStudentId(""); setAssignee(""); }} /> : null}
          </>}
        </>}
        <div className="mt-4"><Label htmlFor="followup-category">Category</Label><Select id="followup-category" value={category} disabled={Boolean(source || submission)} onChange={event => { setCategory(event.target.value as Category); setAssignee(""); }}>
          {(source ? [source.category] : [Category.ADMINISTRATIVE, Category.STUDENT_CONTACT, Category.REFERRAL_ACTION]).map(value => <option key={value} value={value}>{categoryLabel(value)}</option>)}
        </Select></div>
      </PanelSection>
      <PanelSection title="Responsibility and due date" titleId="followup-responsibility">
        <Label htmlFor="followup-assignee">Responsible staff member</Label><Select id="followup-assignee" required value={assignee} disabled={!studentId || Boolean(submission) || assignees.isFetching} onChange={event => setAssignee(event.target.value)}><option value="">Choose a staff member</option>{assignees.data?.data.items.map(row => <option key={row.id} value={row.id}>{row.display_name}</option>)}</Select>
        {assignees.isError ? <FollowupFailure error={assignees.error} retry={() => void assignees.refetch()} /> : null}
        {assignees.data ? <CanonicalPagination label="Staff pages" page={assignees.data.data.page} hasNext={assignees.data.data.has_next} onPageChange={page => { setAssigneePage(page); setAssignee(""); }} /> : null}
        <div className="mt-4"><Label htmlFor="followup-due">Due date and time (Philippine Time)</Label><Input id="followup-due" type="datetime-local" required value={due} disabled={Boolean(submission)} onChange={event => setDue(event.target.value)} /></div>
      </PanelSection>
      <PanelSection title="Description" titleId="followup-description-section"><Label htmlFor="followup-description">Follow-up description (optional)</Label><Textarea id="followup-description" maxLength={4000} value={description} disabled={Boolean(submission)} onChange={event => setDescription(event.target.value)} /><p className="mt-2 text-sm text-muted">Include only information needed for this follow-up. The description is protected.</p></PanelSection>
      <PanelFooter><Button type="submit" disabled={create.isPending || assignees.isFetching}>{create.isPending ? "Creating follow-up…" : submission ? "Retry the same follow-up" : "Create follow-up"}</Button>{error ? <p role="alert">{error} Return to Follow-Ups to check the saved record before starting another request.</p> : null}</PanelFooter>
    </Panel></form>
    <StepUpDialog open={Boolean(stepUp)} requirement={stepUp ?? "verify"} onOpenChange={open => { if (!open) setStepUp(null); }} />
  </>;
}

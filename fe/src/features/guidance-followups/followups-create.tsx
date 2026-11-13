"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelSection, PanelFooter, PanelMessage } from "@/components/ui/panel";
import { LoadingRegion } from "@/components/ui/loading-region";
import { FollowupsHelp } from "./followups-help";
import { invalidateFollowups } from "./followups-data";
import { followupAccess, FollowupRestricted, FollowupFailure, followupError, categoryLabel } from "./followups-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { portalReturnHref, withWorkflowReturn, workflowBackLabel } from "@/features/portal/workflow-navigation";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import {
  guidanceFollowupsCreate, useGuidanceFollowupsGet, useGuidanceFollowupsGetContext,
  useGuidanceFollowupsEligibleStudents, useGuidanceFollowupsEligibleAssignees,
} from "@/lib/api/generated/guidance-followups/guidance-followups";
import { useProtectedCase } from "@/features/counseling/cases/use-protected-case";
import { CompassApiError } from "@/lib/api/errors";
import {
  Category, SourceKind, type FollowUpCreate, type FollowUpDetail,
  type SourceContext, type FollowUpCaseReference, type StudentOption,
} from "@/lib/api/generated/model";
import { institutionalDateTimeInputToISO } from "@/lib/institutional-time";

export function FollowupsCreate() {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const access = followupAccess(user);
  const predecessorId = params.get("predecessor_id");
  const caseId = params.get("case_id");
  const predecessor = useGuidanceFollowupsGet(predecessorId ?? "", {
    query: { enabled: access.manage && Boolean(predecessorId), retry: false },
  });
  const previous = predecessor.data?.data;
  const rawKind = previous ? previous.source?.kind : params.get("source_kind");
  const sourceId = previous ? previous.source?.id : params.get("source_id");
  const sourceKind = Object.values(SourceKind).find(value => value === rawKind);
  const hasSource = Boolean(rawKind || sourceId);
  const validSource = Boolean(sourceKind && sourceId);
  const source = useGuidanceFollowupsGetContext({
    source_kind: sourceKind ?? SourceKind.COUNSELING_ENCOUNTER, source_id: sourceId ?? "",
  }, { query: { enabled: access.manage && validSource && (!predecessorId || predecessor.isSuccess), retry: false } });
  const caseQuery = useProtectedCase(caseId ?? "", access.manage && Boolean(caseId));
  if (!access.manage) return <FollowupRestricted />;
  if (caseId && caseQuery.privacy.blocked) return <FollowupFailure error={caseQuery.failure} retry={() => caseQuery.privacy.resume()} />;
  if ((predecessorId && predecessor.isPending) || (caseId && caseQuery.isPending) || (hasSource && validSource && source.isPending)) {
    return <LoadingRegion label="Checking next-action context"><Panel><PanelMessage>Checking the related work…</PanelMessage></Panel></LoadingRegion>;
  }
  if (predecessorId && (predecessor.isError || !previous?.can_create_next_action)) {
    return <FollowupFailure error={predecessor.error} />;
  }
  if (caseId && (caseQuery.isError || !caseQuery.data?.data.can_add_next_action)) {
    return <FollowupFailure error={caseQuery.error} retry={() => void caseQuery.refetch()} />;
  }
  if (hasSource && (!validSource || source.isError || !source.data?.data.can_create)) {
    return <FollowupFailure error={source.error} retry={validSource ? () => void source.refetch() : undefined} />;
  }
  const context = hasSource ? source.data?.data : undefined;
  const caseItem = caseQuery.data?.data;
  const caseChoice = previous ? previous.case : caseItem ? {
    id: caseItem.id, reference_code: caseItem.reference_code, status: caseItem.status,
  } : context?.case;
  const fixedStudent = previous ? { id: previous.student_id, display_name: previous.student_name }
    : caseItem ? caseItem.student : undefined;
  return <CreateForm source={context} predecessor={previous} caseChoice={caseChoice ?? undefined}
    fixedStudent={fixedStudent} initialStudentId={params.get("student_id") ?? undefined}
    returnTo={portalReturnHref(params.get("return_to"), "/portal/follow-ups")} />;
}

function CreateForm({ source, predecessor, caseChoice, fixedStudent, initialStudentId, returnTo }: {
  source?: SourceContext;
  predecessor?: FollowUpDetail;
  caseChoice?: FollowUpCaseReference;
  fixedStudent?: Pick<StudentOption, "id" | "display_name">;
  initialStudentId?: string;
  returnTo: string;
}) {
  const { user } = usePortalSession();
  const router = useRouter();
  const client = useQueryClient();
  const initialCategory = predecessor?.category ?? source?.category ?? (caseChoice ? Category.COUNSELING : Category.ADMINISTRATIVE);
  const fixed = Boolean(source || fixedStudent);
  const [studentId, setStudentId] = useState(fixedStudent?.id ?? source?.student_id ?? initialStudentId ?? "");
  const [selectedCase, setSelectedCase] = useState(caseChoice?.id ?? "");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [assigneePage, setAssigneePage] = useState(1);
  const [category, setCategory] = useState<Category>(initialCategory);
  const [assignee, setAssignee] = useState("");
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const continuation = useStepUpContinuation();
  const [submission, setSubmission] = useState<{ data: FollowUpCreate; key: string } | null>(null);
  const create = useMutation({
    mutationFn: (value: { data: FollowUpCreate; key: string }) => guidanceFollowupsCreate(value.data, { headers: { "Idempotency-Key": value.key } }),
    retry: false,
  });
  const students = useGuidanceFollowupsEligibleStudents({ search, page }, { query: { enabled: !fixed, retry: false } });
  const assignees = useGuidanceFollowupsEligibleAssignees({
    student_id: studentId, category, source_kind: source?.source_kind,
    source_id: source?.source_id, case_id: selectedCase || undefined, page: assigneePage,
  }, { query: { enabled: Boolean(studentId), retry: false } });
  useUnsavedChangesGuard({
    dirty: !create.isSuccess && Boolean(title || description || due || assignee || (!fixed && studentId) || category !== initialCategory || selectedCase !== (caseChoice?.id ?? "")),
    message: "Your Follow-Up has not been saved.",
  });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (create.isPending) return;
    setError(null);
    const dueAt = institutionalDateTimeInputToISO(due);
    if (!studentId || !assignee || !dueAt || !title.trim()) {
      setError("Enter an action title and choose a Student, responsible staff member and due date.");
      return;
    }
    const value = submission ?? {
      key: crypto.randomUUID(), data: {
        student_id: studentId, assigned_to_id: assignee, category, title, due_at: dueAt,
        description: description || null, source_kind: source?.source_kind,
        source_id: source?.source_id, case_id: selectedCase || null,
        predecessor_id: predecessor?.id ?? null,
      },
    };
    setSubmission(value);
    const response = await continuation.run(() => create.mutateAsync(value), {
      onFailure: caught => {
        if (caught instanceof CompassApiError && caught.status === 422) setSubmission(null);
        setError(followupError(caught));
      },
    });
    if (!response) return;
    await invalidateFollowups(client);
    router.push(response.data.assigned_to_id === user.id
      ? withWorkflowReturn(`/portal/follow-ups/${response.data.id}`, returnTo) : returnTo);
  }

  const locked = Boolean(submission);
  return <>
    <PageHeader help={<FollowupsHelp />} title="Create Follow-Up"
      description="Creating a task does not book an appointment or contact the Student."
      back={<Link className={pageBackLinkClass} href={returnTo}>{workflowBackLabel(returnTo)}</Link>} />
    <form onSubmit={event => void submit(event)}><Panel>
      <PanelSection title="What needs to be done?" titleId="followup-purpose">
        <div><Label htmlFor="followup-title">Action title</Label><Input id="followup-title" maxLength={120} required value={title} disabled={locked} onChange={event => setTitle(event.target.value)} /></div>
        <div className="mt-4"><Label htmlFor="followup-category">Category</Label><Select id="followup-category" value={category} disabled={Boolean(source || caseChoice || predecessor || locked)} onChange={event => {
          const value = Object.values(Category).find(value => value === event.target.value);
          if (value) { setCategory(value); setAssignee(""); }
        }}>
          {(source || caseChoice || predecessor ? [initialCategory] : [Category.ADMINISTRATIVE, Category.STUDENT_CONTACT, Category.REFERRAL_ACTION]).map(value => <option key={value} value={value}>{categoryLabel(value)}</option>)}
        </Select></div>
        <div className="mt-4"><Label htmlFor="followup-description">Task description (optional)</Label><Textarea id="followup-description" maxLength={4000} value={description} disabled={locked} onChange={event => setDescription(event.target.value)} /></div>
        {caseChoice ? <div className="mt-4"><Label htmlFor="followup-case">Linked case{source && !predecessor ? " (optional)" : ""}</Label>
          <Select id="followup-case" value={selectedCase} disabled={!source || Boolean(predecessor) || locked} onChange={event => { setSelectedCase(event.target.value); setAssignee(""); setAssigneePage(1); }}>
            {source && !predecessor ? <option value="">No case link</option> : null}
            <option value={caseChoice.id}>Case {caseChoice.reference_code}</option>
          </Select>
        </div> : null}
        {predecessor ? <p className="mt-3 text-sm text-muted">This new action continues the preceding task for the same Student{caseChoice ? " and case" : ""}.</p> : null}
      </PanelSection>
      <PanelSection title="Student" titleId="followup-student-section">
        {fixed ? <div>
          <p className="font-semibold">{fixedStudent?.display_name ?? source?.student_name}</p>
          <p className="mt-1 text-sm text-muted">{category === Category.COUNSELING ? "Counselor-confidential" : "Staff coordination"}</p>
        </div> : <>
          <Label htmlFor="followup-student-search">Find a Student</Label><Input id="followup-student-search" placeholder="Search by name or institutional ID" value={search} disabled={locked} onChange={event => { setSearch(event.target.value); setPage(1); setStudentId(""); setAssignee(""); }} />
          {students.isPending ? <p role="status">Loading Students…</p> : students.isError ? <FollowupFailure error={students.error} retry={() => void students.refetch()} /> : <>
            <Label htmlFor="followup-student">Student</Label><Select id="followup-student" required value={studentId} disabled={locked} onChange={event => { setStudentId(event.target.value); setAssignee(""); setAssigneePage(1); }}>
              <option value="">Choose a Student</option>
              {students.data?.data.items.map(row => <option key={row.id} value={row.id}>{row.display_name}{row.institutional_id ? ` · ${row.institutional_id}` : ""}</option>)}
            </Select>
            {students.data ? <CanonicalPagination page={students.data.data.page} hasNext={students.data.data.has_next} onPageChange={setPage} /> : null}
          </>}
        </>}
      </PanelSection>
      <PanelSection title="Responsibility and deadline" titleId="followup-responsibility">
        <Label htmlFor="followup-assignee">Responsible staff member</Label><Select id="followup-assignee" required value={assignee} disabled={locked || assignees.isFetching || !studentId} onChange={event => setAssignee(event.target.value)}>
          <option value="">Choose a staff member</option>{assignees.data?.data.items.map(row => <option key={row.id} value={row.id}>{row.display_name}</option>)}
        </Select>
        {assignees.isError ? <FollowupFailure error={assignees.error} retry={() => void assignees.refetch()} /> : null}
        {assignees.data ? <CanonicalPagination page={assignees.data.data.page} hasNext={assignees.data.data.has_next} onPageChange={setAssigneePage} /> : null}
        <div className="mt-4"><Label htmlFor="followup-due">Due date and time (Philippine Time)</Label><Input id="followup-due" type="datetime-local" required value={due} disabled={locked} onChange={event => setDue(event.target.value)} /></div>
      </PanelSection>
      <PanelFooter>
        {error ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : continuation.notice ? <p role="status" className="w-full text-sm text-muted">{continuation.notice}</p> : null}
        <Button type="submit" disabled={create.isPending || assignees.isFetching}>{create.isPending ? "Creating Follow-Up…" : submission ? "Retry same submission" : "Create Follow-Up"}</Button>
      </PanelFooter>
    </Panel></form>
    <StepUpDialog open={continuation.open} requirement={continuation.requirement} onOpenChange={(open) => { continuation.setOpen(open); if (!open) setError(null); }} isContinuing={continuation.isContinuing} onVerified={continuation.continueAfterVerification} />
  </>;
}

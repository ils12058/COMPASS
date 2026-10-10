"use client";

import { useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { focusHeading } from "@/lib/focus-heading";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Panel, PanelSection, PanelFooter } from "@/components/ui/panel";
import { EligibleStudentPicker, type EligibleStudentOption } from "@/features/portal/components/eligible-student-picker";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { exitInterviewErrorMessage } from "@/features/exit-interviews/exit-interview-shared";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import {
  exitInterviewsOpenOpportunity, useExitInterviewsListEligibleStudents,
  useExitInterviewsListOpportunities,
} from "@/lib/api/generated/exit-interviews/exit-interviews";
import type { ExitInterviewOpenOpportunityRequest } from "@/lib/api/generated/model";
import { ExitInterviewOpportunitySourceValue } from "@/lib/api/generated/model";

export function ExitInterviewOpportunityOpening({ onDone, onOpened }: { onDone: () => void; onOpened: () => void }) {
  const { user } = usePortalSession();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [student, setStudent] = useState<EligibleStudentOption | null>(null);
  const [yearId, setYearId] = useState("");
  const [source, setSource] = useState<ExitInterviewOpenOpportunityRequest["source"]>("GRADUATION");
  const [note, setNote] = useState("");
  const [review, setReview] = useState<ExitInterviewOpenOpportunityRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);
  const discarded = useRef(false);
  const dirty = !completed && (student !== null || Boolean(yearId) || source !== "GRADUATION" || Boolean(note.trim()));
  useUnsavedChangesGuard({ dirty, message: "Discard your unsaved Exit Interview access opening?" });
  const canReadYears = user.capabilities.includes("academic_years.view");
  const years = useAcademicYearsList({ query: { enabled: canReadYears, retry: false } });
  const students = useExitInterviewsListEligibleStudents({ search: query || undefined, page }, { query: { retry: false } });
  const opportunities = useExitInterviewsListOpportunities({ student_id: student?.id, academic_year_id: yearId || undefined, current_year_only: !yearId }, { query: { enabled: student !== null, retry: false } });
  const opening = useMutation({ mutationFn: (payload: ExitInterviewOpenOpportunityRequest) => exitInterviewsOpenOpportunity(payload), retry: false });
  const year = yearId ? years.data?.data.items.find((item) => item.id === yearId) : opportunities.data?.data.current_academic_year ?? years.data?.data.items.find((item) => item.is_current);
  const existing = opportunities.data?.data.items.find((item) => item.academic_year.id === year?.id);
  const effectiveSource = existing?.source ?? source;
  const ready = student !== null && Boolean(year) && opportunities.isSuccess && !opportunities.isFetching && (!canReadYears || years.isSuccess) && (!existing || existing.status === "REVOKED");

  function reviewOpening(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready || !student) return;
    setError(null);
    setReview({ student_id: student.id, academic_year_id: yearId || null, source: effectiveSource, note: note.trim() });
  }

  async function confirm() {
    if (!review) return;
    setError(null);
    try {
      await opening.mutateAsync(review);
      setCompleted(true);
      onOpened();
    } catch (caught) {
      setError(exitInterviewErrorMessage(caught, "Exit Interview access could not be opened. Review the Student and Academic Year, then try again."));
      void opportunities.refetch();
    }
  }

  return <>
    <Panel>
      <PanelSection title="Open Exit Interview access" titleId="exit-opportunity-opening">
        <EligibleStudentPicker search={search} onSearchChange={setSearch} onSearch={() => { setQuery(search.trim()); setPage(1); }} items={students.data?.data.items ?? []} selectedStudent={student} selectedId={student?.id ?? null} onSelect={setStudent} page={students.data?.data.page ?? page} hasNext={students.data?.data.has_next ?? false} isLoading={students.isPending} isError={students.isError} errorMessage={exitInterviewErrorMessage(students.error, "Students could not be loaded.")} onRetry={() => void students.refetch()} onPageChange={setPage} />
      </PanelSection>
      <form onSubmit={reviewOpening}>
        <PanelSection title="Opening details" titleId="exit-opportunity-opening-details">
          <div className="grid gap-5 sm:grid-cols-2">
            <div><Label htmlFor="exit-opportunity-year">Academic Year</Label><Select id="exit-opportunity-year" value={yearId} onChange={(event) => setYearId(event.target.value)} disabled={!canReadYears || years.isPending} className="mt-2">
              <option value="">{yearId ? "Current Academic Year" : year ? `${year.label} · Current` : "Current Academic Year"}</option>
              {(years.data?.data.items ?? []).map((item) => <option key={item.id} value={item.id}>{item.label}{item.is_current ? " · Current" : ""}</option>)}
            </Select>{years.isError ? <p role="alert" className="mt-2 text-sm text-danger">Academic Years could not be loaded. <Button variant="quiet" onClick={() => void years.refetch()}>Retry</Button></p> : null}</div>
            <div><Label htmlFor="exit-opportunity-source">Reason</Label><Select id="exit-opportunity-source" value={effectiveSource} disabled={Boolean(existing)} onChange={(event) => { const value = event.target.value; if (value === "GRADUATION" || value === "MANUAL") setSource(value); }} className="mt-2">
              <option value={ExitInterviewOpportunitySourceValue.GRADUATION}>Graduation</option><option value={ExitInterviewOpportunitySourceValue.MANUAL}>Manual</option>
            </Select><p className="mt-2 text-sm text-muted">{effectiveSource === "GRADUATION" ? "The Student must submit the Exit Interview before requesting their graduation Good Moral certificate." : "Opens the Exit Interview without adding a graduation Good Moral prerequisite."}</p></div>
          </div>
          <div className="mt-5"><Label htmlFor="exit-opportunity-note">Operational note <span className="font-normal text-muted">(optional)</span></Label><Textarea id="exit-opportunity-note" maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} className="mt-2" /></div>
          {student ? <div className="mt-4 text-sm text-muted">{opportunities.isPending ? "Checking existing access…" : opportunities.isError ? <p role="alert">Existing access could not be confirmed. <Button variant="quiet" onClick={() => void opportunities.refetch()}>Retry</Button></p> : existing ? <p>Existing access: {existing.source === "GRADUATION" ? "Graduation" : "Manual"} · {existing.status === "OPEN" ? "Open" : existing.status === "COMPLETED" ? "Completed" : "Revoked"}. {existing.status === "REVOKED" ? "Reopening keeps the same reason." : "Use the existing workflow."}</p> : "No Exit Interview access for this Student and Academic Year."}</div> : null}
        </PanelSection>
        <PanelFooter><Button type="submit" disabled={!ready || opening.isPending}>Review opening</Button><Button type="button" variant="secondary" disabled={opening.isPending} onClick={() => { if (dirty) setDiscardOpen(true); else onDone(); }}>Cancel</Button></PanelFooter>
      </form>
    </Panel>
    <ConsequentialActionDialog open={discardOpen} title="Discard this opening?" confirmLabel="Discard opening" pendingLabel="Discarding…" pending={false} error={null} variant="danger" onConfirm={() => { discarded.current = true; onDone(); }} onOpenChange={setDiscardOpen} onCloseAutoFocus={(event) => { if (discarded.current) { event.preventDefault(); focusHeading("exit-opportunities-heading"); } }}>
      <p>The selected Student, reason, and operational note will be discarded. No access has been opened.</p>
    </ConsequentialActionDialog>
    <ConsequentialActionDialog open={review !== null} title={`Open Exit Interview access for ${student?.display_name ?? "this Student"}?`} confirmLabel="Open access" pendingLabel="Opening…" pending={opening.isPending} error={error} completed={completed ? { title: "Exit Interview access opened", children: "The Student can complete their Exit Interview after submitting their current Individual Inventory." } : null} onConfirm={() => void confirm()} onCloseAutoFocus={(event) => { if (completed) { event.preventDefault(); focusHeading("exit-opportunities-heading"); } }} onOpenChange={(open) => { if (!open) { setReview(null); if (completed) onDone(); } }}>
      <p>{year?.label ?? "Current Academic Year"} · {review?.source === "GRADUATION" ? "Graduation" : "Manual"}</p>
      <p>{review?.source === "GRADUATION" ? "A submitted Exit Interview will be required before the Student can request their graduation Good Moral certificate for this Academic Year." : "This opens Exit Interview access without adding a graduation Good Moral prerequisite."}</p>
    </ConsequentialActionDialog>
  </>;
}

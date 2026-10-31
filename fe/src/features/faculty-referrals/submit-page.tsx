"use client";

import { useEffect, useRef, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { pageSheetWidth } from "@/components/ui/page-width";
import { Panel, PanelBody, PanelFooter, PanelSection } from "@/components/ui/panel";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { facultyReferralsPath, facultySubmissionAvailable } from "./access";
import { useFacultyAvailability } from "./availability";
import { FacultyLoading, FacultyReferralGate, FacultyUnavailable } from "./shared";
import { SubmissionFacts } from "./records";
import { useFacultySubmission } from "./use-submission";

function ReviewHeading() {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  return <h2 ref={heading} id="faculty-review-heading" tabIndex={-1} className="font-heading text-xl font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Review referral</h2>;
}

export function FacultySubmitPage() {
  return <FacultyReferralGate submit><FacultySubmitContent /></FacultyReferralGate>;
}

function FacultySubmitContent() {
  const { user } = usePortalSession();
  const availability = useFacultyAvailability(user);
  const available = facultySubmissionAvailable(availability.availability);
  const flow = useFacultySubmission({ available, onPolicyChange: () => { void availability.refetch(); } });
  const submit = (event: FormEvent) => { event.preventDefault(); flow.review(); };
  const checkedStudent = flow.confirmed?.student;
  return <section className={pageSheetWidth} aria-labelledby="faculty-submit-heading">
    <PageHeader title={flow.result ? "Referral submitted" : "Submit Referral"} headingId="faculty-submit-heading" />
    {flow.result ? <>
      <Notice tone="success" role="status">Your referral has been submitted to the Guidance and Counseling Office.</Notice>
      <Panel className="mt-4"><SubmissionFacts item={flow.result} /><PanelFooter>
        <GuardedPortalLink href={`${facultyReferralsPath}/${flow.result.id}`} className="inline-flex min-h-11 items-center font-semibold text-brand underline">View referral details</GuardedPortalLink>
        <GuardedPortalLink href={facultyReferralsPath} className="inline-flex min-h-11 items-center font-semibold text-brand underline">My Referrals</GuardedPortalLink>
      </PanelFooter></Panel>
    </> : !available && !flow.dirty ? availability.isPending ? <FacultyLoading label="Checking submission availability…" /> : availability.isError ? <Notice role="alert" action={<Button variant="secondary" onClick={() => void availability.refetch()}>Retry</Button>}>Submission availability could not be checked.</Notice> : <FacultyUnavailable onRetry={() => void availability.refetch()} /> : <>
      {!available ? <div className="mb-4"><Notice role="alert" action={<Button variant="secondary" onClick={() => void availability.refetch()}>Check availability</Button>}>Digital Referrals are currently unavailable. Your input is preserved on this page; no request will be repeated automatically.</Notice></div> : null}
      {flow.error ? <Notice tone="warning" role="alert" className="mb-4">{flow.error}</Notice> : null}
      {flow.expired && checkedStudent ? <Notice role="status" className="mb-4">The Student confirmation has expired. Confirm the Student again before a new submission. An uncertain submission can still be retried with its original information.</Notice> : null}
      {flow.reviewing ? <Panel className="[overflow-wrap:anywhere]">
        <PanelBody><ReviewHeading /><p className="mt-2 text-sm text-muted">Review the Student and reason before submitting.</p></PanelBody>
        <PanelSection title="Student" titleId="faculty-review-student"><p className="text-sm font-medium [overflow-wrap:anywhere]">{checkedStudent?.display_name}</p></PanelSection>
        <PanelSection title="Referral information" titleId="faculty-review-information"><dl className="space-y-4 text-sm">
          <div><dt className="font-semibold text-muted">Course/Year/Block</dt><dd className="mt-1 whitespace-pre-wrap [overflow-wrap:anywhere]">{flow.course}</dd></div>
          <div><dt className="font-semibold text-muted">Referral reason</dt><dd className="mt-1 whitespace-pre-wrap [overflow-wrap:anywhere]">{flow.reason}</dd></div>
        </dl></PanelSection>
        {flow.uncertain ? <PanelBody><p className="text-sm text-warning">The result is not confirmed. Retry the exact same submission, or check My Referrals before discarding this draft. Editing is unavailable while this outcome is uncertain.</p></PanelBody> : null}
        <PanelFooter>
          <Button type="button" onClick={() => void flow.submit()} disabled={flow.pending || !available || (flow.expired && !flow.uncertain)}>{flow.submitting ? "Submitting…" : flow.uncertain ? "Retry same submission" : "Submit referral"}</Button>
          <Button type="button" variant="secondary" className="min-w-0 max-w-full" onClick={flow.edit} disabled={flow.pending || flow.uncertain}>Edit referral information</Button>
          <GuardedPortalLink href={facultyReferralsPath} className="inline-flex min-h-11 items-center text-sm font-semibold text-brand underline">My Referrals</GuardedPortalLink>
        </PanelFooter>
      </Panel> : <form onSubmit={submit} noValidate aria-label="Faculty Referral" autoComplete="off">
        <Panel>
          <PanelSection title="1. Confirm Student" titleId="faculty-confirm-heading">
            <div className="max-w-xl space-y-3">
              <div><label htmlFor="faculty-student-id" className="block text-sm font-semibold text-ink">Student institutional ID</label>
                <Input id="faculty-student-id" name="institutional_id" className="mt-2" value={flow.identifier} onChange={(event) => flow.changeIdentifier(event.target.value)} aria-invalid={!!flow.errors.identifier} aria-describedby={`faculty-id-help${flow.errors.identifier ? " faculty-id-error" : ""}`} disabled={flow.pending} autoComplete="off" autoCapitalize="characters" spellCheck={false} />
                <p id="faculty-id-help" className="mt-1 text-sm text-muted">Enter the exact ID, up to 64 characters. Names and partial IDs cannot be searched.</p>
                {flow.errors.identifier ? <p id="faculty-id-error" role="alert" className="mt-1 text-sm text-danger">{flow.errors.identifier}</p> : null}
              </div>
              <Button type="button" variant="secondary" onClick={() => void flow.confirmStudent()} disabled={flow.pending || !available || !!flow.cooldown}>{flow.confirming ? "Confirming…" : checkedStudent ? "Confirm Student again" : "Confirm Student"}</Button>
              {checkedStudent ? <div role="status" className="text-sm"><p className="font-semibold [overflow-wrap:anywhere]">{checkedStudent.display_name}</p><p className="mt-1 text-muted">{flow.expired ? "Confirmation expired." : `Confirmation expires ${formatInstitutionalDateTime(flow.confirmed?.expires_at)} · Philippine Time.`}</p></div> : null}
            </div>
          </PanelSection>
          <PanelSection title="2. Referral information" titleId="faculty-information-heading">
            <fieldset disabled={flow.pending} className="min-w-0 space-y-4 [overflow-wrap:anywhere]">
              <legend className="sr-only">Referral information</legend>
              <div><label htmlFor="faculty-course" className="block text-sm font-semibold text-ink">Course/Year/Block</label><Input id="faculty-course" name="course_year_block" className="mt-2" value={flow.course} onChange={(event) => flow.changeCourse(event.target.value)} aria-invalid={!!flow.errors.course} aria-describedby={`faculty-course-help${flow.errors.course ? " faculty-course-error" : ""}`} />
                <p id="faculty-course-help" className="mt-1 text-sm text-muted">As stated on the Referral Slip, up to 255 characters. This does not establish the Student’s College.</p>
                {flow.errors.course ? <p id="faculty-course-error" role="alert" className="mt-1 text-sm text-danger">{flow.errors.course}</p> : null}</div>
              <div><label htmlFor="faculty-reason" className="block text-sm font-semibold text-ink">Referral reason</label><Textarea id="faculty-reason" name="reason" className="mt-2 min-h-40" value={flow.reason} onChange={(event) => flow.changeReason(event.target.value)} aria-invalid={!!flow.errors.reason} aria-describedby={`faculty-reason-help${flow.errors.reason ? " faculty-reason-error" : ""}`} spellCheck={false} />
                <p id="faculty-reason-help" className="mt-1 text-sm text-muted">Keep observations relevant to the referral, up to 10,000 characters. Unsaved information stays only on this page.</p>
                {flow.errors.reason ? <p id="faculty-reason-error" role="alert" className="mt-1 text-sm text-danger">{flow.errors.reason}</p> : null}</div>
            </fieldset>
          </PanelSection>
          <PanelFooter><Button type="submit" disabled={flow.pending || !available}>Review referral</Button></PanelFooter>
        </Panel>
      </form>}
      <div className="mt-3"><Button type="button" variant="secondary" onClick={flow.discard} disabled={flow.pending || !flow.dirty}>Discard draft</Button></div>
    </>}
  </section>;
}

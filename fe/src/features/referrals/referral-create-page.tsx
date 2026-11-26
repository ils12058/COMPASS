"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelFooter, PanelSection } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { UrgencyCheckbox, UrgentBadge } from "./referral-urgency";
import {
  detectCourseYearBlockMismatch,
  formatAcademicUnit,
  formatStudentPlacementSummary,
} from "./student-verification";
import { TimingEditor } from "@/features/referral-timing/timing-editor";
import { TimingWindows } from "@/features/referral-timing/timing-readout";
import {
  emptyTimingDraft,
  focusTimingError,
  timingBackendErrors,
  timingDraftDirty,
  timingStatementRequest,
  timingWindowsRequest,
  validateTimingDraft,
  type TimingFieldErrors,
} from "@/features/referral-timing/timing-draft";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import {
  ReferralAccessUnavailable,
  ReferralHeading,
  referralErrorCode,
  referralErrorMessage,
  uncertainReferralMutation,
} from "@/features/referrals/referrals-shared";
import { EligibleStudentPicker, type EligibleStudentOption } from "@/features/portal/components/eligible-student-picker";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getReferralsListQueryKey, referralsCreate, useReferralsListEligibleStudents } from "@/lib/api/generated/referrals/referrals";
import type { ReferralCreateRequest, ReferralStudentOptionResponse } from "@/lib/api/generated/model";
import {
  INSTITUTION_TIME_ZONE_LABEL,
  formatDateOnly,
  formatInstitutionalDateTime,
  institutionalDateInputValue,
  institutionalDateTimeInputToISO,
  isFutureInstitutionalDateInput,
  isFutureInstitutionalDateTimeInput,
} from "@/lib/institutional-time";
import { yearLevelLabel } from "@/lib/year-level";

type CreationIntent = { fingerprint: string; key: string; payload: ReferralCreateRequest };

function ReviewHeading() {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  return (
    <h2
      ref={heading}
      id="staff-review-heading"
      tabIndex={-1}
      className="font-heading text-xl font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
    >
      Review Referral
    </h2>
  );
}

export function ReferralCreatePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const access = getReferralAccess(user);
  const [studentSearch, setStudentSearch] = useState("");
  const [appliedStudentSearch, setAppliedStudentSearch] = useState("");
  const [studentPage, setStudentPage] = useState(1);
  const [student, setStudent] = useState<ReferralStudentOptionResponse | null>(null);
  const [courseYearBlock, setCourseYearBlock] = useState("");
  const [reason, setReason] = useState("");
  const [urgent, setUrgent] = useState(false);
  const [referrerName, setReferrerName] = useState("");
  const [referredOn, setReferredOn] = useState("");
  const [receivedAt, setReceivedAt] = useState("");
  const [timing, setTiming] = useState(emptyTimingDraft);
  const [timingErrors, setTimingErrors] = useState<TimingFieldErrors>({});
  const [reviewing, setReviewing] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const intent = useRef<CreationIntent | null>(null);
  useUnsavedChangesGuard({
    dirty: !saved && (urgent || timingDraftDirty(timing) || !!(student || courseYearBlock || reason || referrerName || referredOn || receivedAt)),
    message: uncertain
      ? "The creation outcome is not confirmed. Check Referrals before discarding this draft and its retry information?"
      : "Discard your unsaved Referral? Its scheduling information is kept only on this page.",
  });

  const eligibleStudents = useReferralsListEligibleStudents(
    {
      ...(appliedStudentSearch ? { search: appliedStudentSearch } : {}),
      page: studentPage,
      page_size: 10,
    },
    { query: { enabled: access.canManage, retry: false } },
  );
  const create = useMutation({
    mutationFn: () => {
      if (!intent.current) throw new Error("Missing intended Referral");
      return referralsCreate(intent.current.payload, { headers: { "Idempotency-Key": intent.current.key } });
    },
    retry: false,
    gcTime: 0,
  });

  if (!access.canManage) {
    return <ReferralAccessUnavailable title="Record Referral" message="You don’t have access to record Referrals." />;
  }

  function buildValidatedPayload(): ReferralCreateRequest | null {
    if (!student) { setError("Choose an eligible Student before recording the Referral."); return null; }
    if (!courseYearBlock.trim()) { setError("Course / Year / Block is required."); return null; }
    if (!reason.trim()) { setError("Reason for Referral is required."); return null; }
    if (!referrerName.trim()) { setError("Referrer name is required."); return null; }
    if (!referredOn) { setError("Date referred is required."); return null; }
    if (isFutureInstitutionalDateInput(referredOn)) { setError("Date referred cannot be in the future."); return null; }
    const invalidTiming = validateTimingDraft(timing);
    setTimingErrors(invalidTiming);
    if (Object.keys(invalidTiming).length) { focusTimingError("gco-timing", timing, invalidTiming); return null; }
    const statement = timingStatementRequest(timing);
    if (!statement) return null;

    let receivedAtIso: string | null = null;
    if (receivedAt) {
      receivedAtIso = institutionalDateTimeInputToISO(receivedAt);
      if (!receivedAtIso) { setError("Enter a valid Guidance received date and time."); return null; }
      if (isFutureInstitutionalDateTimeInput(receivedAt)) { setError("Guidance received date and time cannot be in the future."); return null; }
      if (receivedAt.slice(0, 10) < referredOn) {
        setError("Guidance received date cannot be earlier than Date referred.");
        return null;
      }
    }

    if (!globalThis.crypto?.randomUUID) {
      setError("This browser cannot create a secure Referral request. Update the browser and try again.");
      return null;
    }

    return {
      student_id: student.id,
      course_year_block: courseYearBlock.trim(),
      reason: reason.trim(),
      referrer_name: referrerName.trim(),
      referred_on: referredOn,
      received_at: receivedAtIso,
      is_urgent: urgent,
      scheduling_statement: statement,
    };
  }

  function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const payload = buildValidatedPayload();
    if (!payload) return;
    const fingerprint = JSON.stringify(payload);
    if (intent.current && intent.current.fingerprint !== fingerprint) {
      setUncertain(false);
    }
    setReviewing(true);
  }

  function edit() {
    if (create.isPending || uncertain) return;
    setReviewing(false);
    setError(null);
    setNotice(null);
    requestAnimationFrame(() => document.getElementById("eligible-student-search")?.focus());
  }

  async function submit() {
    if (create.isPending) return;
    setError(null);
    setNotice(null);

    if (!intent.current || !uncertain) {
      const payload = buildValidatedPayload();
      if (!payload) { setReviewing(false); return; }
      const fingerprint = JSON.stringify(payload);
      const key = intent.current?.fingerprint === fingerprint
        ? intent.current.key
        : globalThis.crypto.randomUUID();
      intent.current = { fingerprint, key, payload };
    }

    try {
      const response = await create.mutateAsync();
      const referral = response.data;
      intent.current = null;
      setUncertain(false);
      setSaved(true);
      await queryClient.invalidateQueries({ queryKey: getReferralsListQueryKey() });
      router.push(`/portal/referrals/${referral.id}`);
    } catch (caught) {
      const invalidFields = timingBackendErrors(caught);
      if (Object.keys(invalidFields).length) {
        setTimingErrors(invalidFields);
        setReviewing(false);
        setUncertain(false);
        intent.current = null;
        requestAnimationFrame(() => focusTimingError("gco-timing", timing, invalidFields));
      }
      if (referralErrorCode(caught) === "idempotency_key_conflict") {
        intent.current = null;
        setUncertain(false);
        setError(referralErrorMessage(caught, "Couldn't create the Referral. Try again."));
      } else if (uncertainReferralMutation(caught)) {
        setUncertain(true);
        setError("Couldn't confirm Referral creation result. Retry the same unchanged Referral details to safely check the result.");
      } else {
        setUncertain(false);
        setError(referralErrorMessage(caught, "Couldn't create the Referral. Try again."));
      }
    } finally { create.reset(); }
  }

  const studentPageData = eligibleStudents.data?.data;
  const studentCollege = formatAcademicUnit(student?.college);
  const studentProgram = formatAcademicUnit(student?.program);
  const studentYearLevel = student?.year_level !== null && student?.year_level !== undefined
    ? yearLevelLabel(student.year_level)
    : null;
  const mismatch = reviewing ? detectCourseYearBlockMismatch(courseYearBlock, student, { action: "record" }) : null;
  const receivedAtIso = receivedAt ? institutionalDateTimeInputToISO(receivedAt) : null;

  return (
    <div className="space-y-5">
      <ReferralHeading title="Record Referral" backHref="/portal/referrals" />
      {reviewing && student ? (
        <Panel as="div" className="max-w-3xl [overflow-wrap:anywhere]" aria-busy={create.isPending}>
          <PanelBody>
            <ReviewHeading />
            <p className="mt-2 text-sm text-muted">Review the Student and Referral details before recording.</p>
          </PanelBody>
          <PanelSection title="Student" titleId="staff-review-student">
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="font-semibold text-muted">Name</dt>
                <dd className="mt-1 font-medium [overflow-wrap:anywhere]">{student.display_name}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted">Institutional ID</dt>
                <dd className="mt-1 [overflow-wrap:anywhere]">{student.institutional_id || "Not available"}</dd>
              </div>
              {studentCollege ? (
                <div>
                  <dt className="font-semibold text-muted">College</dt>
                  <dd className="mt-1 [overflow-wrap:anywhere]">{studentCollege}</dd>
                </div>
              ) : null}
              {studentProgram ? (
                <div>
                  <dt className="font-semibold text-muted">Program</dt>
                  <dd className="mt-1 [overflow-wrap:anywhere]">{studentProgram}</dd>
                </div>
              ) : null}
              {studentYearLevel ? (
                <div>
                  <dt className="font-semibold text-muted">Year level</dt>
                  <dd className="mt-1">{studentYearLevel}</dd>
                </div>
              ) : null}
            </dl>
          </PanelSection>
          {urgent ? <PanelBody><UrgentBadge urgent /></PanelBody> : null}
          <PanelSection title="Referral source" titleId="staff-review-source">
            <dl className="space-y-4 text-sm">
              <div>
                <dt className="font-semibold text-muted">Course / Year / Block</dt>
                <dd className="mt-1 whitespace-pre-wrap [overflow-wrap:anywhere]">{courseYearBlock.trim()}</dd>
              </div>
              {mismatch ? (
                <Notice tone="warning" role="status" title="Check Course / Year / Block">{mismatch.message}</Notice>
              ) : null}
              <div>
                <dt className="font-semibold text-muted">Reason for Referral</dt>
                <dd className="mt-1 whitespace-pre-wrap [overflow-wrap:anywhere]">{reason.trim()}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted">Referrer name</dt>
                <dd className="mt-1 whitespace-pre-wrap [overflow-wrap:anywhere]">{referrerName.trim()}</dd>
              </div>
            </dl>
          </PanelSection>
          <PanelSection title="History" titleId="staff-review-history">
            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="font-semibold text-muted">Date referred</dt>
                <dd className="mt-1">{formatDateOnly(referredOn)}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted">Received by the Guidance Office</dt>
                <dd className="mt-1">
                  {receivedAtIso ? `${formatInstitutionalDateTime(receivedAtIso)} · ${INSTITUTION_TIME_ZONE_LABEL}` : "Not recorded"}
                </dd>
              </div>
            </dl>
          </PanelSection>
          <PanelSection title="When can Guidance reach or meet the student?" titleId="staff-review-timing">
            {timing.answer === "UNKNOWN" ? (
              <p className="text-sm">Unknown / needs confirmation</p>
            ) : (
              <>
                <TimingWindows windows={timingWindowsRequest(timing).map((window) => ({ ...window, expired: false }))} />
                {timing.note ? (
                  <p className="mt-3 whitespace-pre-wrap text-sm [overflow-wrap:anywhere]">
                    <span className="font-semibold">Scheduling constraints: </span>{timing.note}
                  </p>
                ) : null}
              </>
            )}
          </PanelSection>
          {uncertain ? (
            <PanelBody>
              <p className="text-sm text-warning">Retry the same unchanged Referral details or check Referrals before discarding this draft. You can edit after the result is confirmed.</p>
            </PanelBody>
          ) : null}
          <PanelFooter>
            {error ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : null}
            {notice ? <p role="status" className="w-full text-sm text-muted">{notice}</p> : null}
            <Button type="button" onClick={() => void submit()} disabled={create.isPending}>
              {create.isPending ? "Recording…" : uncertain ? "Retry same submission" : "Record Referral"}
            </Button>
            <Button type="button" variant="secondary" onClick={edit} disabled={create.isPending || uncertain}>
              Edit Referral details
            </Button>
            <GuardedPortalLink href="/portal/referrals" className={buttonVariants({ variant: "secondary" })}>Cancel</GuardedPortalLink>
          </PanelFooter>
        </Panel>
      ) : (
        /* One sheet in the order of the paper referral: who was referred, the source details, then
           the dates. The form's one action area advances to the Review Referral summary. */
        <form className="max-w-3xl" onSubmit={review} aria-busy={create.isPending}>
          <Panel as="div">
            <PanelSection
              title="Student"
              titleId="referral-student-heading"
              description="Find the Student named on the Referral."
            >
              <EligibleStudentPicker
                label="Choose Student"
                search={studentSearch}
                onSearchChange={setStudentSearch}
                onSearch={() => { setAppliedStudentSearch(studentSearch.trim()); setStudentPage(1); }}
                items={studentPageData?.items ?? []}
                selectedStudent={student}
                selectedId={student?.id ?? null}
                onSelect={(selected: EligibleStudentOption) => setStudent(selected as ReferralStudentOptionResponse)}
                optionDescription={(option) =>
                  "program" in option || "year_level" in option
                    ? formatStudentPlacementSummary(option as ReferralStudentOptionResponse)
                    : ""
                }
                page={studentPageData?.page ?? studentPage}
                hasNext={studentPageData?.has_next ?? false}
                isLoading={eligibleStudents.isPending}
                isError={eligibleStudents.isError}
                errorMessage={referralErrorMessage(eligibleStudents.error, "Couldn't load eligible Students. Try again.")}
                onRetry={() => void eligibleStudents.refetch()}
                onPageChange={setStudentPage}
              />
            </PanelSection>

            <PanelSection title="Referral source" titleId="referral-source-heading">
              <div className="grid gap-5">
                <div className="grid gap-2">
                  <Label htmlFor="referral-course-year-block">Course / Year / Block</Label>
                  <Input id="referral-course-year-block" maxLength={255} required value={courseYearBlock} onChange={(event) => setCourseYearBlock(event.target.value)} />
                  <p className="text-xs text-muted">Enter the value shown on the source Referral. It will remain as entered on this Referral.</p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="referral-reason">Reason for Referral</Label>
                  <Textarea id="referral-reason" required rows={6} maxLength={10_000} value={reason} onChange={(event) => setReason(event.target.value)} />
                  <p className="text-xs text-muted">Copy the reason as written on the Referral. Do not add a diagnosis or risk assessment here.</p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="referral-referrer-name">Referrer name</Label>
                  <Input id="referral-referrer-name" maxLength={255} required value={referrerName} onChange={(event) => setReferrerName(event.target.value)} />
                  <p className="text-xs text-muted">Enter the name shown on the source Referral. This is not a digital signature.</p>
                </div>
              </div>
            </PanelSection>

            <PanelSection title="Urgency" titleId="gco-urgency-heading">
              <UrgencyCheckbox id="gco-urgent" checked={urgent} onChange={setUrgent} disabled={create.isPending} />
            </PanelSection>
            <PanelSection title="History" titleId="referral-chronology-heading">
              <div className="grid gap-5 sm:grid-cols-2">
                <div className="grid content-start gap-2">
                  <Label htmlFor="referral-referred-on">Date referred</Label>
                  <Input id="referral-referred-on" type="date" required max={institutionalDateInputValue()} value={referredOn} onChange={(event) => setReferredOn(event.target.value)} />
                  <p className="text-xs leading-5 text-muted">The date the source Referral was made or signed. It is not the date entered into COMPASS.</p>
                </div>
                <div className="grid content-start gap-2">
                  <Label htmlFor="referral-received-at">Received by the Guidance Office (optional)</Label>
                  <Input id="referral-received-at" type="datetime-local" step="60" value={receivedAt} onChange={(event) => setReceivedAt(event.target.value)} />
                  <p className="text-xs leading-5 text-muted">Enter the date and time the Guidance Office received this Referral, if known. Times use {INSTITUTION_TIME_ZONE_LABEL}.</p>
                </div>
              </div>
            </PanelSection>

            <PanelSection title="When can Guidance reach or meet the student?" titleId="gco-timing-heading">
              <TimingEditor prefix="gco-timing" draft={timing} onChange={setTiming} errors={timingErrors} disabled={create.isPending} />
            </PanelSection>
            <PanelFooter>
              {error ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : null}
              {notice ? <p role="status" className="w-full text-sm text-muted">{notice}</p> : null}
              <Button type="submit" disabled={create.isPending || eligibleStudents.isPending}>
                Review Referral
              </Button>
              <GuardedPortalLink href="/portal/referrals" className={buttonVariants({ variant: "secondary" })}>Cancel</GuardedPortalLink>
            </PanelFooter>
          </Panel>
        </form>
      )}
    </div>
  );
}

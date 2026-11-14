"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { TimingEditor } from "@/features/referral-timing/timing-editor";
import { emptyTimingDraft, focusTimingError, timingBackendErrors, timingDraftDirty, timingStatementRequest, validateTimingDraft, type TimingFieldErrors } from "@/features/referral-timing/timing-draft";
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
import type { ReferralCreateRequest } from "@/lib/api/generated/model";
import {
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateInputValue,
  institutionalDateTimeInputToISO,
  isFutureInstitutionalDateInput,
  isFutureInstitutionalDateTimeInput,
} from "@/lib/institutional-time";

type CreationIntent = { fingerprint: string; key: string; payload: ReferralCreateRequest };

export function ReferralCreatePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const access = getReferralAccess(user);
  const [studentSearch, setStudentSearch] = useState("");
  const [appliedStudentSearch, setAppliedStudentSearch] = useState("");
  const [studentPage, setStudentPage] = useState(1);
  const [student, setStudent] = useState<EligibleStudentOption | null>(null);
  const [courseYearBlock, setCourseYearBlock] = useState("");
  const [reason, setReason] = useState("");
  const [referrerName, setReferrerName] = useState("");
  const [referredOn, setReferredOn] = useState("");
  const [receivedAt, setReceivedAt] = useState("");
  const [timing, setTiming] = useState(emptyTimingDraft);
  const [timingErrors, setTimingErrors] = useState<TimingFieldErrors>({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const intent = useRef<CreationIntent | null>(null);
  useUnsavedChangesGuard({ dirty: !saved && (timingDraftDirty(timing) || !!(student || courseYearBlock || reason || referrerName || referredOn || receivedAt)), message: "Discard your unsaved Referral? Its scheduling information is kept only on this page." });

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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (!student) return setError("Choose an eligible Student before recording the Referral.");
    if (!courseYearBlock.trim()) return setError("Course / Year / Block is required.");
    if (!reason.trim()) return setError("Reason for Referral is required.");
    if (!referrerName.trim()) return setError("Referrer name is required.");
    if (!referredOn) return setError("Date referred is required.");
    if (isFutureInstitutionalDateInput(referredOn)) return setError("Date referred cannot be in the future.");
    const invalidTiming = validateTimingDraft(timing);
    setTimingErrors(invalidTiming);
    if (Object.keys(invalidTiming).length) { focusTimingError("gco-timing", timing, invalidTiming); return; }
    const statement = timingStatementRequest(timing);
    if (!statement) return;

    let receivedAtIso: string | null = null;
    if (receivedAt) {
      receivedAtIso = institutionalDateTimeInputToISO(receivedAt);
      if (!receivedAtIso) return setError("Enter a valid Guidance received date and time.");
      if (isFutureInstitutionalDateTimeInput(receivedAt)) return setError("Guidance received date and time cannot be in the future.");
      if (receivedAt.slice(0, 10) < referredOn) {
        return setError("Guidance received date cannot be earlier than Date referred.");
      }
    }

    if (!globalThis.crypto?.randomUUID) {
      return setError("This browser cannot create a secure Referral request. Update the browser and try again.");
    }

    const payload: ReferralCreateRequest = {
      student_id: student.id,
      course_year_block: courseYearBlock.trim(),
      reason: reason.trim(),
      referrer_name: referrerName.trim(),
      referred_on: referredOn,
      received_at: receivedAtIso,
      scheduling_statement: statement,
    };
    const fingerprint = JSON.stringify(payload);
    const key = intent.current?.fingerprint === fingerprint
      ? intent.current.key
      : globalThis.crypto.randomUUID();
    intent.current = { fingerprint, key, payload };

    try {
      const response = await create.mutateAsync();
      const referral = response.data;
      intent.current = null;
      setSaved(true);
      await queryClient.invalidateQueries({ queryKey: getReferralsListQueryKey() });
      router.push(`/portal/referrals/${referral.id}`);
    } catch (caught) {
      const invalidFields = timingBackendErrors(caught);
      setTimingErrors(invalidFields); focusTimingError("gco-timing", timing, invalidFields);
      if (referralErrorCode(caught) === "idempotency_key_conflict") {
        intent.current = null;
        setError(referralErrorMessage(caught, "Couldn't create the Referral. Try again."));
      } else if (uncertainReferralMutation(caught)) {
        setError("Couldn't confirm Referral creation result. Retry the same unchanged Referral details to safely check the result.");
      } else {
        setError(referralErrorMessage(caught, "Couldn't create the Referral. Try again."));
      }
    } finally { create.reset(); }
  }

  const studentPageData = eligibleStudents.data?.data;

  return (
    <div className="space-y-5">
      <ReferralHeading title="Record Referral" backHref="/portal/referrals" />
      {/* One sheet in the order of the paper referral: who was referred, the source details, then
          the dates. The form's one action area closes the sheet. */}
      <form className="max-w-3xl" onSubmit={submit} aria-busy={create.isPending}>
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
              onSelect={setStudent}
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

          <PanelSection title="Chronology" titleId="referral-chronology-heading">
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
              {create.isPending ? "Recording…" : "Record Referral"}
            </Button>
            <GuardedPortalLink href="/portal/referrals" className={buttonVariants({ variant: "secondary" })}>Cancel</GuardedPortalLink>
          </PanelFooter>
        </Panel>
      </form>
    </div>
  );
}

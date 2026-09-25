"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { StepUpDialog } from "@/features/account/security/security-shared";
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
import { dateTimeInputToISO, isFutureDateInput, isFutureDateTimeInput } from "@/lib/date-time";

type CreationIntent = { fingerprint: string; key: string };

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
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const intent = useRef<CreationIntent | null>(null);

  const eligibleStudents = useReferralsListEligibleStudents(
    {
      ...(appliedStudentSearch ? { search: appliedStudentSearch } : {}),
      page: studentPage,
      page_size: 10,
    },
    { query: { enabled: access.canManage, retry: false } },
  );
  const create = useMutation({
    mutationFn: ({ payload, key }: { payload: ReferralCreateRequest; key: string }) =>
      referralsCreate(payload, { headers: { "Idempotency-Key": key } }),
    retry: false,
  });

  if (!access.canManage) {
    return <ReferralAccessUnavailable title="Referral recording unavailable" message="Your current access does not include Referral management." />;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (!student) return setError("Choose an eligible Student before recording the Referral.");
    if (!courseYearBlock.trim()) return setError("Course / Year / Block is required.");
    if (!reason.trim()) return setError("Reason for referral is required.");
    if (!referrerName.trim()) return setError("Referrer name is required.");
    if (!referredOn) return setError("Date referred is required.");
    if (isFutureDateInput(referredOn)) return setError("Date referred cannot be in the future.");

    let receivedAtIso: string | null = null;
    if (receivedAt) {
      receivedAtIso = dateTimeInputToISO(receivedAt);
      if (!receivedAtIso) return setError("Enter a valid Guidance received date and time.");
      if (isFutureDateTimeInput(receivedAt)) return setError("Guidance received date and time cannot be in the future.");
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
    };
    const fingerprint = JSON.stringify(payload);
    const key = intent.current?.fingerprint === fingerprint
      ? intent.current.key
      : globalThis.crypto.randomUUID();
    intent.current = { fingerprint, key };

    try {
      const response = await create.mutateAsync({ payload, key });
      const referral = response.data;
      intent.current = null;
      await queryClient.invalidateQueries({ queryKey: getReferralsListQueryKey() });
      router.push(`/portal/referrals/${referral.id}`);
    } catch (caught) {
      if (referralErrorCode(caught) === "recent_mfa_required") {
        setNotice("Verify your authenticator, then submit the same Referral details again.");
        setStepUpOpen(true);
      } else if (referralErrorCode(caught) === "idempotency_key_conflict") {
        intent.current = null;
        setError(referralErrorMessage(caught, "The Referral could not be created."));
      } else if (uncertainReferralMutation(caught)) {
        setError("The Referral creation result could not be confirmed. Retry the same unchanged Referral details to safely check the result.");
      } else {
        setError(referralErrorMessage(caught, "The Referral could not be created."));
      }
    }
  }

  const studentPageData = eligibleStudents.data?.data;

  return (
    <div className="space-y-7">
      <ReferralHeading title="Record referral" description="Enter the source Referral details. Date referred, Guidance receipt, and the time COMPASS records this entry remain distinct." backHref="/portal/referrals" />
      <form className="max-w-3xl space-y-8" onSubmit={submit} aria-busy={create.isPending}>
        <section aria-labelledby="referral-student-heading" className="border-b border-border pb-7">
          <h2 id="referral-student-heading" className="font-heading text-xl font-semibold text-ink">Student</h2>
          <p className="mt-2 text-sm leading-6 text-muted">Search Students available for Referrals. College is shown for context.</p>
          <div className="mt-4">
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
              errorMessage={referralErrorMessage(eligibleStudents.error, "Eligible Students could not be loaded.")}
              onRetry={() => void eligibleStudents.refetch()}
              onPageChange={setStudentPage}
            />
          </div>
        </section>

        <section aria-labelledby="referral-source-heading" className="border-b border-border pb-7">
          <h2 id="referral-source-heading" className="font-heading text-xl font-semibold text-ink">Referral source</h2>
          <div className="mt-5 grid gap-5">
            <div className="grid gap-2">
              <Label htmlFor="referral-course-year-block">Course / Year / Block</Label>
              <Input id="referral-course-year-block" maxLength={255} required value={courseYearBlock} onChange={(event) => setCourseYearBlock(event.target.value)} />
              <p className="text-xs text-muted">Enter the value shown on the source Referral. It is saved as a historical snapshot.</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="referral-reason">Reason for referral</Label>
              <Textarea id="referral-reason" required rows={6} maxLength={10_000} value={reason} onChange={(event) => setReason(event.target.value)} />
              <p className="text-xs text-muted">Source text only. Do not classify severity, diagnosis, or risk.</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="referral-referrer-name">Referrer name</Label>
              <Input id="referral-referrer-name" maxLength={255} required value={referrerName} onChange={(event) => setReferrerName(event.target.value)} />
              <p className="text-xs text-muted">Enter the name shown on the source Referral. This is not a digital signature.</p>
            </div>
          </div>
        </section>

        <section aria-labelledby="referral-chronology-heading" className="border-b border-border pb-7">
          <h2 id="referral-chronology-heading" className="font-heading text-xl font-semibold text-ink">Chronology</h2>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="referral-referred-on">Date referred</Label>
              <Input id="referral-referred-on" type="date" required value={referredOn} onChange={(event) => setReferredOn(event.target.value)} />
              <p className="text-xs leading-5 text-muted">The date the source Referral was made or signed. It is not the date entered into COMPASS.</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="referral-received-at">Received by Guidance/GCO (optional)</Label>
              <Input id="referral-received-at" type="datetime-local" step="60" value={receivedAt} onChange={(event) => setReceivedAt(event.target.value)} />
              <p className="text-xs leading-5 text-muted">Enter only when the actual Guidance/GCO receipt date and time are known.</p>
            </div>
          </div>
        </section>

        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={create.isPending || eligibleStudents.isPending}>
            {create.isPending ? "Recording…" : "Record referral"}
          </Button>
          <Link href="/portal/referrals" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Cancel</Link>
        </div>
      </form>
      <StepUpDialog
        open={stepUpOpen}
        onOpenChange={setStepUpOpen}
        onVerified={() => setNotice("Verification complete. Submit the same Referral details again to continue.")}
      />
    </div>
  );
}

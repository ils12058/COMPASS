"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
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
import {
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateTimeInputToISO,
  isFutureInstitutionalDateInput,
  isFutureInstitutionalDateTimeInput,
} from "@/lib/institutional-time";

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
    return <ReferralAccessUnavailable title="Referral recording unavailable" message="Referral management is unavailable to this account." />;
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
    if (isFutureInstitutionalDateInput(referredOn)) return setError("Date referred cannot be in the future.");

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
    <div className="space-y-5">
      <ReferralHeading title="Record referral" backHref="/portal/referrals" />
      {/* One sheet in the order of the paper referral: who was referred, the source details, then
          the dates. The form's one action area closes the sheet. */}
      <form className="max-w-3xl" onSubmit={submit} aria-busy={create.isPending}>
        <Panel as="div">
          <PanelSection
            title="Student"
            titleId="referral-student-heading"
            description="Find the student named on the referral."
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
              errorMessage={referralErrorMessage(eligibleStudents.error, "Eligible Students could not be loaded.")}
              onRetry={() => void eligibleStudents.refetch()}
              onPageChange={setStudentPage}
            />
          </PanelSection>

          <PanelSection title="Referral source" titleId="referral-source-heading">
            <div className="grid gap-5">
              <div className="grid gap-2">
                <Label htmlFor="referral-course-year-block">Course / Year / Block</Label>
                <Input id="referral-course-year-block" maxLength={255} required value={courseYearBlock} onChange={(event) => setCourseYearBlock(event.target.value)} />
                <p className="text-xs text-muted">Enter the value shown on the source Referral. It will remain as entered on this referral.</p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="referral-reason">Reason for referral</Label>
                <Textarea id="referral-reason" required rows={6} maxLength={10_000} value={reason} onChange={(event) => setReason(event.target.value)} />
                <p className="text-xs text-muted">Copy the reason as written on the referral. Do not add a diagnosis or risk assessment here.</p>
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
                <Input id="referral-referred-on" type="date" required value={referredOn} onChange={(event) => setReferredOn(event.target.value)} />
                <p className="text-xs leading-5 text-muted">The date the source Referral was made or signed. It is not the date entered into COMPASS.</p>
              </div>
              <div className="grid content-start gap-2">
                <Label htmlFor="referral-received-at">Received by Guidance/GCO (optional)</Label>
                <Input id="referral-received-at" type="datetime-local" step="60" value={receivedAt} onChange={(event) => setReceivedAt(event.target.value)} />
                <p className="text-xs leading-5 text-muted">Enter only when the actual Guidance/GCO receipt date and time are known. Times use {INSTITUTION_TIME_ZONE_LABEL}.</p>
              </div>
            </div>
          </PanelSection>

          <PanelFooter>
            {error ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : null}
            {notice ? <p role="status" className="w-full text-sm text-muted">{notice}</p> : null}
            <Button type="submit" disabled={create.isPending || eligibleStudents.isPending}>
              {create.isPending ? "Recording…" : "Record referral"}
            </Button>
            <Link href="/portal/referrals" className={buttonVariants({ variant: "secondary" })}>Cancel</Link>
          </PanelFooter>
        </Panel>
      </form>
      <StepUpDialog
        open={stepUpOpen}
        onOpenChange={setStepUpOpen}
        onVerified={() => setNotice("Verification complete. Submit the same Referral details again to continue.")}
      />
    </div>
  );
}

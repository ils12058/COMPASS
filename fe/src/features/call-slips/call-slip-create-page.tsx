"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { CallSlipFormFields, type CallSlipDraft, toCallSlipRequestFields } from "@/features/call-slips/call-slip-form-fields";
import { CallSlipAccessUnavailable, CallSlipHeading, callSlipErrorCode, callSlipErrorMessage, callSlipDestinationLabel, uncertainCallSlipMutation } from "@/features/call-slips/call-slips-shared";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { EligibleStudentPicker, type EligibleStudentOption } from "@/features/portal/components/eligible-student-picker";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { callSlipsCreate, getCallSlipsListQueryKey, useCallSlipsListEligibleStudents } from "@/lib/api/generated/call-slips/call-slips";
import type { CallSlipCreateRequest } from "@/lib/api/generated/model";
import { dateTimeInputToISO } from "@/lib/date-time";

type CreateIntent = { fingerprint: string; key: string; payload: CallSlipCreateRequest };

const initialDraft: CallSlipDraft = {
  courseYear: "",
  destinationType: "GUIDANCE_OFFICE",
  otherDestination: "",
  reportAt: "",
  notifyStudent: true,
};

export function DirectCallSlipCreatePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const access = getCallSlipAccess(user);
  const [studentSearch, setStudentSearch] = useState("");
  const [appliedStudentSearch, setAppliedStudentSearch] = useState("");
  const [studentPage, setStudentPage] = useState(1);
  const [student, setStudent] = useState<EligibleStudentOption | null>(null);
  const [draft, setDraft] = useState(initialDraft);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const intent = useRef<CreateIntent | null>(null);

  const students = useCallSlipsListEligibleStudents(
    { ...(appliedStudentSearch ? { search: appliedStudentSearch } : {}), page: studentPage, page_size: 10 },
    { query: { enabled: access.canManageOperational, retry: false } },
  );
  const create = useMutation({
    mutationFn: ({ payload, key }: { payload: CallSlipCreateRequest; key: string }) =>
      callSlipsCreate(payload, { headers: { "Idempotency-Key": key } }),
    retry: false,
  });

  if (!access.canManageOperational) {
    return <CallSlipAccessUnavailable title="Call Slip issuance unavailable" message="Your current access does not include Call Slip management." />;
  }

  function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    if (!student) return setError("Choose an eligible Student before issuing the Call Slip.");
    const fields = toCallSlipRequestFields(draft);
    if (!fields) return setError("Complete Course / Year, destination, and report date and time.");
    const reportAt = dateTimeInputToISO(draft.reportAt);
    if (!reportAt) return setError("Enter a valid report date and time.");
    if (draft.destinationType === "OTHER" && !draft.otherDestination.trim()) return setError("Enter the other destination.");
    if (!globalThis.crypto?.randomUUID) return setError("This browser cannot create a secure issuance request. Update the browser and try again.");

    const payload: CallSlipCreateRequest = { ...fields, report_at: reportAt, student_id: student.id };
    const fingerprint = JSON.stringify(payload);
    const key = intent.current?.fingerprint === fingerprint ? intent.current.key : globalThis.crypto.randomUUID();
    intent.current = { fingerprint, key, payload };
    setConfirmOpen(true);
  }

  async function issueConfirmed() {
    setError(null);
    setNotice(null);
    const current = intent.current;
    if (!current) {
      setError("Review the Call Slip details again before issuing.");
      setConfirmOpen(false);
      return;
    }
    try {
      const response = await create.mutateAsync({ payload: current.payload, key: current.key });
      const callSlip = response.data;
      intent.current = null;
      setConfirmOpen(false);
      await queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey() });
      router.push(`/portal/call-slips/${callSlip.id}`);
    } catch (caught) {
      if (callSlipErrorCode(caught) === "recent_mfa_required") {
        setConfirmOpen(false);
        setNotice("Verify your authenticator, then review and confirm this issuance again.");
        setStepUpOpen(true);
      } else if (callSlipErrorCode(caught) === "idempotency_key_conflict") {
        intent.current = null;
        setConfirmOpen(false);
        setError(callSlipErrorMessage(caught, "This issuance attempt no longer matches its original details. Review the form and try again."));
      } else if (uncertainCallSlipMutation(caught)) {
        setError("The issuance result could not be confirmed. Retry only with these same unchanged details to safely check the result.");
      } else {
        setError(callSlipErrorMessage(caught, "The Call Slip could not be issued."));
      }
    }
  }

  const studentData = students.data?.data;
  const selectedDestination = callSlipDestinationLabel(draft.destinationType, draft.otherDestination);

  return (
    <main className="space-y-7">
      <CallSlipHeading title="Issue Call Slip" description="Record a Call Slip not requiring the linked Referral workflow." backHref="/portal/call-slips" />
      <form className="max-w-3xl space-y-8" onSubmit={prepare} aria-busy={create.isPending}>
        <section aria-labelledby="direct-call-slip-student-heading" className="border-b border-border pb-7">
          <h2 id="direct-call-slip-student-heading" className="font-heading text-xl font-semibold text-ink">Student</h2>
          <p className="mt-2 text-sm leading-6 text-muted">Search Students available for Call Slips. The issuer is recorded automatically.</p>
          <div className="mt-4">
            <EligibleStudentPicker
              label="Choose Student"
              search={studentSearch}
              onSearchChange={setStudentSearch}
              onSearch={() => { setAppliedStudentSearch(studentSearch.trim()); setStudentPage(1); }}
              items={studentData?.items ?? []}
              selectedStudent={student}
              selectedId={student?.id ?? null}
              onSelect={setStudent}
              page={studentData?.page ?? studentPage}
              hasNext={studentData?.has_next ?? false}
              isLoading={students.isPending}
              isError={students.isError}
              errorMessage={callSlipErrorMessage(students.error, "Eligible Students could not be loaded.")}
              onRetry={() => void students.refetch()}
              onPageChange={setStudentPage}
            />
          </div>
        </section>

        <section aria-labelledby="direct-call-slip-details-heading" className="border-b border-border pb-7">
          <h2 id="direct-call-slip-details-heading" className="font-heading text-xl font-semibold text-ink">Call Slip details</h2>
          <div className="mt-5">
            <CallSlipFormFields draft={draft} onChange={setDraft} />
          </div>
          <p className="mt-5 text-sm leading-6 text-muted">The entered Course / Year and report time are source text. Report date/time may be past, present, or future and does not determine whether this is a live or historical issuance.</p>
        </section>

        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={create.isPending || students.isPending}>{create.isPending ? "Issuing…" : "Review issuance"}</Button>
          <Link href="/portal/call-slips" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Cancel</Link>
        </div>
      </form>

      <AlertDialog open={confirmOpen} onOpenChange={(open) => { if (!create.isPending) setConfirmOpen(open); }}>
        <AlertDialogContent onEscapeKeyDown={(event) => { if (create.isPending) event.preventDefault(); }}>
          <AlertDialogTitle>Confirm Call Slip issuance</AlertDialogTitle>
          <AlertDialogDescription>Review the source details and selected issuance mode. COMPASS records the issuer and any separate recorder.</AlertDialogDescription>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-xs font-semibold text-muted">Student</dt><dd className="mt-1 text-ink">{student?.display_name ?? "Not selected"}{student?.institutional_id ? ` · ${student.institutional_id}` : ""}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Course / Year</dt><dd className="mt-1 text-ink">{draft.courseYear || "Not entered"}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Destination</dt><dd className="mt-1 text-ink">{selectedDestination}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Report date and time</dt><dd className="mt-1 text-ink">{draft.reportAt || "Not entered"}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs font-semibold text-muted">Issuance mode</dt><dd className="mt-1 text-ink">{draft.notifyStudent ? "Live issuance — creates an in-app notification and queues required operational email." : "Historical / back-entry — no new issuance notification."}</dd></div>
          </dl>
          {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild><Button variant="secondary" disabled={create.isPending}>Review details</Button></AlertDialogCancel>
            <Button disabled={create.isPending} onClick={() => void issueConfirmed()}>{create.isPending ? "Issuing…" : "Confirm and issue"}</Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => { setNotice("Verification complete. Review and confirm the issuance again."); setConfirmOpen(true); }} />
    </main>
  );
}

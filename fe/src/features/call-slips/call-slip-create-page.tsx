"use client";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import { CallSlipFormFields, type CallSlipDraft, toCallSlipRequestFields } from "@/features/call-slips/call-slip-form-fields";
import { CallSlipAccessUnavailable, CallSlipHeading, callSlipErrorCode, callSlipErrorMessage, callSlipDestinationLabel, uncertainCallSlipMutation } from "@/features/call-slips/call-slips-shared";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { EligibleStudentPicker, type EligibleStudentOption } from "@/features/portal/components/eligible-student-picker";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { callSlipsCreate, getCallSlipsListQueryKey, useCallSlipsListEligibleStudents } from "@/lib/api/generated/call-slips/call-slips";
import { getCounselingGetCaseQueryKey, useCounselingGetSessionProposalContext } from "@/lib/api/generated/counseling/counseling";
import { useGuidanceFollowupsGet } from "@/lib/api/generated/guidance-followups/guidance-followups";
import { portalReturnHref, withWorkflowReturn, workflowBackLabel } from "@/features/portal/workflow-navigation";
import { Notice } from "@/components/ui/notice";
import { isoToInstitutionalDateTimeInput } from "@/lib/institutional-time";
import type { CallSlipCreateRequest } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime, INSTITUTION_TIME_ZONE_LABEL, institutionalDateTimeInputToISO } from "@/lib/institutional-time";

type CreateIntent = { fingerprint: string; key: string; payload: CallSlipCreateRequest };

const initialDraft: CallSlipDraft = {
  courseYear: "",
  destinationType: "GUIDANCE_OFFICE",
  otherDestination: "",
  reportAt: "",
  notifyStudent: true,
};

type FixedStudent = { id: string; display_name: string; institutional_id: string | null };

export function DirectCallSlipCreatePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const access = getCallSlipAccess(user);
  // NS-1 shortcuts open this page prefilled: a Student (from a Follow-up) or a case and its Appointment.
  const params = useSearchParams() ?? new URLSearchParams();
  const returnTo = params.get("return_to");
  const back = portalReturnHref(returnTo, "/portal/call-slips");
  const prefillStudentId = params.get("student_id");
  const caseId = params.get("case_id");
  const appointmentId = caseId ? params.get("appointment_id") : null;
  const followUpId = caseId ? null : params.get("follow_up_id");
  const caseContext = useCounselingGetSessionProposalContext({ case_id: caseId ?? "" }, {
    query: { enabled: Boolean(caseId) && access.canManageOperational, retry: false, staleTime: 0 },
  });
  const followUp = useGuidanceFollowupsGet(followUpId ?? "", {
    query: { enabled: Boolean(followUpId) && access.canManageOperational, retry: false },
  });
  const contextData = caseContext.data?.data;
  const fixedStudent: FixedStudent | null = contextData && contextData.student.id === prefillStudentId
    ? { id: contextData.student.id, display_name: contextData.student.display_name, institutional_id: contextData.student.institutional_id }
    : followUp.data?.data && followUp.data.data.student_id === prefillStudentId
      ? { id: followUp.data.data.student_id, display_name: followUp.data.data.student_name, institutional_id: null }
      : null;
  const prefillPending = (Boolean(caseId) && caseContext.isPending) || (Boolean(followUpId) && followUp.isPending);
  const prefillFailed = (Boolean(caseId) && (caseContext.isError || (contextData && !fixedStudent))) || (Boolean(followUpId) && followUp.isError);
  const [studentSearch, setStudentSearch] = useState("");
  const [appliedStudentSearch, setAppliedStudentSearch] = useState("");
  const [studentPage, setStudentPage] = useState(1);
  const [student, setStudent] = useState<EligibleStudentOption | null>(null);
  const [draft, setDraft] = useState<CallSlipDraft>(() => ({ ...initialDraft, reportAt: isoToInstitutionalDateTimeInput(params.get("report_at")) }));
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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
    return <CallSlipAccessUnavailable title="Issue Call Slip" message="You don’t have access to issue Call Slips." />;
  }

  function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const chosen = fixedStudent ?? student;
    if (!chosen) return setError("Choose an eligible Student before issuing the Call Slip.");
    const fields = toCallSlipRequestFields(draft);
    if (!fields) return setError("Complete Course / Year, destination, and report date and time.");
    const reportAt = fields.report_at;
    if (draft.destinationType === "OTHER" && !draft.otherDestination.trim()) return setError("Enter the other destination.");
    if (!globalThis.crypto?.randomUUID) return setError("This browser cannot create a secure issuance request. Update the browser and try again.");

    const payload: CallSlipCreateRequest = {
      ...fields,
      report_at: reportAt,
      student_id: chosen.id,
      ...(caseId && fixedStudent ? { counseling_case_id: caseId, appointment_id: appointmentId, notify_student: true } : {}),
    };
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
      await Promise.all([queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey() }),
        invalidateGuidanceWork(queryClient),
        caseId ? queryClient.invalidateQueries({ queryKey: getCounselingGetCaseQueryKey(caseId) }) : Promise.resolve()]);
      router.push(returnTo ? withWorkflowReturn(`/portal/call-slips/${callSlip.id}`, back) : `/portal/call-slips/${callSlip.id}`);
    } catch (caught) {
      if (callSlipErrorCode(caught) === "idempotency_key_conflict") {
        intent.current = null;
        setConfirmOpen(false);
        setError(callSlipErrorMessage(caught, "This issuance attempt no longer matches its original details. Review the form and try again."));
      } else if (uncertainCallSlipMutation(caught)) {
        setError("Couldn't confirm the issuance result. Retry only with these same unchanged details to safely check the result.");
      } else {
        setError(callSlipErrorMessage(caught, "Couldn't issue the Call Slip. Try again."));
      }
    }
  }

  const studentData = students.data?.data;
  const selectedDestination = callSlipDestinationLabel(draft.destinationType, draft.otherDestination);

  return (
    <div className="space-y-5">
      <CallSlipHeading title="Issue Call Slip" description={caseId ? "Issue a Call Slip from a counseling case." : "Issue a Call Slip without linking it to a Referral."} backHref={back} backLabel={back === "/portal/call-slips" ? undefined : workflowBackLabel(back)} />
      {prefillFailed ? <Notice tone="warning" role="status">{caseId ? "This case can't be used for a Call Slip now. Choose the Student instead, or go back and check the case." : "The Follow-Up's Student couldn't be loaded. Choose the Student instead."}</Notice> : null}
      <form className="max-w-3xl" onSubmit={prepare} aria-busy={create.isPending}>
        <Panel as="div">
        <PanelSection
          title="Student"
          titleId="direct-call-slip-student-heading"
          description="Your name will be recorded as the issuer."
        >
            {prefillPending ? <p role="status" className="text-sm text-muted">Loading the Student…</p> : fixedStudent ? <div className="text-sm">
              <p className="font-semibold text-ink">{fixedStudent.display_name}{fixedStudent.institutional_id ? ` · ${fixedStudent.institutional_id}` : ""}</p>
              {caseId && contextData ? <p className="mt-1 text-muted">Linked to case {contextData.case.reference_code}{appointmentId ? " and its In person Appointment" : ""}. Only you and the case&apos;s Counselor see this link.</p> : null}
            </div> : <EligibleStudentPicker
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
              errorMessage={callSlipErrorMessage(students.error, "Couldn't load eligible Students. Try again.")}
              onRetry={() => void students.refetch()}
              onPageChange={setStudentPage}
            />}
        </PanelSection>

        <PanelSection
          title="Call Slip details"
          titleId="direct-call-slip-details-heading"
          description="Enter course/year and report time as shown on the source form."
        >
          <CallSlipFormFields draft={draft} onChange={setDraft} liveOnly={Boolean(caseId && fixedStudent)} />
        </PanelSection>

        <PanelFooter>
          {error && !confirmOpen ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : null}
          {notice ? <p role="status" className="w-full text-sm text-muted">{notice}</p> : null}
          <Button type="submit" disabled={create.isPending || prefillPending || (!fixedStudent && students.isPending)}>{create.isPending ? "Issuing…" : "Review issuance"}</Button>
          <Link href={back} className={buttonVariants({ variant: "secondary" })}>Cancel</Link>
        </PanelFooter>
        </Panel>
      </form>

      <ConsequentialActionDialog
        open={confirmOpen}
        title="Issue Call Slip?"
        confirmLabel="Issue Call Slip"
        cancelLabel="Review details"
        pendingLabel="Issuing…"
        pending={create.isPending}
        error={error}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void issueConfirmed()}
      >
        <p>
          Check the Student and report details before issuing. The selected notification option determines whether the Student is notified.
        </p>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-xs font-semibold text-muted">Student</dt><dd className="mt-1 text-ink">{(fixedStudent ?? student)?.display_name ?? "Not selected"}{(fixedStudent ?? student)?.institutional_id ? ` · ${(fixedStudent ?? student)?.institutional_id}` : ""}</dd></div>
          <div><dt className="text-xs font-semibold text-muted">Course / Year</dt><dd className="mt-1 text-ink">{draft.courseYear || "Not entered"}</dd></div>
          <div><dt className="text-xs font-semibold text-muted">Destination</dt><dd className="mt-1 text-ink">{selectedDestination}</dd></div>
          <div><dt className="text-xs font-semibold text-muted">Report date and time</dt><dd className="mt-1 text-ink">{formatInstitutionalDateTime(institutionalDateTimeInputToISO(draft.reportAt))} {INSTITUTION_TIME_ZONE_LABEL}</dd></div>
          <div className="sm:col-span-2"><dt className="text-xs font-semibold text-muted">Issuance mode</dt><dd className="mt-1 text-ink">{draft.notifyStudent ? "Issuing creates an in-app notification and queues the required email." : "Historical / back-entry — no new issuance notification."}</dd></div>
        </dl>
      </ConsequentialActionDialog>
    </div>
  );
}

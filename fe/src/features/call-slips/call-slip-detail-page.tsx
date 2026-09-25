"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Download } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { CallSlipAccessUnavailable, CallSlipHeading, CallSlipQueryError, callSlipDestinationLabel, callSlipErrorCode, callSlipErrorMessage, callSlipStateLabel, uncertainCallSlipMutation } from "@/features/call-slips/call-slips-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import {
  callSlipsDownloadMyPdf,
  callSlipsDownloadPdf,
  callSlipsRecordInterviewEnded,
  callSlipsVoid,
  getCallSlipsGetMyQueryKey,
  getCallSlipsGetQueryKey,
  getCallSlipsListMyQueryKey,
  getCallSlipsListQueryKey,
  useCallSlipsGet,
  useCallSlipsGetMy,
} from "@/lib/api/generated/call-slips/call-slips";
import type { CallSlipOperationalResponse, CallSlipStudentResponse } from "@/lib/api/generated/model";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { dateTimeInputToISO, formatDateTime, isFutureDateTimeInput, localDateInputValue } from "@/lib/date-time";

export function CallSlipDetailPage({ callSlipId }: { callSlipId: string }) {
  const { user } = usePortalSession();
  const access = getCallSlipAccess(user);

  if (access.canViewSelf) return <StudentCallSlipDetail callSlipId={callSlipId} />;
  if (access.canViewOperational) return <OperationalCallSlipDetail callSlipId={callSlipId} />;
  return <CallSlipAccessUnavailable />;
}

function StudentCallSlipDetail({ callSlipId }: { callSlipId: string }) {
  const slip = useCallSlipsGetMy(callSlipId, { query: { retry: false } });

  if (slip.isError) return <CallSlipQueryError error={slip.error} fallback="Call Slip detail could not be loaded." onRetry={() => void slip.refetch()} />;
  if (slip.isPending) return <CallSlipLoading />;

  const item = slip.data.data;
  return (
    <main className="space-y-7">
      <CallSlipHeading title="Call Slip / Interview Permit" description="Your Call Slip details" backHref="/portal/call-slips" backLabel="Back to My Call Slips" action={<CallSlipPdfDownload callSlipId={item.id} studentFacing />} />
      {item.state === "VOIDED" ? <div role="status" className="border-y border-warning/30 py-4"><p className="font-semibold text-warning">Withdrawn</p><p className="mt-1 text-sm text-ink">This Call Slip is no longer active.</p></div> : null}
      <RecordSection title="Permit details">
        <Field label="Student identity" value={item.student.display_name} />
        <Field label="Name on source Call Slip" value={item.student_name_snapshot} />
        <Field label="Course / Year" value={item.course_year_snapshot} />
        <Field label="Please report to" value={callSlipDestinationLabel(item.destination_type, item.other_destination)} />
        <Field label="Date and time to report" value={formatDateTime(item.report_at)} />
      </RecordSection>
      <section aria-labelledby="student-call-slip-instruction" className="border-t border-border py-6">
        <h2 id="student-call-slip-instruction" className="font-heading text-xl font-semibold text-ink">Instruction</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink">Please show this permit to your instructor/professor and proceed according to the permit.</p>
      </section>
      <RecordSection title="Issuance and status">
        <Field label="Guidance Counselor issuer (source snapshot)" value={item.issued_by_name_snapshot} />
        <Field label="State" value={callSlipStateLabel(item.state, true)} />
        <Field label="Current issuer account" value={item.issued_by.display_name} />
        <Field label="Interview ended" value={formatDateTime(item.interview_ended_at)} />
        <Field label="Recorded in COMPASS" value={formatDateTime(item.created_at)} />
      </RecordSection>
      <FormRevisionSection revision={item.form_revision} />
    </main>
  );
}

function OperationalCallSlipDetail({ callSlipId }: { callSlipId: string }) {
  const { user } = usePortalSession();
  const referralAccess = getReferralAccess(user);
  const slip = useCallSlipsGet(callSlipId, { query: { retry: false } });

  if (slip.isError) return <CallSlipQueryError error={slip.error} fallback="Call Slip detail could not be loaded." onRetry={() => void slip.refetch()} />;
  if (slip.isPending) return <CallSlipLoading />;

  const item = slip.data.data;
  return (
    <main className="space-y-7">
      <CallSlipHeading title="Call Slip / Interview Permit" description="Operational source record" backHref="/portal/call-slips" action={<CallSlipPdfDownload callSlipId={item.id} />} />
      {item.state === "VOIDED" ? (
        <div role="status" className="border-y border-warning/30 py-4">
          <p className="font-semibold text-warning">Voided</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{item.void_reason}</p>
          {item.voided_at ? <p className="mt-1 text-sm text-muted">Voided {formatDateTime(item.voided_at)}</p> : null}
        </div>
      ) : null}
      <RecordSection title="Permit details">
        <Field label="Student on source Call Slip" value={item.student_name_snapshot} />
        <Field label="Current Student identity" value={item.student.display_name} />
        <Field label="Course / Year" value={item.course_year_snapshot} />
        <Field label="Please report to" value={callSlipDestinationLabel(item.destination_type, item.other_destination)} />
        <Field label="Date and time to report" value={formatDateTime(item.report_at)} />
      </RecordSection>
      <section aria-labelledby="operational-call-slip-instruction" className="border-t border-border py-6">
        <h2 id="operational-call-slip-instruction" className="font-heading text-xl font-semibold text-ink">Source instruction</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink">Please show this permit to the Student&apos;s instructor/professor and proceed according to the permit.</p>
      </section>
      <RecordSection title="Issuance and recordkeeping">
        <Field label="Guidance Counselor issuer" value={item.issued_by_name_snapshot} />
        <Field label="Issuer account" value={item.issued_by.display_name} />
        <Field label="Recorded by" value={item.recorded_by?.display_name ?? "Not separately recorded"} />
        <Field label="State" value={callSlipStateLabel(item.state)} />
        <Field label="Interview ended" value={formatDateTime(item.interview_ended_at)} />
        <Field label="Created in COMPASS" value={formatDateTime(item.created_at)} />
        <Field label="Last updated" value={formatDateTime(item.updated_at)} />
      </RecordSection>
      <FormRevisionSection revision={item.form_revision} />
      {item.referral ? (
        <section aria-labelledby="linked-referral-heading" className="border-t border-border py-6">
          <h2 id="linked-referral-heading" className="font-heading text-xl font-semibold text-ink">Linked Referral</h2>
          {referralAccess.canView ? (
            <Link href={`/portal/referrals/${item.referral.id}`} className="mt-3 inline-block font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Open linked Referral {item.referral.reference_code}</Link>
          ) : <p className="mt-3 text-sm text-muted">A linked Referral exists, but its reference is unavailable in your current access.</p>}
        </section>
      ) : null}
      <CallSlipLifecycleActions slip={item} onRefresh={async () => {
        const refreshed = await slip.refetch();
        return refreshed.isSuccess ? refreshed.data.data : undefined;
      }} />
    </main>
  );
}

function CallSlipLoading() {
  return <div className="space-y-4" aria-busy="true"><span className="sr-only">Loading Call Slip…</span><Skeleton className="h-16 w-full" /><Skeleton className="h-48 w-full" /><Skeleton className="h-32 w-full" /></div>;
}

function Field({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm text-ink">{value}</dd></div>;
}

function RecordSection({ title, children }: { title: string; children: ReactNode }) {
  return <section aria-label={title} className="border-t border-border py-6"><h2 className="font-heading text-xl font-semibold text-ink">{title}</h2><dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">{children}</dl></section>;
}

function FormRevisionSection({ revision }: { revision: CallSlipStudentResponse["form_revision"] }) {
  return (
    <section aria-labelledby="call-slip-form-revision-heading" className="border-t border-border py-6">
      <h2 id="call-slip-form-revision-heading" className="font-heading text-xl font-semibold text-ink">Form provenance</h2>
      <dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">
        <Field label="Official form code" value={revision.official_code ?? "Official code not recorded"} />
        <Field label="Official revision" value={revision.official_revision ? `Revision ${revision.official_revision}` : "Official revision not recorded"} />
        <Field label="Internal schema version" value={String(revision.internal_schema_version)} />
      </dl>
    </section>
  );
}

function CallSlipPdfDownload({ callSlipId, studentFacing = false }: { callSlipId: string; studentFacing?: boolean }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setPending(true);
    setError(null);
    try {
      const response = studentFacing ? await callSlipsDownloadMyPdf(callSlipId) : await callSlipsDownloadPdf(callSlipId);
      downloadBinaryResponse(response, `call-slip-${callSlipId}.pdf`);
    } catch (caught) {
      setError(callSlipErrorMessage(caught, "The document could not be released right now. Try again later."));
    } finally {
      setPending(false);
    }
  }

  return <div className="flex flex-col items-start gap-2 sm:items-end"><Button variant="secondary" onClick={() => void download()} disabled={pending}><Download aria-hidden="true" size={16} />{pending ? "Preparing…" : "Download Call Slip"}</Button>{error ? <p role="alert" className="max-w-sm text-sm text-danger">{error}</p> : null}</div>;
}

function CallSlipLifecycleActions({ slip, onRefresh }: { slip: CallSlipOperationalResponse; onRefresh: () => Promise<CallSlipOperationalResponse | undefined> }) {
  if (slip.state !== "ACTIVE") return null;
  return (
    <section aria-labelledby="call-slip-actions-heading" className="border-t border-border py-6">
      <h2 id="call-slip-actions-heading" className="font-heading text-xl font-semibold text-ink">Operational actions</h2>
      {!slip.interview_ended_at ? <RecordInterviewEnd slip={slip} onRefresh={onRefresh} /> : <p className="mt-3 text-sm text-muted">Interview end is recorded at {formatDateTime(slip.interview_ended_at)} and cannot be edited.</p>}
      <VoidCallSlip slip={slip} onRefresh={onRefresh} />
    </section>
  );
}

function RecordInterviewEnd({ slip, onRefresh }: { slip: CallSlipOperationalResponse; onRefresh: () => Promise<CallSlipOperationalResponse | undefined> }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reconcileRequired, setReconcileRequired] = useState(false);
  const mutation = useMutation({
    mutationFn: () => callSlipsRecordInterviewEnded(slip.id, { interview_ended_at: dateTimeInputToISO(value)! }),
    retry: false,
  });

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getCallSlipsGetQueryKey(slip.id) }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsGetMyQueryKey(slip.id) }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey() }),
      ...(slip.referral ? [queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey({ referral_id: slip.referral.id }) })] : []),
    ]);
  }

  async function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const iso = dateTimeInputToISO(value);
    if (!iso) return setError("Enter a valid interview end date and time.");
    if (isFutureDateTimeInput(value)) return setError("Interview end date and time cannot be in the future.");
    setConfirmOpen(true);
  }

  async function record() {
    if (reconcileRequired) {
      const refreshed = await onRefresh();
      if (!refreshed) return setError("The Call Slip could not be refreshed. Do not retry until its current state can be checked.");
      setReconcileRequired(false);
      if (refreshed.interview_ended_at) {
        setConfirmOpen(false);
        setNotice(`Interview end is recorded at ${formatDateTime(refreshed.interview_ended_at)}.`);
        await invalidate();
      } else {
        setError("No interview end is recorded after refresh. Review the same timestamp and explicitly submit again if it remains correct.");
      }
      return;
    }
    setError(null);
    try {
      await mutation.mutateAsync();
      setConfirmOpen(false);
      setNotice("Interview end recorded.");
      setValue("");
      await invalidate();
    } catch (caught) {
      if (callSlipErrorCode(caught) === "recent_mfa_required") {
        setConfirmOpen(false);
        setNotice("Verify your authenticator, then review and record the interview end again.");
        setStepUpOpen(true);
      } else if (callSlipErrorCode(caught) === "call_slip_conflict" || uncertainCallSlipMutation(caught)) {
        const refreshed = await onRefresh();
        if (refreshed?.interview_ended_at) {
          setConfirmOpen(false);
          setNotice(`Interview end is recorded at ${formatDateTime(refreshed.interview_ended_at)}.`);
          await invalidate();
        } else if (refreshed) {
          setConfirmOpen(false);
          setError(callSlipErrorMessage(caught, "The interview end was not found after refreshing. Review the timestamp before submitting again."));
        } else {
          setConfirmOpen(false);
          setReconcileRequired(true);
          setError("The Call Slip could not be refreshed. Do not retry until its current state can be checked.");
        }
      } else {
        setError(callSlipErrorMessage(caught, "Interview end could not be recorded."));
      }
    }
  }

  return (
    <div className="mt-4 max-w-2xl border-b border-border pb-6">
      <h3 className="font-semibold text-ink">Record interview end</h3>
      <p className="mt-1 text-sm leading-6 text-muted">This records only the source Call Slip&apos;s interview-end time. It does not complete an Appointment or Counseling record.</p>
      <form className="mt-4 space-y-3" onSubmit={prepare} aria-busy={mutation.isPending}>
        <div className="grid gap-2 sm:max-w-sm">
          <Label htmlFor="call-slip-interview-ended">Interview ended</Label>
          <Input id="call-slip-interview-ended" type="datetime-local" step="60" required max={`${localDateInputValue()}T23:59`} value={value} disabled={mutation.isPending || reconcileRequired} onChange={(event) => setValue(event.target.value)} />
        </div>
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
        <Button type="submit" variant="secondary" disabled={mutation.isPending || reconcileRequired}>{reconcileRequired ? "Refresh required" : "Review interview end"}</Button>
        {reconcileRequired ? <Button type="button" variant="secondary" className="ml-2" onClick={() => void record()}>Refresh Call Slip</Button> : null}
      </form>
      <AlertDialog open={confirmOpen} onOpenChange={(open) => { if (!mutation.isPending) setConfirmOpen(open); }}>
        <AlertDialogContent onEscapeKeyDown={(event) => { if (mutation.isPending) event.preventDefault(); }}>
          <AlertDialogTitle>Record interview end?</AlertDialogTitle>
          <AlertDialogDescription>This source timestamp becomes immutable after it is recorded.</AlertDialogDescription>
          <p className="mt-4 text-sm text-ink">{value}</p>
          {error ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2"><AlertDialogCancel asChild><Button variant="secondary" disabled={mutation.isPending}>Review details</Button></AlertDialogCancel><Button disabled={mutation.isPending} onClick={() => void record()}>{mutation.isPending ? "Recording…" : "Record interview end"}</Button></div>
        </AlertDialogContent>
      </AlertDialog>
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => { setNotice("Verification complete. Review and record the interview end again."); setConfirmOpen(true); }} />
    </div>
  );
}

function VoidCallSlip({ slip, onRefresh }: { slip: CallSlipOperationalResponse; onRefresh: () => Promise<CallSlipOperationalResponse | undefined> }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [reconcileRequired, setReconcileRequired] = useState(false);
  const mutation = useMutation({ mutationFn: () => callSlipsVoid(slip.id, { reason: reason.trim() }), retry: false });

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getCallSlipsGetQueryKey(slip.id) }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsGetMyQueryKey(slip.id) }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsListMyQueryKey() }),
      ...(slip.referral ? [queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey({ referral_id: slip.referral.id }) })] : []),
    ]);
  }

  async function confirmVoid() {
    setError(null);
    setNotice(null);
    if (reconcileRequired) {
      const refreshed = await onRefresh();
      if (!refreshed) return setError("The Call Slip could not be refreshed. Do not retry the void until its current state can be checked.");
      setReconcileRequired(false);
      if (refreshed.state === "VOIDED") {
        setOpen(false);
        setNotice("This Call Slip is withdrawn.");
        await invalidate();
      } else {
        setError("The Call Slip is not shown as withdrawn after refresh. Review the current record before confirming again.");
      }
      return;
    }
    if (!reason.trim()) return setError("Void reason is required.");
    try {
      await mutation.mutateAsync();
      setOpen(false);
      setReason("");
      setNotice("Call Slip withdrawn. The Student will be notified.");
      await invalidate();
    } catch (caught) {
      if (callSlipErrorCode(caught) === "recent_mfa_required") {
        setOpen(false);
        setNotice("Verify your authenticator, then review and confirm the void again.");
        setStepUpOpen(true);
      } else if (callSlipErrorCode(caught) === "call_slip_conflict" || uncertainCallSlipMutation(caught)) {
        const refreshed = await onRefresh();
        if (refreshed?.state === "VOIDED") {
          setOpen(false);
          setNotice("This Call Slip is withdrawn.");
          await invalidate();
        } else if (refreshed) {
          setOpen(false);
          setError(callSlipErrorMessage(caught, "The Call Slip is not shown as withdrawn after refresh. Review the current record before confirming again."));
        } else {
          setOpen(false);
          setReconcileRequired(true);
          setError("The Call Slip could not be refreshed. Do not retry the void until its current state can be checked.");
        }
      } else {
        setError(callSlipErrorMessage(caught, "The Call Slip could not be voided."));
      }
    }
  }

  return (
    <div className="mt-6 border-t border-border pt-6">
      <Button variant="danger" onClick={() => { setError(null); setNotice(null); setOpen(true); }}>Void Call Slip</Button>
      {error ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
      {notice ? <p role="status" className="mt-3 text-sm text-muted">{notice}</p> : null}
      {reconcileRequired ? <Button className="mt-3" variant="secondary" onClick={() => void confirmVoid()}>Refresh Call Slip state</Button> : null}
      <AlertDialog open={open} onOpenChange={(next) => { if (!mutation.isPending) setOpen(next); }}>
        <AlertDialogContent onEscapeKeyDown={(event) => { if (mutation.isPending) event.preventDefault(); }}>
          <AlertDialogTitle>Void this Call Slip?</AlertDialogTitle>
          <AlertDialogDescription>The Student will be notified that this Call Slip has been withdrawn. This notification is sent even when the permit was originally entered as historical/back-entry.</AlertDialogDescription>
          <div className="mt-4 grid gap-2"><Label htmlFor="call-slip-void-reason">Void reason</Label><Textarea id="call-slip-void-reason" rows={3} maxLength={1_000} required value={reason} disabled={mutation.isPending} onChange={(event) => setReason(event.target.value)} /><p className="text-xs text-muted">{reason.length} / 1,000 characters</p></div>
          {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2"><AlertDialogCancel asChild><Button variant="secondary" disabled={mutation.isPending}>Cancel</Button></AlertDialogCancel><Button variant="danger" disabled={mutation.isPending || !reason.trim()} onClick={() => void confirmVoid()}>{mutation.isPending ? "Voiding…" : "Void Call Slip"}</Button></div>
        </AlertDialogContent>
      </AlertDialog>
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => { setNotice("Verification complete. Review the reason and confirm the void again."); setOpen(true); }} />
    </div>
  );
}

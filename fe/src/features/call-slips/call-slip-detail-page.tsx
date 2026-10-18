"use client";

import { ArrowUpRight, Download } from "lucide-react";
import { PageAction, PageActionGroup, PageActionLink } from "@/components/ui/page-action";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";

import { CallSlipHelp } from "@/features/call-slips/call-slip-help";
import { IconAction } from "@/components/ui/icon-action";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelSection, RecordSummary } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { CallSlipAccessUnavailable, CallSlipDetailSkeleton, CallSlipHeading, CallSlipQueryError, CallSlipStatusBadge, callSlipDestinationLabel, callSlipErrorCode, callSlipErrorMessage, callSlipIssuanceModeLabels, uncertainCallSlipMutation } from "@/features/call-slips/call-slips-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { PersonAvatar } from "@/features/account/components/person-avatar";
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
import { CallSlipLifecycleStateValue } from "@/lib/api/generated/model";
import type { CallSlipOperationalResponse, CallSlipStudentResponse } from "@/lib/api/generated/model";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { institutionalPdfFallbackFilename } from "@/lib/institutional-pdf-filenames";
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateInputValue,
  institutionalDateTimeInputToISO,
  isFutureInstitutionalDateTimeInput,
} from "@/lib/institutional-time";

export function CallSlipDetailPage({ callSlipId }: { callSlipId: string }) {
  const { user } = usePortalSession();
  const access = getCallSlipAccess(user);

  if (access.canViewSelf) return <StudentCallSlipDetail callSlipId={callSlipId} />;
  if (access.canViewOperational) return <OperationalCallSlipDetail callSlipId={callSlipId} />;
  return <CallSlipAccessUnavailable />;
}

function StudentCallSlipDetail({ callSlipId }: { callSlipId: string }) {
  const slip = useCallSlipsGetMy(callSlipId, { query: { retry: false } });
  const confirmed = safeQueryData(slip);

  if (slip.isError && !confirmed) return <div className="space-y-5"><CallSlipHeading title="Call Slip / Interview Permit" backHref="/portal/call-slips" /><CallSlipQueryError error={slip.error} fallback="Call Slip detail could not be loaded." onRetry={() => void slip.refetch()} /></div>;
  if (slip.isPending) return <CallSlipDetailSkeleton />;
  if (!confirmed) return <CallSlipDetailSkeleton />;

  const item = confirmed.data;
  return (
    <div className="space-y-5">
      {slip.isError ? <RefreshFailureNotice onRetry={() => void slip.refetch()} retrying={slip.isFetching} /> : null}
      <CallSlipHeading title="Call Slip / Interview Permit" backHref="/portal/call-slips" backLabel="Back to My Call Slips" />
      <div data-page-action-layout="call-slip" className="grid gap-4 lg:grid-cols-[7rem_minmax(0,1fr)] lg:gap-5">
        <PageActionGroup
          aria-label="Call Slip page actions"
          data-page-action-rail=""
          className="empty:hidden lg:sticky lg:top-4 lg:flex-col lg:items-center lg:gap-x-0 lg:gap-y-3"
        >
          <CallSlipPdfDownload callSlipId={item.id} studentFacing />
        </PageActionGroup>
        <div className="min-w-0 space-y-5">
          {item.state === CallSlipLifecycleStateValue.VOIDED ? <Notice role="status" tone="warning" title={<span className="text-warning">Withdrawn</span>}><p className="text-ink">This Call Slip is no longer active.</p></Notice> : null}
          <Panel as="div">
            <RecordSummary
              label="Name on Call Slip"
              title={item.student_name_snapshot}
              titleId="student-call-slip-summary"
              status={<CallSlipStatusBadge state={item.state} studentFacing />}
              facts={[
                { label: "Current Student identity", value: <span className="inline-flex items-center gap-2"><PersonAvatar displayName={item.student.display_name} photoUrl={item.student.profile_photo_url} photoUpdatedAt={item.student.profile_photo_updated_at} size="compact" />{item.student.display_name}</span> },
                { label: "Course / Year", value: item.course_year_snapshot },
                { label: "Please report to", value: callSlipDestinationLabel(item.destination_type, item.other_destination) },
                { label: "Date and time to report", value: formatInstitutionalDateTime(item.report_at) },
              ]}
            />
            <PanelSection title="Instruction" titleId="student-call-slip-instruction">
              <p className="max-w-3xl text-sm leading-6 text-ink">Show this Call Slip to your instructor and report to {callSlipDestinationLabel(item.destination_type, item.other_destination)}.</p>
            </PanelSection>
            <RecordSection title="Issuance">
              <Field label="Issuing Guidance Counselor" value={item.issued_by_name_snapshot} />
              <Field label="Current issuer account" value={item.issued_by.display_name} />
              <Field label="Interview ended" value={formatInstitutionalDateTime(item.interview_ended_at)} />
              <Field label="Recorded in COMPASS" value={formatInstitutionalDateTime(item.created_at)} />
            </RecordSection>
            <FormRevisionSection revision={item.form_revision} />
          </Panel>
        </div>
      </div>
    </div>
  );
}

function OperationalCallSlipDetail({ callSlipId }: { callSlipId: string }) {
  const { user } = usePortalSession();
  const access = getCallSlipAccess(user);
  const referralAccess = getReferralAccess(user);
  const slip = useCallSlipsGet(callSlipId, { query: { retry: false } });
  const confirmed = safeQueryData(slip);

  if (slip.isError && !confirmed) return <div className="space-y-5"><CallSlipHeading title="Call Slip / Interview Permit" backHref="/portal/call-slips" /><CallSlipQueryError error={slip.error} fallback="Call Slip detail could not be loaded." onRetry={() => void slip.refetch()} /></div>;
  if (slip.isPending) return <CallSlipDetailSkeleton />;
  if (!confirmed) return <CallSlipDetailSkeleton />;

  const item = confirmed.data;
  return (
    <div className="space-y-5">
      {slip.isError ? <RefreshFailureNotice onRetry={() => void slip.refetch()} retrying={slip.isFetching} /> : null}
      <CallSlipHeading title="Call Slip / Interview Permit" backHref="/portal/call-slips" help={<CallSlipHelp />} />
      <div data-page-action-layout="call-slip" className="grid gap-4 lg:grid-cols-[7rem_minmax(0,1fr)] lg:gap-5">
        <PageActionGroup
          aria-label="Call Slip page actions"
          data-page-action-rail=""
          className="empty:hidden lg:sticky lg:top-4 lg:flex-col lg:items-center lg:gap-x-0 lg:gap-y-3"
        >
          <CallSlipPdfDownload callSlipId={item.id} />
          {item.referral && referralAccess.canView ? (
            <PageActionLink href={`/portal/referrals/${item.referral.id}`} icon={ArrowUpRight} variant="secondary" label="Open Referral" labelDetail={item.referral.reference_code} />
          ) : null}
        </PageActionGroup>
        <div className="min-w-0 space-y-5">
          {item.state === CallSlipLifecycleStateValue.VOIDED ? (
            <Notice role="status" tone="warning" title={<span className="text-warning">Voided</span>}>
              <p className="whitespace-pre-wrap text-ink">{item.void_reason}</p>
              {item.voided_at ? <p className="mt-1 text-muted">Voided {formatInstitutionalDateTime(item.voided_at)}</p> : null}
              {item.voided_by ? <p className="mt-1 text-muted">Voided by {item.voided_by.display_name}</p> : null}
            </Notice>
          ) : null}
          <Panel as="div">
            <RecordSummary
              label="Name on Call Slip"
              title={item.student_name_snapshot}
              titleId="operational-call-slip-summary"
              status={<CallSlipStatusBadge state={item.state} />}
              facts={[
                { label: "Current Student identity", value: <span className="inline-flex items-center gap-2"><PersonAvatar displayName={item.student.display_name} photoUrl={item.student.profile_photo_url} photoUpdatedAt={item.student.profile_photo_updated_at} size="compact" />{item.student.display_name}</span> },
                ...(item.student_institutional_id ? [{ label: "Institutional ID", value: item.student_institutional_id }] : []),
                { label: "Course / Year", value: item.course_year_snapshot },
                { label: "Please report to", value: callSlipDestinationLabel(item.destination_type, item.other_destination) },
                { label: "Date and time to report", value: formatInstitutionalDateTime(item.report_at) },
              ]}
            />
            <PanelSection title="Source instruction" titleId="operational-call-slip-instruction">
              <p className="max-w-3xl text-sm leading-6 text-ink">Show to the instructor; report to {callSlipDestinationLabel(item.destination_type, item.other_destination)}.</p>
            </PanelSection>
            <RecordSection title="Issuance and recordkeeping">
              <Field label="Issuer name on Call Slip" value={item.issued_by_name_snapshot} />
              <Field label="Current issuer account" value={item.issued_by.display_name} />
              <Field label="Recorded by" value={item.recorded_by?.display_name ?? "Not separately recorded"} />
              <Field label="Issuance mode" value={callSlipIssuanceModeLabels[item.issuance_mode]} />
              <Field label="Interview ended" value={formatInstitutionalDateTime(item.interview_ended_at)} />
              <Field label="Created in COMPASS" value={formatInstitutionalDateTime(item.created_at)} />
              <Field label="Last updated" value={formatInstitutionalDateTime(item.updated_at)} />
            </RecordSection>
            <FormRevisionSection revision={item.form_revision} />
            {item.referral && !referralAccess.canView ? (
              <PanelSection title="Linked Referral" titleId="linked-referral-heading">
                <p className="text-sm text-muted">A linked referral exists, but its reference is unavailable to this account.</p>
              </PanelSection>
            ) : null}
          </Panel>
          {access.canManageOperational && !slip.isError ? <CallSlipLifecycleActions slip={item} onRefresh={async () => {
            const refreshed = await slip.refetch();
            return refreshed.isSuccess ? refreshed.data.data : undefined;
          }} /> : null}
        </div>
      </div>
    </div>
  );
}


function Field({ label, value }: { label: string; value: ReactNode }) {
  return <div><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm text-ink">{value}</dd></div>;
}

function RecordSection({ title, children }: { title: string; children: ReactNode }) {
  const titleId = "call-slip-" + title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return <PanelSection title={title} titleId={titleId}><dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">{children}</dl></PanelSection>;
}

function FormRevisionSection({ revision }: { revision: CallSlipStudentResponse["form_revision"] }) {
  return (
    <PanelSection title="Official form" titleId="call-slip-form-revision-heading">
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Official form code" value={revision.official_code ?? "Official code not recorded"} />
        <Field label="Official revision" value={revision.official_revision ? `Revision ${revision.official_revision}` : "Official revision not recorded"} />
      </dl>
    </PanelSection>
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
      downloadBinaryResponse(response, institutionalPdfFallbackFilename("callSlip", callSlipId));
    } catch (caught) {
      setError(callSlipErrorMessage(caught, "The document could not be released right now. Try again later."));
    } finally {
      setPending(false);
    }
  }

  return <div className="flex flex-col items-center gap-2"><PageAction icon={Download} variant="secondary" label={pending ? "Preparing Call Slip…" : "Download"} labelDetail={pending ? undefined : "Call Slip"} onClick={() => void download()} disabled={pending} aria-busy={pending} />{error ? <p role="alert" className="w-28 text-center text-xs text-danger">{error}</p> : null}</div>;
}

function CallSlipLifecycleActions({ slip, onRefresh }: { slip: CallSlipOperationalResponse; onRefresh: () => Promise<CallSlipOperationalResponse | undefined> }) {
  if (slip.state !== CallSlipLifecycleStateValue.ACTIVE) return null;
  return (
    <Panel aria-labelledby="call-slip-actions-heading">
      <PanelHeader title="Operational actions" titleId="call-slip-actions-heading" />
      {!slip.interview_ended_at ? <RecordInterviewEnd slip={slip} onRefresh={onRefresh} /> : <p className="px-4 py-4 text-sm text-muted sm:px-5">Interview end is recorded at {formatInstitutionalDateTime(slip.interview_ended_at)} and cannot be edited.</p>}
      <VoidCallSlip slip={slip} onRefresh={onRefresh} />
    </Panel>
  );
}

function RecordInterviewEnd({ slip, onRefresh }: { slip: CallSlipOperationalResponse; onRefresh: () => Promise<CallSlipOperationalResponse | undefined> }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reconcileRequired, setReconcileRequired] = useState(false);
  const mutation = useMutation({
    mutationFn: () => callSlipsRecordInterviewEnded(slip.id, { interview_ended_at: institutionalDateTimeInputToISO(value)! }),
    retry: false,
  });

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getCallSlipsGetQueryKey(slip.id) }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsGetMyQueryKey(slip.id) }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey() }),
      invalidateGuidanceWork(queryClient),
      ...(slip.referral ? [queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey({ referral_id: slip.referral.id }) })] : []),
    ]);
  }

  async function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const iso = institutionalDateTimeInputToISO(value);
    if (!iso) return setError("Enter a valid interview end date and time.");
    if (isFutureInstitutionalDateTimeInput(value)) return setError("Interview end date and time cannot be in the future.");
    setConfirmOpen(true);
  }

  async function record() {
    if (reconcileRequired) {
      const refreshed = await onRefresh();
      if (!refreshed) return setError("The Call Slip could not be refreshed. Do not retry until its current state can be checked.");
      setReconcileRequired(false);
      if (refreshed.interview_ended_at) {
        setConfirmOpen(false);
        setNotice(`Interview end is recorded at ${formatInstitutionalDateTime(refreshed.interview_ended_at)}.`);
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
      if (callSlipErrorCode(caught) === "call_slip_conflict" || uncertainCallSlipMutation(caught)) {
        const refreshed = await onRefresh();
        if (refreshed?.interview_ended_at) {
          setConfirmOpen(false);
          setNotice(`Interview end is recorded at ${formatInstitutionalDateTime(refreshed.interview_ended_at)}.`);
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
    <div className="px-4 py-4 sm:px-5">
      <h3 className="font-semibold text-ink">Record interview end</h3>
      <p className="mt-1 text-sm leading-6 text-muted">Record when the interview ended. Times use {INSTITUTION_TIME_ZONE_LABEL}.</p>
      <form className="mt-4 max-w-2xl space-y-3" onSubmit={prepare} aria-busy={mutation.isPending}>
        <div className="grid gap-2 sm:max-w-sm">
          <Label htmlFor="call-slip-interview-ended">Interview ended</Label>
          <Input id="call-slip-interview-ended" type="datetime-local" step="60" required max={`${institutionalDateInputValue()}T23:59`} value={value} disabled={mutation.isPending || reconcileRequired} onChange={(event) => setValue(event.target.value)} />
        </div>
        {error && !confirmOpen ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
        <Button
          type="submit"
          variant="secondary"
          disabled={mutation.isPending || reconcileRequired}
          onClick={(event) => event.currentTarget.focus()}
        >
          {reconcileRequired ? "Refresh required" : "Review interview end"}
        </Button>
        {reconcileRequired ? <IconAction action="refresh" label="Refresh Call Slip" className="ml-2" onClick={() => void record()} /> : null}
      </form>
      <ConsequentialActionDialog
        open={confirmOpen}
        title="Record interview end?"
        confirmLabel="Record interview end"
        pendingLabel="Recording…"
        pending={mutation.isPending}
        confirmDisabled={reconcileRequired}
        error={error}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void record()}
      >
        <p>This time cannot be changed once saved. It does not complete a related Appointment or Counseling record.</p>
        <p className="font-semibold text-ink">
          {formatInstitutionalDateTime(institutionalDateTimeInputToISO(value))}{" "}
          {INSTITUTION_TIME_ZONE_LABEL}
        </p>
      </ConsequentialActionDialog>
    </div>
  );
}

function VoidCallSlip({ slip, onRefresh }: { slip: CallSlipOperationalResponse; onRefresh: () => Promise<CallSlipOperationalResponse | undefined> }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reconcileRequired, setReconcileRequired] = useState(false);
  const mutation = useMutation({ mutationFn: () => callSlipsVoid(slip.id, { reason: reason.trim() }), retry: false });

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getCallSlipsGetQueryKey(slip.id) }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsGetMyQueryKey(slip.id) }),
      queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey() }),
      invalidateGuidanceWork(queryClient),
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
      if (refreshed.state === CallSlipLifecycleStateValue.VOIDED) {
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
      setNotice(
        slip.void_notifies_student
          ? "Call Slip withdrawn. The Student will be notified."
          : "Call Slip withdrawn. No Student notification was sent because it was recorded as a historical entry.",
      );
      await invalidate();
    } catch (caught) {
      if (callSlipErrorCode(caught) === "call_slip_conflict" || uncertainCallSlipMutation(caught)) {
        const refreshed = await onRefresh();
        if (refreshed?.state === CallSlipLifecycleStateValue.VOIDED) {
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
    <div className="border-t border-brand-line px-4 py-4 sm:px-5">
      <Button variant="danger" onClick={() => { setError(null); setNotice(null); setOpen(true); }}>Void Call Slip</Button>
      {error && !open ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
      {notice ? <p role="status" className="mt-3 text-sm text-muted">{notice}</p> : null}
      {reconcileRequired ? <IconAction className="mt-3" action="refresh" label="Refresh Call Slip" onClick={() => void confirmVoid()} /> : null}
      <ConsequentialActionDialog
        open={open}
        title="Void this Call Slip?"
        confirmLabel="Void Call Slip"
        pendingLabel="Voiding…"
        pending={mutation.isPending}
        confirmDisabled={reconcileRequired || !reason.trim()}
        error={error}
        variant="danger"
        onOpenChange={setOpen}
        onConfirm={() => void confirmVoid()}
      >
        <p>
          {slip.void_notifies_student
            ? "The Student will be notified that this Call Slip has been withdrawn."
            : "This Call Slip was recorded as a historical entry, so the Student will not be notified that it was withdrawn."}
        </p>
        <div className="grid gap-2">
          <Label htmlFor="call-slip-void-reason">Void reason</Label>
          <Textarea
            id="call-slip-void-reason"
            rows={3}
            maxLength={1_000}
            required
            value={reason}
            disabled={mutation.isPending}
            onChange={(event) => setReason(event.target.value)}
          />
          <p className="text-xs text-muted">{reason.length} / 1,000 characters</p>
        </div>
      </ConsequentialActionDialog>
    </div>
  );
}

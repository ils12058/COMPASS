"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { CallSlipFormFields, type CallSlipDraft, toCallSlipRequestFields } from "@/features/call-slips/call-slip-form-fields";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { CallSlipAccessUnavailable, CallSlipHeading, CallSlipQueryError, callSlipDestinationLabel, callSlipErrorCode, callSlipErrorMessage, callSlipStateLabel, uncertainCallSlipMutation } from "@/features/call-slips/call-slips-shared";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { ReferralAccessUnavailable, ReferralQueryError } from "@/features/referrals/referrals-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { callSlipsCreateFromReferral, getCallSlipsListQueryKey, useCallSlipsList } from "@/lib/api/generated/call-slips/call-slips";
import { getReferralsGetQueryKey, useReferralsGet } from "@/lib/api/generated/referrals/referrals";
import { ReferralActionTypeValue } from "@/lib/api/generated/model";
import type { CallSlipCreateFromReferralRequest, ReferralDetailResponse } from "@/lib/api/generated/model";
import { dateTimeInputToISO, formatDateTime, isFutureDateTimeInput, localDateInputValue } from "@/lib/date-time";

type LinkedCreateIntent = { fingerprint: string; key: string; payload: CallSlipCreateFromReferralRequest };

export function CallSlipFromReferralPage({ referralId }: { referralId: string }) {
  const { user } = usePortalSession();
  const referralAccess = getReferralAccess(user);
  const callSlipAccess = getCallSlipAccess(user);
  const canUse = referralAccess.canView && callSlipAccess.canViewOperational && callSlipAccess.canManageOperational;
  const referral = useReferralsGet(referralId, { query: { enabled: canUse, retry: false } });
  const current = useCallSlipsList(
    { referral_id: referralId, include_voided: false, page: 1, page_size: 1 },
    { query: { enabled: canUse, retry: false } },
  );
  const history = useCallSlipsList(
    { referral_id: referralId, include_voided: true, page: 1, page_size: 20 },
    { query: { enabled: canUse, retry: false } },
  );

  if (!referralAccess.canView) return <ReferralAccessUnavailable title="Referral review unavailable" message="Review access is required to issue a linked Call Slip." />;
  if (!callSlipAccess.canViewOperational || !callSlipAccess.canManageOperational) return <CallSlipAccessUnavailable title="Linked Call Slip issuance unavailable" message="Operational Call Slip review and management access are required." />;
  if (referral.isError) return <ReferralQueryError error={referral.error} fallback="The source Referral could not be loaded." onRetry={() => void referral.refetch()} />;
  if (referral.isPending || current.isPending || history.isPending) {
    return <div className="space-y-4" aria-busy="true"><p role="status" className="text-sm text-muted">Checking Referral and linked Call Slip state…</p></div>;
  }
  if (current.isError) return <CallSlipQueryError error={current.error} fallback="Current linked Call Slip state could not be checked. Issuance is unavailable until it can be refreshed." onRetry={() => void current.refetch()} />;
  if (history.isError) return <CallSlipQueryError error={history.error} fallback="Linked Call Slip history could not be loaded." onRetry={() => void history.refetch()} />;

  const item = referral.data.data;
  const currentSlip = current.data.data.items[0];
  if (currentSlip) {
    return (
      <div className="space-y-7">
        <CallSlipHeading title={`Issue linked Call Slip · ${item.reference_code}`} description="This Referral already has a non-voided linked Call Slip." backHref={`/portal/referrals/${item.id}`} backLabel="Back to Referral" />
        <section className="border-y border-border py-5">
          <p className="font-semibold text-ink">{callSlipStateLabel(currentSlip.state)} linked permit</p>
          <p className="mt-2 text-sm text-muted">{formatDateTime(currentSlip.report_at)} · {callSlipDestinationLabel(currentSlip.destination_type, currentSlip.other_destination)}</p>
          <Link href={`/portal/call-slips/${currentSlip.id}`} className="mt-3 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Open linked Call Slip</Link>
        </section>
      </div>
    );
  }
  if (item.voided_at) {
    return <CallSlipAccessUnavailable title="Linked issuance unavailable" message="A voided Referral cannot receive a new linked Call Slip." />;
  }

  async function refreshContext() {
    await Promise.all([referral.refetch(), current.refetch(), history.refetch()]);
  }

  return (
    <div className="space-y-7">
      <CallSlipHeading title={`Issue linked Call Slip · ${item.reference_code}`} description="Issuing this Call Slip also records the action on the Referral in the same step." backHref={`/portal/referrals/${item.id}`} backLabel="Back to Referral" />
      <LinkedCallSlipHistory items={history.data.data.items} />
      <LinkedCallSlipCreateForm referral={item} onRefresh={refreshContext} />
    </div>
  );
}

function LinkedCallSlipHistory({ items }: { items: { id: string; state: string; report_at: string; destination_type: string; other_destination: string }[] }) {
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="previous-call-slips-heading" className="border-y border-border py-5">
      <h2 id="previous-call-slips-heading" className="font-heading text-lg font-semibold text-ink">Previous linked Call Slips</h2>
      <ul className="mt-3 divide-y divide-border">
        {items.map((slip) => (
          <li key={slip.id} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-sm text-ink">{callSlipStateLabel(slip.state)} · {formatDateTime(slip.report_at)} · {callSlipDestinationLabel(slip.destination_type, slip.other_destination)}</span>
            <Link href={`/portal/call-slips/${slip.id}`} className="min-h-9 self-start text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:self-auto">Open Call Slip</Link>
          </li>
        ))}
      </ul>
      {items.some((slip) => slip.state === "VOIDED") ? <p className="mt-3 text-sm text-muted">A new linked Call Slip can be issued. The existing Referral source action remains recorded and will not be duplicated.</p> : null}
    </section>
  );
}

function LinkedCallSlipCreateForm({ referral, onRefresh }: { referral: ReferralDetailResponse; onRefresh: () => Promise<void> }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const action = referral.actions.find((item) => item.action_type === ReferralActionTypeValue.SEND_CALL_SLIP_INTERVIEW_PERMIT);
  const [draft, setDraft] = useState<CallSlipDraft>(() => ({
    courseYear: referral.course_year_block_snapshot,
    destinationType: "GUIDANCE_OFFICE",
    otherDestination: "",
    reportAt: "",
    notifyStudent: true,
  }));
  const [occurredAt, setOccurredAt] = useState("");
  const [remarks, setRemarks] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const intent = useRef<LinkedCreateIntent | null>(null);
  const create = useMutation({
    mutationFn: ({ payload, key }: { payload: CallSlipCreateFromReferralRequest; key: string }) =>
      callSlipsCreateFromReferral(referral.id, payload, { headers: { "Idempotency-Key": key } }),
    retry: false,
  });

  function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const fields = toCallSlipRequestFields(draft);
    if (!fields) return setError("Complete Course / Year, destination, and report date and time.");
    const reportAt = dateTimeInputToISO(draft.reportAt);
    if (!reportAt) return setError("Enter a valid report date and time.");
    if (!action) {
      if (!occurredAt) return setError("Action occurred date and time is required for the first linked issuance.");
      if (!dateTimeInputToISO(occurredAt)) return setError("Enter a valid action occurred date and time.");
      if (isFutureDateTimeInput(occurredAt)) return setError("Action occurred date and time cannot be in the future.");
      const occurredInstant = new Date(occurredAt).getTime();
      if (referral.received_at) {
        if (occurredInstant < new Date(referral.received_at).getTime()) return setError("Action occurred date and time cannot be earlier than Guidance receipt.");
      } else if (occurredAt.slice(0, 10) < referral.referred_on) {
        return setError("Action date cannot be earlier than Date referred.");
      }
    }
    if (!globalThis.crypto?.randomUUID) return setError("This browser cannot create a secure issuance request. Update the browser and try again.");

    const payload: CallSlipCreateFromReferralRequest = {
      ...fields,
      report_at: reportAt,
      action: action ? null : { occurred_at: dateTimeInputToISO(occurredAt)!, remarks: remarks.trim() },
    };
    const fingerprint = JSON.stringify({ referralId: referral.id, payload });
    const key = intent.current?.fingerprint === fingerprint ? intent.current.key : globalThis.crypto.randomUUID();
    intent.current = { fingerprint, key, payload };
    setConfirmOpen(true);
  }

  async function issueConfirmed() {
    const currentIntent = intent.current;
    if (!currentIntent) {
      setConfirmOpen(false);
      setError("Review the linked Call Slip details again before issuing.");
      return;
    }
    setError(null);
    setNotice(null);
    try {
      const response = await create.mutateAsync({ payload: currentIntent.payload, key: currentIntent.key });
      const slip = response.data;
      intent.current = null;
      setConfirmOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getReferralsGetQueryKey(referral.id) }),
        queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey() }),
      ]);
      router.push(`/portal/call-slips/${slip.id}`);
    } catch (caught) {
      if (callSlipErrorCode(caught) === "recent_mfa_required") {
        setConfirmOpen(false);
        setNotice("Verify your authenticator, then review and confirm this linked issuance again.");
        setStepUpOpen(true);
      } else if (callSlipErrorCode(caught) === "idempotency_key_conflict") {
        intent.current = null;
        setConfirmOpen(false);
        setError(callSlipErrorMessage(caught, "This issuance attempt no longer matches its original details. Review the form and try again."));
      } else if (callSlipErrorCode(caught) === "call_slip_conflict") {
        intent.current = null;
        setConfirmOpen(false);
        await onRefresh();
        setError(callSlipErrorMessage(caught, "The Call Slip conflicts with current Referral or linked Call Slip state. Review the refreshed records before another attempt."));
      } else if (uncertainCallSlipMutation(caught)) {
        setError("The Call Slip issuance result could not be confirmed. Retry the same unchanged details to safely check the result.");
      } else {
        setError(callSlipErrorMessage(caught, "The linked Call Slip could not be issued."));
      }
    }
  }

  return (
    <>
      <form className="max-w-3xl space-y-8" onSubmit={prepare} aria-busy={create.isPending}>
        <section aria-labelledby="linked-call-slip-source-heading" className="border-b border-border pb-7">
          <h2 id="linked-call-slip-source-heading" className="font-heading text-xl font-semibold text-ink">Referral source</h2>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <div><dt className="text-xs font-semibold text-muted">Referral</dt><dd className="mt-1 font-mono text-sm font-semibold text-ink">{referral.reference_code}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Student</dt><dd className="mt-1 text-sm text-ink">{referral.student_name_snapshot}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Source Course / Year / Block</dt><dd className="mt-1 text-sm text-ink">{referral.course_year_block_snapshot}</dd></div>
          </dl>
        </section>

        <section aria-labelledby="linked-call-slip-details-heading" className="border-b border-border pb-7">
          <h2 id="linked-call-slip-details-heading" className="font-heading text-xl font-semibold text-ink">Call Slip details</h2>
          <p className="mt-2 text-sm leading-6 text-muted">Student and Referral are fixed. Course / Year is prefilled from the Referral snapshot but remains editable to reflect the Call Slip source.</p>
          <div className="mt-5"><CallSlipFormFields draft={draft} onChange={setDraft} /></div>
        </section>

        <section aria-labelledby="linked-call-slip-action-heading" className="border-b border-border pb-7">
          <h2 id="linked-call-slip-action-heading" className="font-heading text-xl font-semibold text-ink">Referral source action</h2>
          {action ? (
            <div className="mt-3 border-l-2 border-border pl-4 text-sm text-muted">
              <p>The source action is already recorded and will not be duplicated.</p>
              <p className="mt-2"><span className="font-semibold text-ink">Occurred:</span> {formatDateTime(action.occurred_at)}</p>
              {action.remarks ? <p className="mt-1 whitespace-pre-wrap"><span className="font-semibold text-ink">Remarks:</span> {action.remarks}</p> : null}
            </div>
          ) : (
            <>
              <p className="mt-2 text-sm leading-6 text-muted">Issuing records this action on the Referral and creates the linked Call Slip in the same step.</p>
              <div className="mt-4 grid gap-5 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="linked-action-occurred">Action occurred</Label>
                  <Input id="linked-action-occurred" type="datetime-local" step="60" required max={`${localDateInputValue()}T23:59`} value={occurredAt} onChange={(event) => setOccurredAt(event.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="linked-action-remarks">Remarks (optional)</Label>
                  <Textarea id="linked-action-remarks" rows={3} maxLength={4_000} value={remarks} onChange={(event) => setRemarks(event.target.value)} />
                  <p className="text-xs text-muted">{remarks.length} / 4,000 characters</p>
                </div>
              </div>
            </>
          )}
        </section>

        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={create.isPending}>{create.isPending ? "Issuing…" : "Review linked issuance"}</Button>
          <Link href={`/portal/referrals/${referral.id}`} className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Cancel</Link>
        </div>
      </form>

      <AlertDialog open={confirmOpen} onOpenChange={(open) => { if (!create.isPending) setConfirmOpen(open); }}>
        <AlertDialogContent onEscapeKeyDown={(event) => { if (create.isPending) event.preventDefault(); }}>
          <AlertDialogTitle>Confirm linked Call Slip issuance</AlertDialogTitle>
          <AlertDialogDescription>This issues the Call Slip and, when needed, records the action on the Referral in the same step. Review the details before issuing.</AlertDialogDescription>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-xs font-semibold text-muted">Referral</dt><dd className="mt-1 text-ink">{referral.reference_code}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Student</dt><dd className="mt-1 text-ink">{referral.student_name_snapshot}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Course / Year</dt><dd className="mt-1 text-ink">{draft.courseYear}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Destination</dt><dd className="mt-1 text-ink">{callSlipDestinationLabel(draft.destinationType, draft.otherDestination)}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Report date and time</dt><dd className="mt-1 text-ink">{draft.reportAt}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Issuance mode</dt><dd className="mt-1 text-ink">{draft.notifyStudent ? "Live issuance" : "Historical / back-entry"}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs font-semibold text-muted">Referral action</dt><dd className="mt-1 text-ink">{action ? "Reuse existing action; no new timestamp" : `Record at ${occurredAt}`}</dd></div>
          </dl>
          {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild><Button variant="secondary" disabled={create.isPending}>Review details</Button></AlertDialogCancel>
            <Button disabled={create.isPending} onClick={() => void issueConfirmed()}>{create.isPending ? "Issuing…" : "Confirm and issue"}</Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => { setNotice("Verification complete. Review and confirm the linked issuance again."); setConfirmOpen(true); }} />
    </>
  );
}

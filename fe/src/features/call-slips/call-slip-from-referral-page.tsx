"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelFooter, PanelHeader, PanelSection } from "@/components/ui/panel";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { CallSlipFormFields, type CallSlipDraft, toCallSlipRequestFields } from "@/features/call-slips/call-slip-form-fields";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { CallSlipAccessUnavailable, CallSlipHeading, CallSlipQueryError, LinkedCallSlipCheckLoading, callSlipDestinationLabel, callSlipErrorCode, callSlipErrorMessage, callSlipStateLabel, uncertainCallSlipMutation } from "@/features/call-slips/call-slips-shared";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { ReferralAccessUnavailable, ReferralQueryError } from "@/features/referrals/referrals-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { callSlipsCreateFromReferral, getCallSlipsListQueryKey, useCallSlipsList } from "@/lib/api/generated/call-slips/call-slips";
import { getReferralsGetQueryKey, useReferralsGet } from "@/lib/api/generated/referrals/referrals";
import { CallSlipLifecycleStateValue, ReferralActionTypeValue } from "@/lib/api/generated/model";
import type { CallSlipCreateFromReferralRequest, CallSlipOperationalResponse, ReferralDetailResponse } from "@/lib/api/generated/model";
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateInputValue,
  institutionalDateTimeInputToISO,
  isFutureInstitutionalDateTimeInput,
} from "@/lib/institutional-time";

type LinkedCreateIntent = { fingerprint: string; key: string; payload: CallSlipCreateFromReferralRequest };

function fieldsFromDraft(draft: CallSlipDraft): string | null {
  return institutionalDateTimeInputToISO(draft.reportAt);
}

export function CallSlipFromReferralPage({ referralId }: { referralId: string }) {
  const { user } = usePortalSession();
  const referralAccess = getReferralAccess(user);
  const callSlipAccess = getCallSlipAccess(user);
  const canUse = referralAccess.canView && callSlipAccess.canManageOperational;
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
  if (!callSlipAccess.canManageOperational) return <CallSlipAccessUnavailable title="Linked Call Slip issuance unavailable" message="Call Slip management access is required." />;
  if (referral.isError) return <ReferralQueryError error={referral.error} fallback="The source Referral could not be loaded." onRetry={() => void referral.refetch()} />;
  if (referral.isPending || current.isPending || history.isPending) {
    return <LinkedCallSlipCheckLoading />;
  }
  if (current.isError) return <CallSlipQueryError error={current.error} fallback="Current linked Call Slip state could not be checked. Issuance is unavailable until it can be refreshed." onRetry={() => void current.refetch()} />;
  if (history.isError) return <CallSlipQueryError error={history.error} fallback="Linked Call Slip history could not be loaded." onRetry={() => void history.refetch()} />;

  const item = referral.data.data;
  const currentSlip = current.data.data.items[0];
  if (currentSlip) {
    return (
      <div className="space-y-5">
        <CallSlipHeading title={`Issue linked Call Slip · ${item.reference_code}`} description="This Referral already has a non-voided linked Call Slip." backHref={`/portal/referrals/${item.id}`} backLabel="Back to Referral" />
        <Notice
          className="max-w-3xl"
          title={`${callSlipStateLabel(currentSlip.state)} linked permit`}
          action={<Link href={`/portal/call-slips/${currentSlip.id}`} className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Open linked Call Slip</Link>}
        >
          {formatInstitutionalDateTime(currentSlip.report_at)} · {callSlipDestinationLabel(currentSlip.destination_type, currentSlip.other_destination)}
        </Notice>
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
    <div className="space-y-5">
      <CallSlipHeading title={`Issue linked Call Slip · ${item.reference_code}`} backHref={`/portal/referrals/${item.id}`} backLabel="Back to Referral" />
      <LinkedCallSlipHistory items={history.data.data.items} />
      <LinkedCallSlipCreateForm referral={item} onRefresh={refreshContext} />
    </div>
  );
}

function LinkedCallSlipHistory({
  items,
}: {
  items: Pick<CallSlipOperationalResponse, "id" | "state" | "report_at" | "destination_type" | "other_destination">[];
}) {
  if (items.length === 0) return null;
  return (
    <Panel aria-labelledby="previous-call-slips-heading" className="max-w-3xl">
      <PanelHeader title="Previous linked Call Slips" titleId="previous-call-slips-heading" />
      <ul className="divide-y divide-border">
        {items.map((slip) => (
          <li key={slip.id} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <span className="text-sm text-ink">{callSlipStateLabel(slip.state)} · {formatInstitutionalDateTime(slip.report_at)} · {callSlipDestinationLabel(slip.destination_type, slip.other_destination)}</span>
            <Link href={`/portal/call-slips/${slip.id}`} className="min-h-9 self-start text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:self-auto">Open Call Slip</Link>
          </li>
        ))}
      </ul>
      {items.some((slip) => slip.state === CallSlipLifecycleStateValue.VOIDED) ? <p className="border-t border-border px-4 py-3 text-sm text-muted sm:px-5">A new linked Call Slip can be issued. The existing Referral source action remains recorded and will not be duplicated.</p> : null}
    </Panel>
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
    const reportAt = fields.report_at;
    if (!action) {
      if (!occurredAt) return setError("Action occurred date and time is required for the first linked issuance.");
      if (!institutionalDateTimeInputToISO(occurredAt)) return setError("Enter a valid action occurred date and time.");
      if (isFutureInstitutionalDateTimeInput(occurredAt)) return setError("Action occurred date and time cannot be in the future.");
      const occurredAtIso = institutionalDateTimeInputToISO(occurredAt)!;
      const occurredInstant = new Date(occurredAtIso).getTime();
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
      action: action ? null : { occurred_at: institutionalDateTimeInputToISO(occurredAt)!, remarks: remarks.trim() },
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
      <form className="max-w-3xl" onSubmit={prepare} aria-busy={create.isPending}>
        <Panel as="div">
        <PanelSection title="Referral source" titleId="linked-call-slip-source-heading">
          <dl className="grid gap-4 sm:grid-cols-2">
            <div><dt className="text-xs font-semibold text-muted">Referral</dt><dd className="mt-1 font-mono text-sm font-semibold text-ink">{referral.reference_code}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Student</dt><dd className="mt-1 text-sm text-ink">{referral.student_name_snapshot}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Source Course / Year / Block</dt><dd className="mt-1 text-sm text-ink">{referral.course_year_block_snapshot}</dd></div>
          </dl>
        </PanelSection>

        <PanelSection
          title="Call Slip details"
          titleId="linked-call-slip-details-heading"
          description="Student and Referral are fixed. Course / Year is prefilled from the referral and can be changed to match the Call Slip."
        >
          <CallSlipFormFields draft={draft} onChange={setDraft} />
        </PanelSection>

        <PanelSection title="Referral source action" titleId="linked-call-slip-action-heading">
          {action ? (
            <div className="rounded-sm bg-surface-subtle px-4 py-3.5 text-sm text-muted">
              <p>The source action is already recorded and will not be duplicated.</p>
              <p className="mt-2"><span className="font-semibold text-ink">Occurred:</span> {formatInstitutionalDateTime(action.occurred_at)}</p>
              {action.remarks ? <p className="mt-1 whitespace-pre-wrap"><span className="font-semibold text-ink">Remarks:</span> {action.remarks}</p> : null}
            </div>
          ) : (
            <>
              <p className="text-sm leading-6 text-muted">Issuing records this action on the Referral and creates the linked Call Slip in the same step.</p>
              <div className="mt-4 grid gap-5 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="linked-action-occurred">Action occurred</Label>
                  <Input id="linked-action-occurred" type="datetime-local" step="60" required max={`${institutionalDateInputValue()}T23:59`} value={occurredAt} aria-describedby="linked-action-occurred-timezone" onChange={(event) => setOccurredAt(event.target.value)} />
                  <p id="linked-action-occurred-timezone" className="text-xs leading-5 text-muted">Times use {INSTITUTION_TIME_ZONE_LABEL}.</p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="linked-action-remarks">Remarks (optional)</Label>
                  <Textarea id="linked-action-remarks" rows={3} maxLength={4_000} value={remarks} onChange={(event) => setRemarks(event.target.value)} />
                  <p className="text-xs text-muted">{remarks.length} / 4,000 characters</p>
                </div>
              </div>
            </>
          )}
        </PanelSection>

        <PanelFooter>
          {error && !confirmOpen ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : null}
          {notice ? <p role="status" className="w-full text-sm text-muted">{notice}</p> : null}
          <Button type="submit" disabled={create.isPending}>{create.isPending ? "Issuing…" : "Review linked issuance"}</Button>
          <Link href={`/portal/referrals/${referral.id}`} className={buttonVariants({ variant: "secondary" })}>Cancel</Link>
        </PanelFooter>
        </Panel>
      </form>

      <ConsequentialActionDialog
        open={confirmOpen}
        title="Issue linked Call Slip?"
        confirmLabel="Issue Call Slip"
        cancelLabel="Review details"
        pendingLabel="Issuing…"
        pending={create.isPending}
        error={error}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void issueConfirmed()}
      >
        <p>
          This issues the Call Slip and, when needed, records the action on the
          Referral in the same step. Review the details before issuing.
        </p>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-xs font-semibold text-muted">Referral</dt><dd className="mt-1 text-ink">{referral.reference_code}</dd></div>
          <div><dt className="text-xs font-semibold text-muted">Student</dt><dd className="mt-1 text-ink">{referral.student_name_snapshot}</dd></div>
          <div><dt className="text-xs font-semibold text-muted">Course / Year</dt><dd className="mt-1 text-ink">{draft.courseYear}</dd></div>
          <div><dt className="text-xs font-semibold text-muted">Destination</dt><dd className="mt-1 text-ink">{callSlipDestinationLabel(draft.destinationType, draft.otherDestination)}</dd></div>
          <div><dt className="text-xs font-semibold text-muted">Report date and time</dt><dd className="mt-1 text-ink">{formatInstitutionalDateTime(fieldsFromDraft(draft))} {INSTITUTION_TIME_ZONE_LABEL}</dd></div>
          <div><dt className="text-xs font-semibold text-muted">Issuance mode</dt><dd className="mt-1 text-ink">{draft.notifyStudent ? "Live issuance" : "Historical / back-entry"}</dd></div>
          <div className="sm:col-span-2"><dt className="text-xs font-semibold text-muted">Referral action</dt><dd className="mt-1 text-ink">{action ? "Reuse existing action; no new timestamp" : `Record at ${formatInstitutionalDateTime(institutionalDateTimeInputToISO(occurredAt))} ${INSTITUTION_TIME_ZONE_LABEL}`}</dd></div>
        </dl>
      </ConsequentialActionDialog>
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => { setNotice("Verification complete. Review and confirm the linked issuance again."); setConfirmOpen(true); }} />
    </>
  );
}

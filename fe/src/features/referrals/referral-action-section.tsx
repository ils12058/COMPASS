"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { StepUpDialog } from "@/features/account/security/security-shared";
import {
  referralErrorCode,
  referralErrorMessage,
  uncertainReferralMutation,
} from "@/features/referrals/referrals-shared";
import { getReferralsGetQueryKey, referralsRecordAction } from "@/lib/api/generated/referrals/referrals";
import {
  ReferralActionTypeValue,
  type ReferralActionResponse,
  type ReferralDetailResponse,
} from "@/lib/api/generated/model";
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateInputValue,
  institutionalDateTimeInputToISO,
  isFutureInstitutionalDateTimeInput,
} from "@/lib/institutional-time";

const actionRows: { type: ReferralActionTypeValue; label: string }[] = [
  { type: ReferralActionTypeValue.CALL_PARENT_GUARDIAN, label: "Call Parent/Guardian" },
  { type: ReferralActionTypeValue.SEND_PARENT_NOTIFICATION_LETTER, label: "Send Parent Notification Letter" },
  { type: ReferralActionTypeValue.SEND_CALL_SLIP_INTERVIEW_PERMIT, label: "Send Call Slip/Interview Permit" },
];

export function ReferralActionsSection({
  referral,
  canManage,
  isVoided,
  canManageCallSlips,
  onRefresh,
}: {
  referral: ReferralDetailResponse;
  canManage: boolean;
  isVoided: boolean;
  canManageCallSlips: boolean;
  onRefresh: () => Promise<ReferralDetailResponse | undefined>;
}) {
  return (
    <section aria-labelledby="referral-actions-heading" className="border-t border-border py-6">
      <h2 id="referral-actions-heading" className="font-heading text-xl font-semibold text-ink">Actions taken</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">These rows record source Referral history. Recording a row does not place a call, send a letter, or send a notification.</p>
      <ol className="mt-4 divide-y divide-border border-y border-border">
        {actionRows.map((row) => {
          const action = referral.actions.find((item) => item.action_type === row.type);
          const callSlipIssuanceHandledBelow =
            row.type === ReferralActionTypeValue.SEND_CALL_SLIP_INTERVIEW_PERMIT && canManageCallSlips;
          return (
            <li key={row.type} className="py-4">
              <h3 className="font-semibold text-ink">{row.label}</h3>
              {action ? (
                <RecordedAction action={action} />
              ) : isVoided ? (
                <p className="mt-2 text-sm text-muted">Not recorded. A voided Referral cannot receive new actions.</p>
              ) : canManage && callSlipIssuanceHandledBelow ? (
                <p className="mt-2 text-sm text-muted">Not recorded. See the Call Slip / Interview Permit section below for linked issuance or the historical action-only option.</p>
              ) : canManage ? (
                <ReferralActionEntry
                  referral={referral}
                  actionType={row.type}
                  buttonLabel={row.type === ReferralActionTypeValue.CALL_PARENT_GUARDIAN ? "Record Parent / Guardian call" : row.type === ReferralActionTypeValue.SEND_PARENT_NOTIFICATION_LETTER ? "Record Parent Notification Letter action" : "Record Call Slip / Interview Permit action"}
                  onRefresh={onRefresh}
                />
              ) : (
                <p className="mt-2 text-sm text-muted">Not recorded.</p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function RecordedAction({ action }: { action: ReferralActionResponse }) {
  return (
    <div className="mt-2 space-y-1 text-sm text-muted">
      <p><span className="font-semibold text-ink">Occurred:</span> {formatInstitutionalDateTime(action.occurred_at)}</p>
      {action.remarks ? <p className="whitespace-pre-wrap break-words"><span className="font-semibold text-ink">Remarks:</span> {action.remarks}</p> : null}
      {action.recorded_by ? <p><span className="font-semibold text-ink">Recorded by:</span> {action.recorded_by.display_name}</p> : null}
    </div>
  );
}

export function ReferralActionEntry({
  referral,
  actionType,
  buttonLabel,
  supportingText,
  onRefresh,
}: {
  referral: ReferralDetailResponse;
  actionType: ReferralActionTypeValue;
  buttonLabel: string;
  supportingText?: string;
  onRefresh: () => Promise<ReferralDetailResponse | undefined>;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [occurredAt, setOccurredAt] = useState("");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [reconcileRequired, setReconcileRequired] = useState(false);
  const [review, setReview] = useState<{
    action_type: ReferralActionTypeValue;
    occurred_at: string;
    remarks: string;
  } | null>(null);
  const [resumeReview, setResumeReview] = useState<typeof review>(null);
  // Covers the whole confirmation, including the refresh after the request succeeds.
  const [recording, setRecording] = useState(false);
  const record = useMutation({
    mutationFn: (payload: NonNullable<typeof review>) =>
      referralsRecordAction(referral.id, payload),
    retry: false,
  });
  const recordPending = record.isPending || recording;

  async function reconcile(): Promise<"recorded" | "missing" | "unavailable"> {
    const current = await onRefresh();
    setReconcileRequired(false);
    if (!current) {
      setReconcileRequired(true);
      setError("The Referral could not be refreshed. Do not retry this source action until the Referral detail can be checked.");
      return "unavailable";
    }
    const recorded = current.actions.some((item) => item.action_type === actionType);
    if (recorded) {
      setReview(null);
      setResumeReview(null);
      setOpen(false);
      setNotice("This source action is already recorded on the Referral.");
      return "recorded";
    }
    return "missing";
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    if (reconcileRequired) {
      await reconcile();
      return;
    }
    if (!occurredAt) return setError("Action occurred date and time is required.");
    const occurredAtIso = institutionalDateTimeInputToISO(occurredAt);
    if (!occurredAtIso) return setError("Enter a valid action occurred date and time.");
    if (isFutureInstitutionalDateTimeInput(occurredAt)) return setError("Action occurred date and time cannot be in the future.");
    if (referral.received_at) {
      if (new Date(occurredAtIso).getTime() < new Date(referral.received_at).getTime()) {
        return setError("Action occurred date and time cannot be earlier than Guidance receipt.");
      }
    } else if (occurredAt.slice(0, 10) < referral.referred_on) {
      return setError("Action date cannot be earlier than Date referred.");
    }

    setReview({
      action_type: actionType,
      occurred_at: occurredAtIso,
      remarks: remarks.trim(),
    });
  }

  async function confirmRecord() {
    if (!review || reconcileRequired) return;
    const reviewed = review;
    setError(null);
    setNotice(null);
    setRecording(true);
    try {
      await record.mutateAsync(reviewed);
      await queryClient.invalidateQueries({ queryKey: getReferralsGetQueryKey(referral.id) });
      setReview(null);
      setResumeReview(null);
      setOpen(false);
      setNotice("Referral source action recorded.");
      setOccurredAt("");
      setRemarks("");
    } catch (caught) {
      if (referralErrorCode(caught) === "recent_mfa_required") {
        setReview(null);
        setResumeReview(reviewed);
        setNotice("Verify your authenticator, then review and confirm the source action again.");
        setStepUpOpen(true);
      } else if (referralErrorCode(caught) === "referral_conflict") {
        const result = await reconcile();
        if (result === "missing") {
          setError(referralErrorMessage(caught, "The Referral action conflicts with current source history."));
        }
      } else if (uncertainReferralMutation(caught)) {
        setReconcileRequired(true);
        const result = await reconcile();
        if (result === "missing") {
          setError("The action was not found after refreshing the Referral. Review the source details and submit again only if the action is still unrecorded.");
        }
      } else {
        setError(referralErrorMessage(caught, "The Referral source action could not be recorded."));
      }
    } finally {
      setRecording(false);
    }
  }

  const actionLabel =
    actionRows.find((row) => row.type === actionType)?.label ?? "Referral source action";

  return (
    <div className="mt-3">
      {supportingText ? <p className="mb-3 max-w-2xl text-sm leading-6 text-muted">{supportingText}</p> : null}
      {!open ? (
        <Button variant="secondary" onClick={() => { setOpen(true); setError(null); setNotice(null); }}>
          {buttonLabel}
        </Button>
      ) : (
        <form className="max-w-xl space-y-4 border-l-2 border-border pl-4" onSubmit={submit} aria-busy={recordPending}>
          <div className="grid gap-2">
            <Label htmlFor={`action-occurred-${actionType}`}>Action occurred</Label>
            <Input
              id={`action-occurred-${actionType}`}
              type="datetime-local"
              step="60"
              required
              max={institutionalDateInputValue() + "T23:59"}
              value={occurredAt}
              disabled={recordPending || reconcileRequired}
              aria-describedby={`action-occurred-timezone-${actionType}`}
              onChange={(event) => setOccurredAt(event.target.value)}
            />
            <p
              id={`action-occurred-timezone-${actionType}`}
              className="text-xs leading-5 text-muted"
            >
              Times use {INSTITUTION_TIME_ZONE_LABEL}.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor={`action-remarks-${actionType}`}>Remarks (optional)</Label>
            <Textarea id={`action-remarks-${actionType}`} rows={3} maxLength={4_000} value={remarks} disabled={recordPending || reconcileRequired} onChange={(event) => setRemarks(event.target.value)} />
            <p className="text-xs text-muted">{remarks.length} / 4,000 characters</p>
          </div>
          {error && !review ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
          <div className="flex flex-wrap gap-2">
            {reconcileRequired ? (
              <Button type="button" variant="secondary" onClick={() => void reconcile()}>
                Refresh Referral detail
              </Button>
            ) : (
              <Button type="submit" disabled={recordPending}>
                Review action
              </Button>
            )}
            <Button type="button" variant="secondary" disabled={recordPending} onClick={() => { setOpen(false); setError(null); }}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      {notice ? <p role="status" className="mt-3 text-sm text-muted">{notice}</p> : null}
      <ConsequentialActionDialog
        open={review !== null}
        title={review ? `${buttonLabel}?` : "Review source action"}
        confirmLabel={buttonLabel}
        pendingLabel="Recording…"
        pending={recordPending}
        confirmDisabled={reconcileRequired}
        error={error}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setReview(null);
        }}
        onConfirm={() => void confirmRecord()}
      >
        {review ? (
          <>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted">Action</dt>
                <dd className="font-semibold text-ink">{actionLabel}</dd>
              </div>
              <div>
                <dt className="text-muted">Occurred</dt>
                <dd className="font-semibold text-ink">
                  {formatInstitutionalDateTime(review.occurred_at)} {INSTITUTION_TIME_ZONE_LABEL}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-muted">Remarks</dt>
                <dd className="whitespace-pre-wrap break-words font-semibold text-ink">
                  {review.remarks || "None"}
                </dd>
              </div>
            </dl>
            <p className="font-semibold text-ink">
              This source action cannot be edited or deleted after it is recorded.
            </p>
            {reconcileRequired ? (
              <p>Refresh the Referral detail before deliberately retrying this source action.</p>
            ) : null}
          </>
        ) : null}
      </ConsequentialActionDialog>
      <StepUpDialog
        open={stepUpOpen}
        onOpenChange={setStepUpOpen}
        onVerified={() => {
          const reviewed = resumeReview;
          setResumeReview(null);
          setNotice("Verification complete. Review and confirm the source action again to continue.");
          if (reviewed) setReview(reviewed);
        }}
      />
    </div>
  );
}

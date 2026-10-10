"use client";

import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { CallSlipQueryError, callSlipStateLabel } from "@/features/call-slips/call-slips-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { ReferralActionEntry } from "@/features/referrals/referral-action-section";
import { CallSlipLifecycleStateValue, ReferralActionTypeValue, type CallSlipOperationalResponse, type ReferralDetailResponse } from "@/lib/api/generated/model";
import { useCallSlipsList } from "@/lib/api/generated/call-slips/call-slips";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

export function ReferralCallSlipSection({
  referral,
  canManageReferral,
  canViewCallSlips,
  canManageCallSlips,
  currentItems,
  currentPending,
  currentError,
  retryCurrent,
  onRefresh,
}: {
  referral: ReferralDetailResponse;
  canManageReferral: boolean;
  canViewCallSlips: boolean;
  canManageCallSlips: boolean;
  currentItems: CallSlipOperationalResponse[];
  currentPending: boolean;
  currentError: unknown;
  retryCurrent: () => void;
  onRefresh: () => Promise<ReferralDetailResponse | undefined>;
}) {
  const [historyPage, setHistoryPage] = useState(1);
  const referralAction = referral.actions.find(
    (action) => action.action_type === ReferralActionTypeValue.SEND_CALL_SLIP_INTERVIEW_PERMIT,
  );
  const isVoided = Boolean(referral.voided_at);
  const history = useCallSlipsList(
    { referral_id: referral.id, include_voided: true, page: historyPage, page_size: 20 },
    { query: { enabled: canViewCallSlips, retry: false } },
  );

  return (
    <Panel aria-labelledby="referral-call-slips-heading">
      <PanelHeader title="Call Slip / Interview Permit" titleId="referral-call-slips-heading" />
      <div className="px-4 py-4 *:first:mt-0 sm:px-5">
      {!canViewCallSlips ? (
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">Linked Call Slip details are unavailable here. Open the Call Slip to check its issuance status if you have access.</p>
      ) : currentError ? (
        <div className="mt-4">
          <CallSlipQueryError error={currentError} fallback="Linked Call Slip state could not be checked." onRetry={() => { retryCurrent(); void history.refetch(); }} />
        </div>
      ) : currentPending ? (
        <div className="mt-4 space-y-2" aria-busy="true" aria-label="Checking linked Call Slips">
          <Skeleton className="h-12 w-full" />
        </div>
      ) : (
        <>
          {currentItems[0] ? (
            <LinkedCallSlipSummary callSlip={currentItems[0]} />
          ) : (
            <p className="mt-3 text-sm text-muted">No current linked Call Slip.</p>
          )}

          {history.isError ? (
            <div className="mt-4">
              <CallSlipQueryError error={history.error} fallback="Linked Call Slip history could not be loaded." onRetry={() => void history.refetch()} />
            </div>
          ) : history.isPending ? (
            <p role="status" className="mt-4 text-sm text-muted">Loading linked Call Slip history…</p>
          ) : (
            <LinkedCallSlipHistory
              items={history.data?.data.items ?? []}
              currentId={currentItems[0]?.id}
              page={history.data?.data.page ?? historyPage}
              hasNext={history.data?.data.has_next ?? false}
              onPageChange={setHistoryPage}
            />
          )}

          {!isVoided && !currentItems[0] && canManageCallSlips ? (
            <div className="mt-5 border-t border-border pt-4">
              <p className="text-sm leading-6 text-muted">
                {referralAction
                  ? "The Call Slip action is already recorded."
                  : "Issuing also records the Call Slip action on this Referral."}
              </p>
              <Link href={`/portal/referrals/${referral.id}/issue-call-slip`} className={buttonVariants({ variant: "primary", className: "mt-3" })}>
                {history.data?.data.items.some((item) => item.state === CallSlipLifecycleStateValue.VOIDED)
                  ? "Issue another linked Call Slip"
                  : referralAction
                    ? "Issue linked Call Slip"
                    : "Issue Call Slip / Interview Permit"}
              </Link>
              {!referralAction && canManageReferral ? (
                <ReferralActionEntry
                  referral={referral}
                  actionType={ReferralActionTypeValue.SEND_CALL_SLIP_INTERVIEW_PERMIT}
                  buttonLabel="Record action only"
                  supportingText={'Records the action without issuing a digital Call Slip or notifying the student.'}
                  onRefresh={onRefresh}
                />
              ) : null}
            </div>
          ) : null}
          {isVoided ? <p className="mt-4 text-sm text-muted">A voided Referral cannot receive a new linked Call Slip.</p> : null}
        </>
      )}
      </div>
    </Panel>
  );
}

function LinkedCallSlipSummary({
  callSlip,
}: {
  callSlip: CallSlipOperationalResponse;
}) {
  return (
    <div className="mt-4 rounded-sm border border-border bg-surface-subtle px-4 py-3">
      <p className="font-semibold text-ink">{callSlipStateLabel(callSlip.state)}</p>
      <p className="mt-1 text-sm text-muted">{callSlip.student_name_snapshot} · {callSlip.course_year_snapshot}</p>
      <p className="mt-1 text-sm text-muted">Report {formatInstitutionalDateTime(callSlip.report_at)} · {callSlip.destination_type === "GUIDANCE_OFFICE" ? "Guidance Office" : callSlip.other_destination}</p>
      <Link href={`/portal/call-slips/${callSlip.id}`} className="mt-2 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
        Open Call Slip
      </Link>
    </div>
  );
}

function LinkedCallSlipHistory({
  items,
  currentId,
  page,
  hasNext,
  onPageChange,
}: {
  items: CallSlipOperationalResponse[];
  currentId?: string;
  page: number;
  hasNext: boolean;
  onPageChange: (page: number) => void;
}) {
  const historical = items.filter((item) => item.id !== currentId);
  if (historical.length === 0 && page === 1 && !hasNext) return null;

  return (
    <div className="mt-5">
      <h3 className="text-sm font-semibold text-ink">Linked Call Slip history</h3>
      {historical.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No earlier linked Call Slips on this page.</p>
      ) : (
        <ul className="mt-2 divide-y divide-border rounded-sm border border-border">
          {historical.map((item) => (
            <li key={item.id} className="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-medium text-ink">{callSlipStateLabel(item.state)}</p>
                <p className="mt-1 text-sm text-muted">{formatInstitutionalDateTime(item.report_at)} · {item.destination_type === "GUIDANCE_OFFICE" ? "Guidance Office" : item.other_destination}</p>
              </div>
              <Link href={`/portal/call-slips/${item.id}`} className="min-h-9 self-start text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:self-auto">Open Call Slip</Link>
            </li>
          ))}
        </ul>
      )}
      <CanonicalPagination page={page} hasNext={hasNext} onPageChange={onPageChange} label="Linked Call Slip history pages" />
    </div>
  );
}

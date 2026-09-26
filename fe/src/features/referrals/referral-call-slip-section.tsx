"use client";

import Link from "next/link";
import { useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CallSlipQueryError, callSlipStateLabel } from "@/features/call-slips/call-slips-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { ReferralActionEntry } from "@/features/referrals/referral-action-section";
import { CallSlipLifecycleStateValue, ReferralActionTypeValue, type CallSlipOperationalResponse, type ReferralDetailResponse } from "@/lib/api/generated/model";
import { useCallSlipsList } from "@/lib/api/generated/call-slips/call-slips";
import { formatDateTime } from "@/lib/date-time";

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
    <section aria-labelledby="referral-call-slips-heading" className="border-t border-border py-6">
      <h2 id="referral-call-slips-heading" className="font-heading text-xl font-semibold text-ink">Call Slip / Interview Permit</h2>
      {!canViewCallSlips ? (
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">Linked Call Slip details are not available in your current access, so the existing issuance state cannot be verified here.</p>
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
            <p className="mt-3 text-sm text-muted">No non-voided linked Call Slip is currently recorded.</p>
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
            <div className="mt-5 border-t border-border pt-5">
              <p className="text-sm leading-6 text-muted">
                {referralAction
                  ? "The Referral source action is already recorded. Issuing a linked Call Slip will reuse it without adding another action timestamp."
                  : "Issuing a linked Call Slip will also record the source Referral action in the same transaction."}
              </p>
              <Link href={`/portal/referrals/${referral.id}/issue-call-slip`} className="mt-3 inline-flex min-h-10 items-center justify-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
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
                  supportingText={'Records the Referral source action without creating or notifying a digital Call Slip.'}
                  onRefresh={onRefresh}
                />
              ) : null}
            </div>
          ) : null}
          {isVoided ? <p className="mt-4 text-sm text-muted">A voided Referral cannot receive a new linked Call Slip.</p> : null}
        </>
      )}
    </section>
  );
}

function LinkedCallSlipSummary({
  callSlip,
}: {
  callSlip: CallSlipOperationalResponse;
}) {
  return (
    <div className="mt-4 border-l-2 border-brand pl-4">
      <p className="font-semibold text-ink">{callSlipStateLabel(callSlip.state)}</p>
      <p className="mt-1 text-sm text-muted">{callSlip.student_name_snapshot} · {callSlip.course_year_snapshot}</p>
      <p className="mt-1 text-sm text-muted">Report {formatDateTime(callSlip.report_at)} · {callSlip.destination_type === "GUIDANCE_OFFICE" ? "Guidance Office" : callSlip.other_destination}</p>
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
        <ul className="mt-2 divide-y divide-border border-y border-border">
          {historical.map((item) => (
            <li key={item.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-medium text-ink">{callSlipStateLabel(item.state)}</p>
                <p className="mt-1 text-sm text-muted">{formatDateTime(item.report_at)} · {item.destination_type === "GUIDANCE_OFFICE" ? "Guidance Office" : item.other_destination}</p>
              </div>
              <Link href={`/portal/call-slips/${item.id}`} className="min-h-9 self-start text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:self-auto">Open Call Slip</Link>
            </li>
          ))}
        </ul>
      )}
      {(page > 1 || hasNext) ? (
        <CanonicalPagination page={page} hasNext={hasNext} onPageChange={onPageChange} label="Linked Call Slip history pages" />
      ) : null}
    </div>
  );
}

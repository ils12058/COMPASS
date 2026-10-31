"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { useServerBoundary } from "@/features/freshness/use-server-boundary";
import { administrativeStateLabel } from "@/features/faculty-referrals/presentation";
import { CompassApiError } from "@/lib/api/errors";
import { getReferralsGetQueryKey, getReferralsListQueryKey, referralsAcknowledge, referralsCloseAdministratively, useReferralsGetAdministration } from "@/lib/api/generated/referrals/referrals";
import type { ReferralDetailResponse } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

export function ReferralAdministration({ referral, canManage, refreshFailed }: { referral: ReferralDetailResponse; canManage: boolean; refreshFailed: boolean }) {
  const client = useQueryClient();
  const query = useReferralsGetAdministration(referral.id, { query: { retry: false, refetchOnWindowFocus: "always", refetchOnReconnect: "always" } });
  const data = safeQueryData(query)?.data;
  const [review, setReview] = useState<{ kind: "ack" | "close"; version: number } | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [pending, setPending] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [expiredAt, setExpiredAt] = useState<number | null>(null);
  useServerBoundary({ boundary: query.data?.data.valid_until, serverDate: query.data?.headers.date, receivedAt: query.dataUpdatedAt, onBoundary: () => { setExpiredAt(query.dataUpdatedAt); void query.refetch(); } });
  const unavailable = refreshFailed || query.isError || query.isFetching || expiredAt === query.dataUpdatedAt || blocked || Boolean(referral.voided_at);
  const actionAllowed = review?.kind === "ack" ? data?.can_acknowledge : data?.can_close;
  const stale = Boolean(review && data && review.version !== data.version);

  async function confirm() {
    if (!review || unavailable || stale || !actionAllowed || (review.kind === "close" && !reviewed)) return;
    setPending(true); setError(null); setNotice(null);
    try {
      if (review.kind === "ack") await referralsAcknowledge(referral.id, { expected_version: review.version });
      else await referralsCloseAdministratively(referral.id, { expected_version: review.version, obligations_reviewed: true });
      setReview(null);
      setNotice(review.kind === "ack" ? "Receipt acknowledged." : "Referral closed administratively.");
    } catch (caught) {
      // No mutation replay. Even a lost response requires a canonical read and a fresh review.
      setBlocked(true);
      setError(caught instanceof CompassApiError && caught.status === 403
        ? "This action is no longer permitted. Close this review and refresh the record."
        : caught instanceof CompassApiError && caught.status === 409
          ? "The record changed or this action was already performed. Close this review and check the latest record."
          : "We could not confirm the result. Close this review and refresh the record before deciding what to do next.");
    } finally {
      await Promise.all([query.refetch(), client.invalidateQueries({ queryKey: getReferralsGetQueryKey(referral.id) }), client.invalidateQueries({ queryKey: getReferralsListQueryKey() })]);
      setPending(false);
    }
  }

  return <Panel aria-labelledby="referral-administration-heading">
    <PanelHeader title="Faculty intake" titleId="referral-administration-heading" />
    <PanelBody className="space-y-4">
      {query.isPending ? <p role="status">Loading intake record…</p> : data ? <>
        <p role="status" className="font-semibold text-ink">{data.state ? administrativeStateLabel(data.state) : "Voided — administrative actions unavailable"}</p>
        <dl className="grid min-w-0 gap-4 text-sm sm:grid-cols-2 [&_dd]:mt-1 [&_dd]:[overflow-wrap:anywhere] [&_dt]:font-semibold [&_dt]:text-muted">
          <div><dt>Submitted by</dt><dd>{data.submitted_by.display_name}</dd></div>
          <div><dt>Submitted · Philippine Time</dt><dd>{formatInstitutionalDateTime(data.submitted_at)}</dd></div>
          <div><dt>Faculty home College at submission</dt><dd>{data.faculty_home_college}</dd></div>
          <div><dt>Student College at submission</dt><dd>{data.student_college_at_submission}</dd></div>
          {data.acknowledged_by && data.received_at ? <div><dt>Receipt acknowledged</dt><dd>{data.acknowledged_by.display_name} · {formatInstitutionalDateTime(data.received_at)}</dd></div> : null}
          {data.closed_by && data.closed_at ? <div><dt>Administratively closed</dt><dd>{data.closed_by.display_name} · {formatInstitutionalDateTime(data.closed_at)}</dd></div> : null}
        </dl>
        {canManage && !referral.voided_at && data.state !== "ADMINISTRATIVELY_CLOSED" ? <div>
          {!unavailable && (data.can_acknowledge || data.can_close) ? <Button className="min-w-0 max-w-full [overflow-wrap:anywhere]" variant="secondary" onClick={() => { setReview({ kind: data.can_acknowledge ? "ack" : "close", version: data.version }); setReviewed(false); setError(null); setNotice(null); }}>{data.can_acknowledge ? "Acknowledge receipt" : "Close administratively"}</Button> : <p className="text-sm text-muted">Administrative action is unavailable. Current policy and record eligibility must be confirmed.</p>}
        </div> : null}
      </> : null}
      {query.isError ? <Notice role="alert">Intake details could not be refreshed. Actions are unavailable.</Notice> : null}
      <Button className="min-w-0 max-w-full [overflow-wrap:anywhere]" variant="quiet" disabled={pending || query.isFetching} onClick={async () => { const result = await query.refetch(); if (result.isSuccess) setBlocked(false); }}>Refresh intake record</Button>
      {notice ? <p role="status" className="text-sm text-success">{notice}</p> : null}
    </PanelBody>
    <ConsequentialActionDialog open={review !== null} title={review?.kind === "close" ? "Close this Referral administratively?" : "Acknowledge receipt of this Referral?"} confirmLabel={review?.kind === "close" ? "Close administratively" : "Acknowledge receipt"} pendingLabel="Recording…" pending={pending} confirmDisabled={unavailable || stale || !actionAllowed || (review?.kind === "close" && !reviewed)} error={error || (stale ? "The record changed. Close this review and check the latest record." : null)} onOpenChange={(open) => { if (!open) setReview(null); }} onConfirm={() => void confirm()} choices={review?.kind === "close" ? <div className="flex min-h-11 items-start gap-3"><input id="referral-obligations-reviewed" type="checkbox" className="mt-1 h-4 w-4 shrink-0 accent-brand" checked={reviewed} disabled={pending} onChange={(event) => setReviewed(event.target.checked)} /><Label className="min-w-0 [overflow-wrap:anywhere]" htmlFor="referral-obligations-reviewed">I reviewed the required obligations</Label></div> : undefined}>
      {review?.kind === "close" ? <p>Review the administrative obligations under the approved closure criteria before closing. This records completion of administrative handling. Linked Call Slips and Follow-Ups keep their own status. Closure does not establish that Counseling or the Student’s concern is resolved.</p> : <p>This records your account and the current server time as the GCO receipt. The original Faculty submission and source content are retained.</p>}
    </ConsequentialActionDialog>
  </Panel>;
}

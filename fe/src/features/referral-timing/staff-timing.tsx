"use client";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { useServerBoundary } from "@/features/freshness/use-server-boundary";
import { useReferralsGetTiming } from "@/lib/api/generated/referrals/referrals";
import { ReportedTiming, VerifiedTiming } from "./timing-readout";
import { timingWindowExpiry } from "./timing-presentation";
import { TimingVerificationForm } from "./verification-form";

export function StaffReferralTiming({ referralId, canManage = false, parentStale = false, embedded = false }: {
  referralId: string; canManage?: boolean; parentStale?: boolean; embedded?: boolean;
}) {
  const query = useReferralsGetTiming(referralId, { query: { retry: false, refetchOnWindowFocus: true } });
  const data = safeQueryData(query)?.data;
  const expiries = [...(data?.reported?.windows ?? []), ...(data?.verifications.flatMap(record => record.windows) ?? [])].filter(window => !window.expired).map(timingWindowExpiry).filter((value): value is string => value !== null).sort();
  useServerBoundary({ boundary: expiries[0] ?? null, onBoundary: () => { void query.refetch(); } });
  async function refresh() {
    const result = await query.refetch();
    return result.isSuccess ? result.data.data : undefined;
  }
  const content = query.isPending ? <LoadingRegion label="Loading Referral timing…"><Skeleton className="h-24 w-full" /></LoadingRegion> : !data ? <Notice role="alert" action={<Button type="button" variant="secondary" onClick={() => void query.refetch()}>Retry timing</Button>}>Referral timing is not available. Check your access or try again.</Notice> : <div className="space-y-4">
    {query.isError ? <RefreshFailureNotice message="Couldn't refresh Referral timing. Showing the last confirmed information; refresh before adding verification." retrying={query.isFetching} onRetry={() => void query.refetch()} /> : null}
    {data.referral_closed ? <p className="text-sm font-semibold text-warning">Referral closed</p> : null}
    <div className="grid gap-5 @3xl:grid-cols-2">
      <ReportedTiming statement={data.reported} headingId={embedded ? "call-slip-reported-timing" : "reported-referral-timing"} />
      <VerifiedTiming records={data.verifications} headingId={embedded ? "call-slip-verified-timing" : "verified-referral-timing"} />
    </div>
    <p className="text-sm text-muted">Timing is guidance only. Choose the Call Slip date and time yourself; these windows do not reserve a slot.</p>
    {canManage && data.can_verify ? <div className="border-t border-border pt-4"><TimingVerificationForm key={data.referral_id} facts={data} unavailable={parentStale || query.isError || query.isFetching} onRefresh={refresh} /></div> : null}
  </div>;
  return embedded ? <div className="min-w-0 @container">{content}</div> : <Panel aria-labelledby="referral-timing-heading" className="@container"><PanelHeader title="When can Guidance reach or meet the student?" titleId="referral-timing-heading" /><PanelBody>{content}</PanelBody></Panel>;
}

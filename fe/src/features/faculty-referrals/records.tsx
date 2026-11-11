"use client";

import { TaskGuideAction } from "@/features/portal/orientation/task-guide-action";

import { useState } from "react";
import { Forward } from "lucide-react";
import { ContextHelp } from "@/components/ui/context-help";
import { Button, buttonVariants } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { PageActionLink } from "@/components/ui/page-action";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage, RecordSummary } from "@/components/ui/panel";
import { pageSheetWidth } from "@/components/ui/page-width";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { useReferralsFacultyGetMine, useReferralsFacultyListMine } from "@/lib/api/generated/referrals/referrals";
import type { FacultyReferralSubmissionResponse } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { useFacultyAvailability } from "./availability";
import { facultySubmitPath, facultyReferralsPath, facultyReferralAccess, facultySubmissionAvailable } from "./access";
import { FacultyLoading, FacultyReferralGate, FacultyUnavailable } from "./shared";
import { administrativeStateLabel, facultyReferralError } from "./presentation";

function SubmittedState({ item }: { item: FacultyReferralSubmissionResponse }) {
  return <span className="inline-block max-w-full rounded-sm [overflow-wrap:anywhere] bg-success/10 px-2 py-1 text-sm font-semibold text-success">{administrativeStateLabel(item.state)}</span>;
}

export function SubmissionFacts({ item }: { item: FacultyReferralSubmissionResponse }) {
  return <RecordSummary label="Referral" title={item.reference_code} status={<SubmittedState item={item} />} facts={[
    { label: "Student", value: item.student.display_name },
    { label: "Submitted · Philippine Time", value: formatInstitutionalDateTime(item.submitted_at) },
    ...(item.received_at ? [{ label: "Received by the Guidance Office · Philippine Time", value: formatInstitutionalDateTime(item.received_at) }] : []),
    ...(item.closed_at ? [{ label: "Administratively closed · Philippine Time", value: formatInstitutionalDateTime(item.closed_at) }] : []),
  ]} />;
}

export function SubmissionRows({ items }: { items: FacultyReferralSubmissionResponse[] }) {
  return <ul className="divide-y divide-border">
    {items.map((item) => <li key={item.id} className="grid min-w-0 gap-x-5 gap-y-1 px-4 py-3 text-sm sm:px-5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <GuardedPortalLink data-guide-target="faculty-row" href={`${facultyReferralsPath}/${item.id}`} className="inline-flex min-h-11 max-w-full items-center font-semibold text-brand underline-offset-4 hover:underline [overflow-wrap:anywhere] focus-visible:ring-2 focus-visible:ring-focus" aria-label={`View Referral ${item.reference_code}`}>{item.reference_code}</GuardedPortalLink>
        <p className="text-ink [overflow-wrap:anywhere]">{item.student.display_name}</p>
      </div>
      <p className="min-w-0 self-center text-muted [overflow-wrap:anywhere]"><span className="sr-only">Submitted </span><time dateTime={item.submitted_at}>{formatInstitutionalDateTime(item.submitted_at)}</time><span className="block text-xs">Philippine Time</span></p>
      <div className="self-center"><SubmittedState item={item} /></div>
    </li>)}
  </ul>;
}

export function FacultySubmissionList({ recent = false }: { recent?: boolean }) {
  const [page, setPage] = useState(1);
  const query = useReferralsFacultyListMine({ page, page_size: recent ? 3 : 20 }, { query: { retry: false, refetchOnWindowFocus: true } });
  const data = safeQueryData(query)?.data;
  return <>
    {query.isPending ? <FacultyLoading /> : <Panel data-guide-target="faculty-list" aria-label={recent ? "Recent Referrals" : "Submitted Referrals"}>
      <PanelHeader title={recent ? "Recent Referrals" : "Submitted Referrals"} context={data ? describeResultPage({ count: data.items.length, page: data.page, hasNext: data.has_next, noun: { one: "referral", other: "referrals" } }) : undefined} actions={recent && data ? <GuardedPortalLink href={facultyReferralsPath} className="inline-flex min-h-11 items-center text-sm font-semibold text-brand underline">View all</GuardedPortalLink> : undefined} />
      {query.isError && !data ? <PanelMessage role="alert" action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>{facultyReferralError(query.error, "read")}</PanelMessage> : null}
      {data && query.isError ? <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
      {data?.items.length ? <SubmissionRows items={data.items} /> : data ? <PanelMessage>{page === 1 ? "You have no submitted Referrals." : "No Referrals on this page. Go back to the previous page."}</PanelMessage> : null}
      {data && !recent ? <CanonicalPagination page={data.page} hasNext={data.has_next} disabled={query.isFetching} onPageChange={setPage} label="My Referrals pages" className="mx-4 sm:mx-5" /> : null}
    </Panel>}
  </>;
}

export function FacultyReferralsPage() {
  return <FacultyReferralGate><FacultyReferralsContent /></FacultyReferralGate>;
}

function FacultyReferralsContent() {
  const { user } = usePortalSession();
  const query = useFacultyAvailability(user);
  const available = query.availability;
  return <section className={pageSheetWidth}>
    <PageHeader title="My Referrals" actions={<><TaskGuideAction />{facultyReferralAccess(user).submit && facultySubmissionAvailable(available) ? <PageActionLink data-guide-target="faculty-entry" href={facultySubmitPath} label="Submit Referral" icon={Forward} /> : null}</>} />
    {query.isPending ? <FacultyLoading label="Checking Referral Availability…" /> : query.isError ? <Notice role="alert" action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>Couldn&apos;t check Referral Availability. Try again.</Notice> : available?.can_view_submissions ? <FacultySubmissionList /> : <FacultyUnavailable onRetry={() => void query.refetch()} />}
  </section>;
}

export function FacultyReferralDetailPage({ referralId }: { referralId: string }) {
  return <FacultyReferralGate><FacultyReferralDetail referralId={referralId} /></FacultyReferralGate>;
}

function FacultyReferralDetail({ referralId }: { referralId: string }) {
  const { user } = usePortalSession();
  const query = useReferralsFacultyGetMine(referralId, { query: { retry: false, refetchOnWindowFocus: true } });
  const item = safeQueryData(query)?.data;
  const messageable = facultyReferralAccess(user).message && item !== undefined;
  return <section className={pageSheetWidth}>
    <PageHeader actions={<TaskGuideAction />} title="Referral details" help={<ContextHelp title="Referral tracking" sections={[{ heading: "Administrative handling", content: <ul className="list-disc space-y-2 pl-5"><li><strong>Submitted:</strong> You submitted this Referral online.</li><li><strong>Received by the Guidance Office:</strong> The Guidance Office recorded receipt.</li><li><strong>Administratively Closed:</strong> Administrative handling is complete. Counseling, other support, or the Student’s concern may still need attention.</li></ul> }]} />} back={<GuardedPortalLink href={facultyReferralsPath} className={pageBackLinkClass}>Back to My Referrals</GuardedPortalLink>} />
    {query.isPending ? <FacultyLoading label="Loading Referral details…" /> : null}
    {query.isError && !item ? <Notice role="alert" action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>{facultyReferralError(query.error, "read")}</Notice> : null}
    {item && query.isError ? <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
    {item ? <Panel data-guide-target="faculty-details"><SubmissionFacts item={item} /><PanelMessage>{item.state === "SUBMITTED" ? "Submitted records the online submission. It does not indicate acknowledgment or review by the Guidance Office." : item.state === "RECEIVED_BY_GCO" ? "The Guidance Office recorded receipt of this Referral." : "Administrative handling is complete. See Help for what this status means."}</PanelMessage>{messageable ? <PanelMessage action={<GuardedPortalLink href={`/portal/messages/new?referral=${referralId}`} className={buttonVariants({ variant: "secondary" })}>Message Guidance Office</GuardedPortalLink>}>Ask the Guidance Office about this Referral in Messages. The conversation does not change the Referral record.</PanelMessage> : null}</Panel> : null}
  </section>;
}

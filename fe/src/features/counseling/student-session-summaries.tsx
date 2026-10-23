"use client";

import Link from "next/link";
import { useSearchParams, useRouter, usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import {
  counselingDeliveryModeLabel,
  counselingErrorMessage,
  CounselingPageHeading,
  CounselingQueryError,
  CounselingUnavailable,
  formatCounselingDateTime,
  StudentSessionSummaryDetailSkeleton,
} from "@/features/counseling/counseling-shared";
import type { CounselingAccess } from "@/features/counseling/counseling-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useCounselingGetMyStudentSessionSummary,
  useCounselingListMyStudentSessionSummaries,
} from "@/lib/api/generated/counseling/counseling";

function positivePage(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function excerpt(content: string): string {
  const compact = content.trim().replace(/\s+/g, " ");
  return compact.length > 180 ? `${compact.slice(0, 177)}…` : compact;
}

export function StudentSessionSummaries({ access }: { access: CounselingAccess }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const page = positivePage(searchParams.get("page"));
  const summaries = useCounselingListMyStudentSessionSummaries(
    { page, page_size: 20 },
    { query: { enabled: access.canViewOwnStudentSessionSummaries, retry: false } },
  );
  const items = summaries.data?.data.items ?? [];

  return (
    <div>
      <CounselingPageHeading title="Student Session Summaries" description="View summaries that your Counselor has published for you." />
      <Panel aria-label="Published Student Session Summaries">
      {summaries.isPending ? <RowsSkeleton label="Loading shared Student Session Summaries…" rows={2} /> : summaries.isError ? <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void summaries.refetch()}>Retry</Button>}>{counselingErrorMessage(summaries.error, "Published Student Session Summaries could not be loaded.")}</PanelMessage> : items.length === 0 ? <PanelMessage>No Student Session Summaries have been published for you yet.</PanelMessage> : (
        <>
          <ul className="divide-y divide-border" aria-label="Published Student Session Summaries">
            {items.map((summary) => (
              <li key={summary.id}>
                <Link href={`/portal/counseling/student-session-summaries/${summary.id}`} className="block px-4 py-4 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-5">
                  <span className="font-semibold text-brand underline-offset-2 hover:underline">Counseling on {formatCounselingDateTime(summary.counseling_ended_at)}</span>
                  <span className="mt-1 block text-sm text-muted">{counselingDeliveryModeLabel(summary.delivery_mode)} · Published {formatCounselingDateTime(summary.published_at)}</span>
                  {summary.content.trim() ? <span className="mt-2 block max-w-4xl text-sm leading-6 text-ink">{excerpt(summary.content)}</span> : null}
                </Link>
              </li>
            ))}
          </ul>
          <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" label="Student Session Summary pages" page={summaries.data?.data.page ?? page} hasNext={summaries.data?.data.has_next ?? false} onPageChange={(nextPage) => {
            const next = new URLSearchParams(searchParams.toString());
            if (nextPage > 1) next.set("page", String(nextPage)); else next.delete("page");
            const query = next.toString();
            router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
          }} />
        </>
      )}
      </Panel>
    </div>
  );
}

const summariesBackLink = <Link href="/portal/counseling" className={pageBackLinkClass}>Back to Student Session Summaries</Link>;

export function StudentSessionSummaryDetail({ summaryId }: { summaryId: string }) {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const query = useCounselingGetMyStudentSessionSummary(summaryId, { query: { enabled: access.canViewOwnStudentSessionSummaries, retry: false } });
  const summary = query.data?.data;
  if (!access.canViewOwnStudentSessionSummaries) return <CounselingUnavailable title="Student Session Summary unavailable">This student session summary is unavailable.</CounselingUnavailable>;
  if (query.isPending) return <StudentSessionSummaryDetailSkeleton />;
  if (query.isError || !summary) return <div><CounselingPageHeading title="Student Session Summary" back={summariesBackLink} /><CounselingQueryError message={counselingErrorMessage(query.error, "This student session summary is unavailable.")} onRetry={() => void query.refetch()} /></div>;

  return (
    <article className="max-w-4xl">
      <CounselingPageHeading title="Student Session Summary" description={`Counseling ended ${formatCounselingDateTime(summary.counseling_ended_at)} · ${counselingDeliveryModeLabel(summary.delivery_mode)} · Published ${formatCounselingDateTime(summary.published_at)}`} back={summariesBackLink} />
      <Panel as="div" className="px-5 py-5 sm:px-6">
        <div className="whitespace-pre-wrap break-words text-sm leading-7 text-ink">{summary.content}</div>
      </Panel>
    </article>
  );
}

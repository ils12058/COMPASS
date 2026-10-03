"use client";

import Link from "next/link";
import { useSearchParams, useRouter, usePathname } from "next/navigation";

import { Button, buttonVariants } from "@/components/ui/button";
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
  SharedSummaryDetailSkeleton,
} from "@/features/counseling/counseling-shared";
import type { CounselingAccess } from "@/features/counseling/counseling-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useCounselingGetMySharedSummary,
  useCounselingListMySharedSummaries,
} from "@/lib/api/generated/counseling/counseling";

function positivePage(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function excerpt(content: string): string {
  const compact = content.trim().replace(/\s+/g, " ");
  return compact.length > 180 ? `${compact.slice(0, 177)}…` : compact;
}

export function StudentSharedSummaries({ access }: { access: CounselingAccess }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const page = positivePage(searchParams.get("page"));
  const summaries = useCounselingListMySharedSummaries(
    { page, page_size: 20 },
    { query: { enabled: access.canViewOwnSummaries, retry: false } },
  );
  const items = summaries.data?.data.items ?? [];

  return (
    <div>
      <CounselingPageHeading title="Counseling summaries" description="View summaries that your Counselor has explicitly shared with you." />
      <Panel aria-label="Published Counseling summaries">
      {summaries.isPending ? <RowsSkeleton label="Loading published Counseling summaries…" rows={2} /> : summaries.isError ? <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void summaries.refetch()}>Retry</Button>}>{counselingErrorMessage(summaries.error, "Published Counseling summaries could not be loaded.")}</PanelMessage> : items.length === 0 ? <PanelMessage>No Counseling summaries have been shared with you yet.</PanelMessage> : (
        <>
          <ul className="divide-y divide-border" aria-label="Published Counseling summaries">
            {items.map((summary) => (
              <li key={summary.id}>
                <Link href={`/portal/counseling/summaries/${summary.id}`} className="block px-4 py-4 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-5">
                  <span className="font-semibold text-brand underline-offset-2 hover:underline">Counseling on {formatCounselingDateTime(summary.counseling_ended_at)}</span>
                  <span className="mt-1 block text-sm text-muted">{counselingDeliveryModeLabel(summary.delivery_mode)} · Shared {formatCounselingDateTime(summary.published_at)}</span>
                  {summary.content.trim() ? <span className="mt-2 block max-w-4xl text-sm leading-6 text-ink">{excerpt(summary.content)}</span> : null}
                </Link>
              </li>
            ))}
          </ul>
          <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" label="Shared Summary pages" page={summaries.data?.data.page ?? page} hasNext={summaries.data?.data.has_next ?? false} onPageChange={(nextPage) => {
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

export function StudentSharedSummaryDetail({ summaryId }: { summaryId: string }) {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const query = useCounselingGetMySharedSummary(summaryId, { query: { enabled: access.canViewOwnSummaries, retry: false } });
  const summary = query.data?.data;
  if (!access.canViewOwnSummaries) return <CounselingUnavailable title="Counseling summary unavailable">This shared summary is unavailable to this account.</CounselingUnavailable>;
  if (query.isPending) return <SharedSummaryDetailSkeleton />;
  if (query.isError || !summary) return <div><CounselingPageHeading title="Counseling summary" /><CounselingQueryError message={counselingErrorMessage(query.error, "This shared summary is unavailable to this account.")} onRetry={() => void query.refetch()} /></div>;

  return (
    <article className="max-w-4xl">
      <CounselingPageHeading title="Counseling summary" description={`Counseling ended ${formatCounselingDateTime(summary.counseling_ended_at)} · ${counselingDeliveryModeLabel(summary.delivery_mode)} · Shared ${formatCounselingDateTime(summary.published_at)}`} action={<Link href="/portal/counseling" className={buttonVariants({ variant: "secondary" })}>Back to Counseling summaries</Link>} />
      <Panel as="div" className="px-5 py-5 sm:px-6">
        <div className="whitespace-pre-wrap break-words text-sm leading-7 text-ink">{summary.content}</div>
      </Panel>
    </article>
  );
}

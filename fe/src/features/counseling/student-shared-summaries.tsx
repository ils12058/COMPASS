"use client";

import Link from "next/link";
import { useSearchParams, useRouter, usePathname } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import {
  counselingDeliveryModeLabel,
  counselingErrorMessage,
  CounselingPageHeading,
  CounselingPagination,
  CounselingQueryError,
  formatCounselingDateTime,
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
      {summaries.isPending ? <div aria-busy="true" className="space-y-4"><span className="sr-only">Loading published Counseling summaries…</span><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /></div> : summaries.isError ? <CounselingQueryError message={counselingErrorMessage(summaries.error, "Published Counseling summaries could not be loaded.")} onRetry={() => void summaries.refetch()} /> : items.length === 0 ? <p className="border-y border-border py-6 text-sm text-muted">No Counseling summaries have been shared with you yet.</p> : (
        <>
          <ul className="divide-y divide-border border-y border-border" aria-label="Published Counseling summaries">
            {items.map((summary) => (
              <li key={summary.id} className="py-5">
                <Link href={`/portal/counseling/summaries/${summary.id}`} className="block rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                  <span className="font-semibold text-brand underline-offset-2 hover:underline">Counseling on {formatCounselingDateTime(summary.counseling_ended_at)}</span>
                  <span className="mt-1 block text-sm text-muted">{counselingDeliveryModeLabel(summary.delivery_mode)} · Shared {formatCounselingDateTime(summary.published_at)}</span>
                  {summary.content.trim() ? <span className="mt-2 block max-w-4xl text-sm leading-6 text-ink">{excerpt(summary.content)}</span> : null}
                </Link>
              </li>
            ))}
          </ul>
          <CounselingPagination page={summaries.data?.data.page ?? page} hasNext={summaries.data?.data.has_next ?? false} onPageChange={(nextPage) => {
            const next = new URLSearchParams(searchParams.toString());
            if (nextPage > 1) next.set("page", String(nextPage)); else next.delete("page");
            const query = next.toString();
            router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
          }} />
        </>
      )}
    </div>
  );
}

export function StudentSharedSummaryDetail({ summaryId }: { summaryId: string }) {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const query = useCounselingGetMySharedSummary(summaryId, { query: { enabled: access.canViewOwnSummaries, retry: false } });
  const summary = query.data?.data;
  if (!access.canViewOwnSummaries) return <CounselingPageHeading title="Shared Summary unavailable" description="This published Shared Summary is not available within your current access." />;
  if (query.isPending) return <div aria-busy="true"><span className="sr-only">Loading published Shared Summary…</span><Skeleton className="h-10 w-2/3" /><Skeleton className="mt-4 h-32 w-full" /></div>;
  if (query.isError || !summary) return <CounselingQueryError message={counselingErrorMessage(query.error, "This published Shared Summary is not available within your current access.")} onRetry={() => void query.refetch()} />;

  return (
    <article className="max-w-4xl">
      <CounselingPageHeading title="Counseling summary" description={`Counseling ended ${formatCounselingDateTime(summary.counseling_ended_at)} · ${counselingDeliveryModeLabel(summary.delivery_mode)} · Shared ${formatCounselingDateTime(summary.published_at)}`} action={<Link href="/portal/counseling" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Counseling summaries</Link>} />
      <div className="whitespace-pre-wrap break-words text-sm leading-7 text-ink">{summary.content}</div>
    </article>
  );
}

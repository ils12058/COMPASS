"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { GoodMoralError, GoodMoralHeading, GoodMoralStatus, formatGoodMoralDateTime, goodMoralVariantLabel } from "@/features/good-moral/good-moral-shared";
import { useGoodMoralListMyRequests } from "@/lib/api/generated/good-moral/good-moral";

export function GoodMoralStudentHistory({
  canView,
  requestHref,
  requestLabel,
}: {
  canView: boolean;
  requestHref: string | null;
  requestLabel: string | null;
}) {
  const history = useGoodMoralListMyRequests({ query: { enabled: canView, retry: false } });
  const confirmed = safeQueryData(history);

  return (
    <section className="space-y-6" aria-labelledby="good-moral-student-heading">
      <GoodMoralHeading
        headingId="good-moral-student-heading"
        title="Good Moral"
        description="Request and review your Good Moral Character certificates."
        action={requestHref && requestLabel ? (
          <Link href={requestHref} className={buttonVariants({ variant: "primary" })}>
            {requestLabel}
          </Link>
        ) : undefined}
      />

      {canView ? (
        <section aria-labelledby="good-moral-my-requests-heading">
          <h2 id="good-moral-my-requests-heading" className="font-heading text-xl font-semibold text-ink">My requests</h2>
          {history.isError && confirmed ? <RefreshFailureNotice onRetry={() => void history.refetch()} retrying={history.isFetching} /> : null}
          {history.isPending ? (
            <div className="mt-4 space-y-3" aria-busy="true"><span className="sr-only">Loading Good Moral requests…</span>
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : !confirmed ? (
            <div className="mt-4"><GoodMoralError error={history.error} fallback="Your Good Moral requests could not be loaded." onRetry={() => void history.refetch()} /></div>
          ) : confirmed.data.items.length === 0 ? (
            <p className="mt-4 border-y border-border py-5 text-sm text-muted">
              You do not have any Good Moral requests yet.
            </p>
          ) : (
            <ol className="mt-4 divide-y divide-border border-y border-border">
              {confirmed.data.items.map((item) => (
                <li key={item.id} className="grid gap-3 py-4 sm:grid-cols-[minmax(12rem,1fr)_auto] sm:items-center">
                  <div className="min-w-0">
                    <Link href={`/portal/good-moral/${item.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                      {goodMoralVariantLabel(item.variant)} certificate
                    </Link>
                    <p className="mt-1 break-words text-sm text-muted">{item.applicant_name || "Applicant name not provided"}</p>
                    <p className="mt-1 text-xs text-muted">Requested {formatGoodMoralDateTime(item.created_at)}</p>
                    {item.issued_at ? <p className="mt-1 text-xs text-muted">Issued {formatGoodMoralDateTime(item.issued_at)}</p> : null}
                    {item.cancelled_at ? <p className="mt-1 text-xs text-muted">Cancelled {formatGoodMoralDateTime(item.cancelled_at)}</p> : null}
                  </div>
                  <div className="flex items-center justify-between gap-3 sm:justify-end">
                    <GoodMoralStatus status={item.status} />
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      ) : (
        <p className="border-y border-border py-5 text-sm text-muted">Request history is not available for your current access.</p>
      )}
    </section>
  );
}

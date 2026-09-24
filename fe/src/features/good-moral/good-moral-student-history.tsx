"use client";

import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
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

  return (
    <section className="space-y-6" aria-labelledby="good-moral-student-heading">
      <GoodMoralHeading
        headingId="good-moral-student-heading"
        title="Good Moral"
        description="Request and review your Good Moral Character certificates."
        action={requestHref && requestLabel ? (
          <Link href={requestHref} className="inline-flex min-h-10 items-center justify-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body">
            {requestLabel}
          </Link>
        ) : undefined}
      />

      {canView ? (
        <section aria-labelledby="good-moral-my-requests-heading">
          <h2 id="good-moral-my-requests-heading" className="font-heading text-xl font-semibold text-ink">My requests</h2>
          {history.isPending ? (
            <div className="mt-4 space-y-3" aria-busy="true" aria-label="Loading Good Moral requests">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : history.isError ? (
            <div className="mt-4"><GoodMoralError error={history.error} fallback="Your Good Moral requests could not be loaded." onRetry={() => void history.refetch()} /></div>
          ) : history.data.data.items.length === 0 ? (
            <p className="mt-4 border-y border-border py-5 text-sm text-muted">
              You do not have any Good Moral requests yet.
            </p>
          ) : (
            <ol className="mt-4 divide-y divide-border border-y border-border">
              {history.data.data.items.map((item) => (
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

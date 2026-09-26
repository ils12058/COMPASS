"use client";

import { keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { reviewTypeShortLabels } from "@/features/privacy-governance/privacy-governance-presentation";
import {
  EmptyListState,
  PRIVACY_PAGE_SIZE,
  PrivacyListSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
  privacySelectClass,
  recordLinkClass,
  RefreshingNotice,
  ReviewStatusBadge,
  tableCellClass,
  tableHeadClass,
  tableHeaderCellClass,
  tableRowHeaderClass,
  useListSearchParams,
} from "@/features/privacy-governance/privacy-governance-shared";
import { formatDateTime } from "@/lib/date-time";
import { ReviewStatusValue, ReviewTypeValue } from "@/lib/api/generated/model";
import { usePrivacyGovernanceListAllReviews } from "@/lib/api/generated/privacy-governance/privacy-governance";

type StatusFilter = "OPEN" | "RESOLVED" | "ALL";

function statusFilterFrom(value: string | null): StatusFilter {
  return value === "RESOLVED" || value === "ALL" ? value : "OPEN";
}

function typeFilterFrom(value: string | null): ReviewTypeValue | undefined {
  return value === ReviewTypeValue.PRIVACY_REVIEW || value === ReviewTypeValue.PIA
    ? value
    : undefined;
}

export function ReviewsPage() {
  const { searchParams, page, update, setPage } = useListSearchParams();
  // Open reviews are the actionable queue, so they are the default view.
  const status = statusFilterFrom(searchParams.get("status"));
  const reviewType = typeFilterFrom(searchParams.get("type"));
  const query = usePrivacyGovernanceListAllReviews(
    {
      page,
      page_size: PRIVACY_PAGE_SIZE,
      ...(status === "ALL" ? {} : { status: ReviewStatusValue[status] }),
      ...(reviewType ? { review_type: reviewType } : {}),
    },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const result = query.data?.data;
  const showAll = (
    <Button variant="secondary" onClick={() => update({ status: "ALL", type: null })}>
      Show all reviews and PIAs
    </Button>
  );

  return (
    <section>
      <PrivacyPageHeader
        title="Reviews & PIAs"
        description="Reviews and privacy impact assessments are started from a Processing Activity."
      />

      <div className="flex flex-wrap gap-4">
        <div className="grid w-full max-w-48 gap-2">
          <label htmlFor="review-status-filter" className="text-sm font-medium text-ink">
            Status
          </label>
          <select
            id="review-status-filter"
            className={privacySelectClass}
            value={status}
            onChange={(event) => {
              const next = statusFilterFrom(event.target.value);
              update({ status: next === "OPEN" ? null : next });
            }}
          >
            <option value="OPEN">Open</option>
            <option value="RESOLVED">Resolved</option>
            <option value="ALL">All</option>
          </select>
        </div>
        <div className="grid w-full max-w-48 gap-2">
          <label htmlFor="review-type-filter" className="text-sm font-medium text-ink">
            Type
          </label>
          <select
            id="review-type-filter"
            className={privacySelectClass}
            value={reviewType ?? ""}
            onChange={(event) => update({ type: typeFilterFrom(event.target.value) ?? null })}
          >
            <option value="">All</option>
            <option value={ReviewTypeValue.PRIVACY_REVIEW}>Privacy review</option>
            <option value={ReviewTypeValue.PIA}>PIA</option>
          </select>
        </div>
      </div>

      {query.isPending ? (
        <div className="mt-5">
          <PrivacyListSkeleton label="Loading reviews and PIAs…" />
        </div>
      ) : query.isError && !result ? (
        <div className="mt-5">
          <PrivacyQueryError
            error={query.error}
            fallback="Reviews and PIAs could not be loaded."
            onRetry={() => void query.refetch()}
          />
        </div>
      ) : result && result.items.length === 0 ? (
        reviewType ? (
          <EmptyListState message="No reviews match the selected filters." action={showAll} />
        ) : status === "OPEN" ? (
          <EmptyListState message="No open reviews or PIAs." action={showAll} />
        ) : status === "RESOLVED" ? (
          <EmptyListState message="No resolved reviews or PIAs." action={showAll} />
        ) : (
          <EmptyListState
            message={
              page === 1
                ? "No reviews or PIAs have been recorded."
                : "No reviews or PIAs on this page."
            }
          />
        )
      ) : result ? (
        <>
          <RefreshingNotice show={query.isFetching} label="Refreshing reviews and PIAs…" />
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[46rem] border-collapse text-left text-sm">
              <caption className="sr-only">Reviews and PIAs</caption>
              <thead className={tableHeadClass}>
                <tr>
                  <th scope="col" className={tableHeaderCellClass}>
                    Processing Activity
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Type
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Status
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Reviewed by
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {result.items.map((review) => (
                  <tr key={review.id}>
                    <th scope="row" className={tableRowHeaderClass + " min-w-48 text-ink"}>
                      {review.processing_activity.name}
                      <span className="mt-1 block break-all font-mono text-xs text-muted">
                        {review.processing_activity.code}
                      </span>
                    </th>
                    <td className={tableCellClass}>
                      <Link
                        href={`/portal/privacy/reviews/${review.id}`}
                        className={recordLinkClass}
                      >
                        {reviewTypeShortLabels[review.review_type]}
                        <span className="sr-only">
                          {" "}for {review.processing_activity.name}, created{" "}
                          {formatDateTime(review.created_at)}
                        </span>
                      </Link>
                    </td>
                    <td className={tableCellClass}>
                      <ReviewStatusBadge status={review.status} />
                    </td>
                    <td className={tableCellClass + " text-ink"}>
                      {review.reviewed_by.display_name}
                    </td>
                    <td className={tableCellClass + " whitespace-nowrap text-ink"}>
                      {formatDateTime(review.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.page > 1 || result.has_next ? (
            <CanonicalPagination
              page={result.page}
              hasNext={result.has_next}
              onPageChange={setPage}
              label="Review pages"
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}

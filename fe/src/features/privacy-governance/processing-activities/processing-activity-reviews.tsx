"use client";

import { keepPreviousData, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  reviewTypeOptionLabels,
  reviewTypeShortLabels,
} from "@/features/privacy-governance/privacy-governance-presentation";
import {
  ActionMessages,
  PRIVACY_PAGE_SIZE,
  PrivacyListSkeleton,
  PrivacyQueryError,
  recordLinkClass,
  ReviewStatusBadge,
  tableCellClass,
  tableHeadClass,
  tableHeaderCellClass,
  tableRowHeaderClass,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  reviewFieldLabels,
  ReviewTextFields,
  type ReviewTextValues,
} from "@/features/privacy-governance/reviews/review-text-fields";
import { formatDateTime } from "@/lib/date-time";
import {
  ReviewTypeValue,
  type ProcessingActivityResponse,
} from "@/lib/api/generated/model";
import { getOverviewGetSummaryQueryKey } from "@/lib/api/generated/overview/overview";
import {
  getPrivacyGovernanceListAllReviewsQueryKey,
  getPrivacyGovernanceListReviewsQueryKey,
  usePrivacyGovernanceCreateReview,
  usePrivacyGovernanceListReviews,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

function StartReviewForm({
  processing,
  onCancel,
}: {
  processing: ProcessingActivityResponse;
  onCancel: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = usePrivacyGovernanceCreateReview();
  const action = usePrivacyAction(reviewFieldLabels);
  const [reviewType, setReviewType] = useState<ReviewTypeValue | "">("");
  const [text, setText] = useState<ReviewTextValues>({
    scope: "",
    findings: "",
    recommendations: "",
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reviewType) {
      action.setError("Choose a review type.");
      return;
    }
    const result = await action.run(
      () =>
        create.mutateAsync({
          processingId: processing.id,
          data: {
            review_type: reviewType,
            scope_summary: text.scope,
            findings_summary: text.findings,
            recommendations_summary: text.recommendations,
          },
        }),
      "The review could not be started.",
    );
    if (!result) return;
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceListReviewsQueryKey(processing.id),
    });
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceListAllReviewsQueryKey(),
    });
    void queryClient.invalidateQueries({ queryKey: getOverviewGetSummaryQueryKey() });
    router.push(`/portal/privacy/reviews/${result.data.id}?created=1`);
  }

  return (
    <>
      <form
        aria-labelledby="start-review-heading"
        className="mt-4 grid max-w-3xl gap-5 border-y border-border py-6"
        onSubmit={(event) => void submit(event)}
      >
        <h3 id="start-review-heading" className="font-heading text-lg font-semibold text-ink">
          Start a privacy review or PIA
        </h3>
        <fieldset className="grid gap-2">
          <legend className="text-sm font-medium text-ink">Review type</legend>
          {Object.values(ReviewTypeValue).map((type) => (
            <label key={type} className="inline-flex min-h-10 items-center gap-3 text-sm text-ink">
              <input
                type="radio"
                name="start-review-type"
                className="h-4 w-4 accent-brand"
                required
                checked={reviewType === type}
                onChange={() => setReviewType(type)}
              />
              {reviewTypeOptionLabels[type]}
            </label>
          ))}
        </fieldset>
        <ReviewTextFields idPrefix="start-review" values={text} onChange={setText} />
        <ActionMessages error={action.error} notice={action.notice} className="" />
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" disabled={create.isPending} onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Starting…" : "Start review"}
          </Button>
        </div>
      </form>
      {/* Outside the form: submit events bubble through portals in React. */}
      {action.stepUpDialog}
    </>
  );
}

export function ProcessingActivityReviews({
  processing,
  canManage,
}: {
  processing: ProcessingActivityResponse;
  canManage: boolean;
}) {
  const [page, setPage] = useState(1);
  const [starting, setStarting] = useState(false);
  const reviews = usePrivacyGovernanceListReviews(
    processing.id,
    { page, page_size: PRIVACY_PAGE_SIZE },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const result = reviews.data?.data;

  return (
    <section aria-labelledby="processing-reviews-heading" className="py-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2
          id="processing-reviews-heading"
          className="font-heading text-lg font-semibold text-ink"
        >
          Reviews & PIAs
        </h2>
        {canManage && processing.is_active && !starting ? (
          <Button variant="secondary" onClick={() => setStarting(true)}>
            Start privacy review / PIA
          </Button>
        ) : null}
      </div>

      {starting ? (
        <StartReviewForm processing={processing} onCancel={() => setStarting(false)} />
      ) : null}

      <div className="mt-4">
        {reviews.isPending ? (
          <PrivacyListSkeleton rows={2} label="Loading reviews…" />
        ) : reviews.isError && !result ? (
          <PrivacyQueryError
            error={reviews.error}
            fallback="Reviews for this processing activity could not be loaded."
            onRetry={() => void reviews.refetch()}
          />
        ) : result && result.items.length === 0 ? (
          <p className="text-sm text-muted">
            No reviews or PIAs have been recorded for this processing activity.
          </p>
        ) : result ? (
          <>
            <div className="overflow-x-auto border-y border-border">
              <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
                <caption className="sr-only">
                  Reviews and PIAs for {processing.name}
                </caption>
                <thead className={tableHeadClass}>
                  <tr>
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
                      <th scope="row" className={tableRowHeaderClass}>
                        <Link
                          href={`/portal/privacy/reviews/${review.id}`}
                          className={recordLinkClass}
                        >
                          {reviewTypeShortLabels[review.review_type]}
                          <span className="sr-only">
                            {" "}created {formatDateTime(review.created_at)}
                          </span>
                        </Link>
                      </th>
                      <td className={tableCellClass}>
                        <ReviewStatusBadge status={review.status} />
                      </td>
                      <td className={tableCellClass + " text-ink"}>
                        {review.reviewed_by.display_name}
                      </td>
                      <td className={tableCellClass + " text-ink"}>
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
                label="Review pages for this processing activity"
              />
            ) : null}
          </>
        ) : null}
      </div>
    </section>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import { reviewTypeTitles } from "@/features/privacy-governance/privacy-governance-presentation";
import {
  ActionMessages,
  DetailSection,
  invalidatePrivacyRecords,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyRecordUnavailable,
  privacyPaths,
  ReviewStatusBadge,
  textLinkClass,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  reviewFieldLabels,
  ReviewTextFields,
  type ReviewTextValues,
} from "@/features/privacy-governance/reviews/review-text-fields";
import { formatDateTime } from "@/lib/date-time";
import {
  ReviewStatusValue,
  type PrivacyReviewResponse,
  type PrivacyReviewUpdateRequest,
} from "@/lib/api/generated/model";
import { getOverviewGetSummaryQueryKey } from "@/lib/api/generated/overview/overview";
import {
  usePrivacyGovernanceGetReview,
  usePrivacyGovernanceResolveReview,
  usePrivacyGovernanceUpdateReview,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

function ReviewEditor({
  review,
  onDone,
}: {
  review: PrivacyReviewResponse;
  onDone: (saved: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const update = usePrivacyGovernanceUpdateReview();
  const action = usePrivacyAction(reviewFieldLabels);
  const [baseline] = useState<ReviewTextValues>(() => ({
    scope: review.scope_summary,
    findings: review.findings_summary,
    recommendations: review.recommendations_summary,
  }));
  const [values, setValues] = useState(baseline);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const changes: PrivacyReviewUpdateRequest = {};
    if (values.scope !== baseline.scope) changes.scope_summary = values.scope;
    if (values.findings !== baseline.findings) changes.findings_summary = values.findings;
    if (values.recommendations !== baseline.recommendations) {
      changes.recommendations_summary = values.recommendations;
    }
    if (Object.keys(changes).length === 0) {
      action.setError(null);
      action.setNotice("No changes to save.");
      return;
    }
    const result = await action.run(
      () => update.mutateAsync({ reviewId: review.id, data: changes }),
      "The review could not be saved.",
    );
    if (!result) return;
    await invalidatePrivacyRecords(
      queryClient,
      privacyPaths.reviews,
      privacyPaths.processingActivities,
    );
    onDone(true);
  }

  return (
    <>
      <form className="grid max-w-3xl gap-5" onSubmit={(event) => void submit(event)}>
        <ReviewTextFields idPrefix="edit-review" values={values} onChange={setValues} />
        <ActionMessages error={action.error} notice={action.notice} className="" />
        <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-6">
          <Button variant="secondary" disabled={update.isPending} onClick={() => onDone(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
      {action.stepUpDialog}
    </>
  );
}

export function ReviewDetailPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const searchParams = useSearchParams();
  const { canManage } = usePrivacyAccess();
  const queryClient = useQueryClient();
  const detail = usePrivacyGovernanceGetReview(reviewId, { query: { retry: false } });
  const resolve = usePrivacyGovernanceResolveReview();
  const action = usePrivacyAction(reviewFieldLabels);
  const [editing, setEditing] = useState(false);
  const [resolveOpen, setResolveOpen] = useState(false);
  const [resolution, setResolution] = useState("");

  if (detail.isPending) return <PrivacyDetailSkeleton label="Loading review…" />;
  if (detail.isError) {
    return (
      <PrivacyRecordUnavailable
        title="Review unavailable"
        error={detail.error}
        fallback="The review could not be loaded."
        backHref="/portal/privacy/reviews"
        backLabel="Reviews & PIAs"
        onRetry={() => void detail.refetch()}
      />
    );
  }

  const review = detail.data.data;
  const isOpen = review.status === ReviewStatusValue.OPEN;
  const manageable = canManage && isOpen;
  const activity = review.processing_activity;
  const reviewKind = review.review_type === "PIA" ? "PIA" : "privacy review";

  async function confirmResolve() {
    const result = await action.run(
      () =>
        resolve.mutateAsync({
          reviewId,
          data: { resolution_summary: resolution },
        }),
      "The review could not be resolved.",
      { onStepUpRequired: () => setResolveOpen(false) },
    );
    if (!result) return;
    setResolveOpen(false);
    setResolution("");
    action.setNotice("Review resolved.");
    void invalidatePrivacyRecords(
      queryClient,
      privacyPaths.reviews,
      privacyPaths.processingActivities,
    );
    void queryClient.invalidateQueries({ queryKey: getOverviewGetSummaryQueryKey() });
  }

  return (
    <article>
      <PrivacyPageHeader
        title={reviewTypeTitles[review.review_type]}
        backHref="/portal/privacy/reviews"
        backLabel="Reviews & PIAs"
        meta={
          <>
            <ReviewStatusBadge status={review.status} />
            <span>Reviewed by {review.reviewed_by.display_name}</span>
          </>
        }
        action={
          manageable && !editing ? (
            <>
              <Button
                variant="secondary"
                onClick={() => {
                  action.reset();
                  setEditing(true);
                }}
              >
                Edit
              </Button>
              <Button
                onClick={() => {
                  action.reset();
                  setResolveOpen(true);
                }}
              >
                Resolve review
              </Button>
            </>
          ) : null
        }
      />

      {searchParams.get("created") === "1" && !editing ? (
        <p role="status" className="mb-4 text-sm text-success">
          Review started.
        </p>
      ) : null}
      <ActionMessages
        error={resolveOpen ? null : action.error}
        notice={action.notice}
        className="mb-4"
      />

      <dl className="mb-6 grid max-w-4xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <dt className="text-xs font-semibold text-muted">Processing Activity</dt>
          <dd className="mt-1 break-words text-sm text-ink">
            <Link
              href={`/portal/privacy/processing-activities/${activity.id}`}
              className={textLinkClass}
            >
              {activity.name}
            </Link>
            <span className="ml-2 font-mono text-xs text-muted">{activity.code}</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Created</dt>
          <dd className="mt-1 text-sm text-ink">{formatDateTime(review.created_at)}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">
            {review.resolved_at ? "Resolved" : "Updated"}
          </dt>
          <dd className="mt-1 text-sm text-ink">
            {formatDateTime(review.resolved_at ?? review.updated_at)}
          </dd>
        </div>
      </dl>

      {editing ? (
        <ReviewEditor
          key={review.updated_at}
          review={review}
          onDone={(saved) => {
            setEditing(false);
            if (saved) action.setNotice("Review updated.");
          }}
        />
      ) : (
        <div className="max-w-4xl divide-y divide-border border-y border-border">
          <DetailSection title="Scope">
            <PlainTextBlock text={review.scope_summary} />
          </DetailSection>
          <DetailSection title="Findings">
            <PlainTextBlock text={review.findings_summary} />
          </DetailSection>
          <DetailSection title="Recommendations">
            <PlainTextBlock text={review.recommendations_summary} />
          </DetailSection>
          {isOpen ? null : (
            <DetailSection title="Resolution">
              <PlainTextBlock text={review.resolution_summary} />
            </DetailSection>
          )}
        </div>
      )}

      <PrivacyConfirmDialog
        open={resolveOpen}
        title={`Resolve this ${reviewKind}?`}
        description={
          <p>Resolved reviews cannot be edited through the ordinary workflow.</p>
        }
        confirmLabel="Resolve review"
        pendingLabel="Resolving…"
        pending={resolve.isPending}
        confirmDisabled={!resolution.trim()}
        error={resolveOpen ? action.error : null}
        onOpenChange={(open) => {
          setResolveOpen(open);
          if (!open) action.setError(null);
        }}
        onConfirm={() => void confirmResolve()}
      >
        <div className="mt-4 grid gap-2">
          <Label htmlFor="review-resolution">Resolution summary</Label>
          <Textarea
            id="review-resolution"
            required
            maxLength={4000}
            rows={4}
            value={resolution}
            onChange={(event) => setResolution(event.target.value)}
          />
        </div>
      </PrivacyConfirmDialog>
      {action.stepUpDialog}
    </article>
  );
}

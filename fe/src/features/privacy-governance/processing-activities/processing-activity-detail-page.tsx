"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import {
  ActionMessages,
  ActiveBadge,
  CategoryList,
  DetailSection,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyRecordUnavailable,
  secondaryLinkClass,
  textLinkClass,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import { ProcessingActivityReviews } from "@/features/privacy-governance/processing-activities/processing-activity-reviews";
import { formatDateTime } from "@/lib/date-time";
import type { ProcessingActivityResponse } from "@/lib/api/generated/model";
import {
  getPrivacyGovernanceGetProcessingActivityQueryKey,
  getPrivacyGovernanceListProcessingActivitiesQueryKey,
  usePrivacyGovernanceGetProcessingActivity,
  usePrivacyGovernanceRetireProcessingActivity,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

function RetentionDetails({ item }: { item: ProcessingActivityResponse }) {
  return (
    <dl className="grid max-w-3xl gap-4 sm:grid-cols-2">
      <div>
        <dt className="text-xs font-semibold text-muted">Retention Policy</dt>
        <dd className="mt-1 text-sm text-ink">
          {item.retention_policy ? (
            <>
              <Link
                href={`/portal/privacy/retention-policies/${item.retention_policy.id}`}
                className={textLinkClass}
              >
                {item.retention_policy.name}
              </Link>
              {item.retention_policy.is_active ? null : (
                <span className="text-muted"> (retired)</span>
              )}
            </>
          ) : (
            <span className="text-muted">No internal Retention Policy</span>
          )}
        </dd>
      </div>
      <div>
        <dt className="text-xs font-semibold text-muted">
          External retention-policy reference
        </dt>
        <dd className="mt-1 break-words text-sm text-ink">
          {item.retention_policy_reference || (
            <span className="text-muted">None recorded.</span>
          )}
        </dd>
      </div>
    </dl>
  );
}

export function ProcessingActivityDetailPage() {
  const { processingId } = useParams<{ processingId: string }>();
  const searchParams = useSearchParams();
  const { canManage } = usePrivacyAccess();
  const queryClient = useQueryClient();
  const detail = usePrivacyGovernanceGetProcessingActivity(processingId, {
    query: { retry: false },
  });
  const retire = usePrivacyGovernanceRetireProcessingActivity();
  const action = usePrivacyAction();
  const [retireOpen, setRetireOpen] = useState(false);

  if (detail.isPending) return <PrivacyDetailSkeleton label="Loading processing activity…" />;
  if (detail.isError) {
    return (
      <PrivacyRecordUnavailable
        title="Processing activity unavailable"
        error={detail.error}
        fallback="The processing activity could not be loaded."
        backHref="/portal/privacy/processing-activities"
        backLabel="Processing Activities"
        onRetry={() => void detail.refetch()}
      />
    );
  }

  const item = detail.data.data;
  const manageable = canManage && item.is_active;

  async function confirmRetire() {
    const result = await action.run(
      () => retire.mutateAsync({ processingId }),
      "The processing activity could not be retired.",
      { onStepUpRequired: () => setRetireOpen(false) },
    );
    if (!result) return;
    setRetireOpen(false);
    action.setNotice("Processing activity retired.");
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceGetProcessingActivityQueryKey(processingId),
    });
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceListProcessingActivitiesQueryKey(),
    });
  }

  return (
    <article>
      <PrivacyPageHeader
        title={item.name}
        backHref="/portal/privacy/processing-activities"
        backLabel="Processing Activities"
        meta={
          <>
            <span className="break-all font-mono text-ink">{item.code}</span>
            <ActiveBadge active={item.is_active} />
            <span>Updated {formatDateTime(item.updated_at)}</span>
          </>
        }
        action={
          manageable ? (
            <>
              <Link
                href={`/portal/privacy/processing-activities/${item.id}/edit`}
                className={secondaryLinkClass}
              >
                Edit
              </Link>
              <Button
                variant="danger"
                onClick={() => {
                  action.reset();
                  setRetireOpen(true);
                }}
              >
                Retire
              </Button>
            </>
          ) : null
        }
      />

      {searchParams.get("created") === "1" ? (
        <p role="status" className="mb-4 text-sm text-success">
          Processing activity created.
        </p>
      ) : null}
      {searchParams.get("updated") === "1" ? (
        <p role="status" className="mb-4 text-sm text-success">
          Processing activity updated.
        </p>
      ) : null}
      <ActionMessages
        error={retireOpen ? null : action.error}
        notice={action.notice}
        className="mb-4"
      />

      <div className="max-w-4xl divide-y divide-border border-y border-border">
        <DetailSection title="Why we use this information">
          <PlainTextBlock text={item.purpose} />
        </DetailSection>
        <DetailSection title="Who the information is about">
          <CategoryList items={item.data_subject_categories} />
        </DetailSection>
        <DetailSection title="What information is used">
          <CategoryList items={item.personal_data_categories} />
        </DetailSection>
        <DetailSection title="Who may access it">
          <PlainTextBlock text={item.authorized_access_summary} />
        </DetailSection>
        <DetailSection title="How it is protected">
          <PlainTextBlock text={item.safeguards_summary} />
        </DetailSection>
        <DetailSection title="Choices and consent">
          <PlainTextBlock
            text={item.data_subject_choice_summary}
            empty="No user choice is recorded for this activity."
          />
        </DetailSection>
        <DetailSection title="Retention">
          <RetentionDetails item={item} />
        </DetailSection>
        <DetailSection title="Policy basis reference">
          {item.policy_basis_reference ? (
            <p className="break-words text-sm text-ink">{item.policy_basis_reference}</p>
          ) : (
            <p className="text-sm text-muted">None recorded.</p>
          )}
        </DetailSection>
        <ProcessingActivityReviews processing={item} canManage={canManage} />
      </div>

      <PrivacyConfirmDialog
        open={retireOpen}
        title="Retire this processing activity?"
        description={
          <p>
            {item.name} will remain available in governance history but will no
            longer be active.
          </p>
        }
        confirmLabel="Retire processing activity"
        pendingLabel="Retiring…"
        pending={retire.isPending}
        error={retireOpen ? action.error : null}
        destructive
        onOpenChange={(open) => {
          setRetireOpen(open);
          if (!open) action.setError(null);
        }}
        onConfirm={() => void confirmRetire()}
      />
      {action.stepUpDialog}
    </article>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  ActionMessages,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyRecordUnavailable,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  ProcessingActivityForm,
  processingActivityChanges,
  processingActivityFieldLabels,
  processingActivityFormValues,
  type ProcessingActivityFormValues,
} from "@/features/privacy-governance/processing-activities/processing-activity-form";
import type { ProcessingActivityResponse } from "@/lib/api/generated/model";
import {
  getPrivacyGovernanceGetProcessingActivityQueryKey,
  getPrivacyGovernanceListAllReviewsQueryKey,
  getPrivacyGovernanceListProcessingActivitiesQueryKey,
  usePrivacyGovernanceGetProcessingActivity,
  usePrivacyGovernanceUpdateProcessingActivity,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

function ProcessingActivityEditor({ item }: { item: ProcessingActivityResponse }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const update = usePrivacyGovernanceUpdateProcessingActivity();
  const action = usePrivacyAction(processingActivityFieldLabels);
  // Compare against the values the form opened with, so a background refresh
  // never turns untouched fields into changes.
  const [baseline] = useState(() => processingActivityFormValues(item));
  const detailHref = `/portal/privacy/processing-activities/${item.id}`;

  async function submit(values: ProcessingActivityFormValues) {
    const changes = processingActivityChanges(baseline, values);
    if (Object.keys(changes).length === 0) {
      action.setError(null);
      action.setNotice("No changes to save.");
      return;
    }
    const result = await action.run(
      () => update.mutateAsync({ processingId: item.id, data: changes }),
      "The processing activity could not be saved.",
    );
    if (!result) return;
    await queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceGetProcessingActivityQueryKey(item.id),
    });
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceListProcessingActivitiesQueryKey(),
    });
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceListAllReviewsQueryKey(),
    });
    router.push(`${detailHref}?updated=1`);
  }

  return (
    <section>
      <PrivacyPageHeader
        title={`Edit ${item.name}`}
        backHref={detailHref}
        backLabel={item.name}
      />
      <ProcessingActivityForm
        mode="edit"
        initial={baseline}
        currentPolicy={item.retention_policy}
        pending={update.isPending}
        submitLabel="Save changes"
        pendingLabel="Saving…"
        cancelHref={detailHref}
        messages={<ActionMessages error={action.error} notice={action.notice} />}
        onSubmit={(values) => void submit(values)}
      />
      {action.stepUpDialog}
    </section>
  );
}

export function ProcessingActivityEditPage() {
  const { processingId } = useParams<{ processingId: string }>();
  const { canManage } = usePrivacyAccess();
  const detail = usePrivacyGovernanceGetProcessingActivity(processingId, {
    query: { retry: false },
  });

  if (!canManage) {
    return (
      <WorkspaceUnavailable title="Processing activity editing unavailable">
        Your current access does not include managing Privacy Governance records.
      </WorkspaceUnavailable>
    );
  }
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

  return <ProcessingActivityEditor item={detail.data.data} />;
}

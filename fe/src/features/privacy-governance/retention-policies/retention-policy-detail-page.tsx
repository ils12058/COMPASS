"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import {
  ActionMessages,
  ActiveBadge,
  DetailSection,
  invalidatePrivacyRecords,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyRecordUnavailable,
  privacyPaths,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  RETENTION_BOUNDARY_NOTE,
  retentionChanges,
  retentionFieldLabels,
  retentionFormValues,
  RetentionPolicyForm,
  ReviewDueText,
  type RetentionFormValues,
} from "@/features/privacy-governance/retention-policies/retention-policy-form";
import { formatDateOnly, formatDateTime } from "@/lib/date-time";
import type { RetentionResponse } from "@/lib/api/generated/model";
import {
  usePrivacyGovernanceGetRetentionPolicy,
  usePrivacyGovernanceRetireRetentionPolicy,
  usePrivacyGovernanceUpdateRetentionPolicy,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

function RetentionPolicyEditor({
  item,
  onDone,
}: {
  item: RetentionResponse;
  onDone: (saved: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const update = usePrivacyGovernanceUpdateRetentionPolicy();
  const action = usePrivacyAction(retentionFieldLabels);
  const [baseline] = useState(() => retentionFormValues(item));

  async function submit(values: RetentionFormValues) {
    const changes = retentionChanges(baseline, values);
    if (Object.keys(changes).length === 0) {
      action.setError(null);
      action.setNotice("No changes to save.");
      return;
    }
    const result = await action.run(
      () => update.mutateAsync({ policyId: item.id, data: changes }),
      "The retention policy could not be saved.",
    );
    if (!result) return;
    await invalidatePrivacyRecords(
      queryClient,
      privacyPaths.retentionPolicies,
      privacyPaths.processingActivities,
    );
    onDone(true);
  }

  return (
    <>
      <RetentionPolicyForm
        mode="edit"
        initial={baseline}
        pending={update.isPending}
        submitLabel="Save changes"
        pendingLabel="Saving…"
        messages={<ActionMessages error={action.error} notice={action.notice} />}
        cancel={
          <Button variant="secondary" disabled={update.isPending} onClick={() => onDone(false)}>
            Cancel
          </Button>
        }
        onSubmit={(values) => void submit(values)}
      />
      {action.stepUpDialog}
    </>
  );
}

export function RetentionPolicyDetailPage() {
  const { policyId } = useParams<{ policyId: string }>();
  const searchParams = useSearchParams();
  const { canManage } = usePrivacyAccess();
  const queryClient = useQueryClient();
  const detail = usePrivacyGovernanceGetRetentionPolicy(policyId, {
    query: { retry: false },
  });
  const retire = usePrivacyGovernanceRetireRetentionPolicy();
  const action = usePrivacyAction();
  const [editing, setEditing] = useState(false);
  const [retireOpen, setRetireOpen] = useState(false);

  if (detail.isPending) return <PrivacyDetailSkeleton label="Loading retention policy…" />;
  if (detail.isError) {
    return (
      <PrivacyRecordUnavailable
        title="Retention policy unavailable"
        error={detail.error}
        fallback="The retention policy could not be loaded."
        backHref="/portal/privacy/retention-policies"
        backLabel="Retention Policies"
        onRetry={() => void detail.refetch()}
      />
    );
  }

  const policy = detail.data.data;
  const manageable = canManage && policy.is_active;

  async function confirmRetire() {
    const result = await action.run(
      () => retire.mutateAsync({ policyId }),
      "The retention policy could not be retired.",
      { onStepUpRequired: () => setRetireOpen(false) },
    );
    if (!result) return;
    setRetireOpen(false);
    action.setNotice("Retention policy retired.");
    void invalidatePrivacyRecords(
      queryClient,
      privacyPaths.retentionPolicies,
      privacyPaths.processingActivities,
    );
  }

  return (
    <article>
      <PrivacyPageHeader
        title={editing ? `Edit ${policy.name}` : policy.name}
        backHref="/portal/privacy/retention-policies"
        backLabel="Retention Policies"
        meta={
          <>
            <span className="break-all font-mono text-ink">{policy.code}</span>
            <ActiveBadge active={policy.is_active} />
            <span>Updated {formatDateTime(policy.updated_at)}</span>
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

      {searchParams.get("created") === "1" && !editing ? (
        <p role="status" className="mb-4 text-sm text-success">
          Retention policy created.
        </p>
      ) : null}
      <ActionMessages
        error={retireOpen ? null : action.error}
        notice={action.notice}
        className="mb-4"
      />

      {editing ? (
        <RetentionPolicyEditor
          key={policy.updated_at}
          item={policy}
          onDone={(saved) => {
            setEditing(false);
            if (saved) action.setNotice("Retention policy updated.");
          }}
        />
      ) : (
        <>
          <p className="mb-5 max-w-3xl border-l-2 border-border-strong pl-3 text-sm leading-6 text-muted">
            {RETENTION_BOUNDARY_NOTE}
          </p>
          <div className="max-w-4xl divide-y divide-border border-y border-border">
            <DetailSection title="What records does this cover?">
              <PlainTextBlock text={policy.scope_summary} />
            </DetailSection>
            <DetailSection title="When does the retention period start?">
              <PlainTextBlock text={policy.retention_trigger_summary} />
            </DetailSection>
            <DetailSection title="How long are records kept?">
              <PlainTextBlock text={policy.retention_period_summary} />
            </DetailSection>
            <DetailSection title="What happens after the retention period?">
              <PlainTextBlock text={policy.disposition_summary} />
            </DetailSection>
            <DetailSection title="Policy reference">
              {policy.policy_reference ? (
                <p className="break-words text-sm text-ink">{policy.policy_reference}</p>
              ) : (
                <p className="text-sm text-muted">None recorded.</p>
              )}
            </DetailSection>
            <DetailSection title="Dates">
              <dl className="grid max-w-3xl gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-semibold text-muted">Effective date</dt>
                  <dd className="mt-1 text-sm text-ink">
                    {policy.effective_on ? (
                      formatDateOnly(policy.effective_on)
                    ) : (
                      <span className="text-muted">Not set</span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-muted">Review</dt>
                  <dd className="mt-1 text-sm text-ink">
                    <ReviewDueText value={policy.review_due_on} />
                  </dd>
                </div>
              </dl>
            </DetailSection>
          </div>
        </>
      )}

      <PrivacyConfirmDialog
        open={retireOpen}
        title="Retire this retention policy?"
        description={
          <p>
            Retired policies remain in governance history and cannot be assigned to
            new active Processing Activities.
          </p>
        }
        confirmLabel="Retire retention policy"
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

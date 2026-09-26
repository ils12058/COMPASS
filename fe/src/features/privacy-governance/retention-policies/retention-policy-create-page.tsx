"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  ActionMessages,
  PrivacyPageHeader,
  secondaryLinkClass,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  emptyRetentionValues,
  retentionCreateRequest,
  retentionFieldLabels,
  RetentionPolicyForm,
  type RetentionFormValues,
} from "@/features/privacy-governance/retention-policies/retention-policy-form";
import {
  getPrivacyGovernanceListRetentionPoliciesQueryKey,
  usePrivacyGovernanceCreateRetentionPolicy,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

export function RetentionPolicyCreatePage() {
  const { canManage } = usePrivacyAccess();
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = usePrivacyGovernanceCreateRetentionPolicy();
  const action = usePrivacyAction(retentionFieldLabels);

  if (!canManage) {
    return (
      <WorkspaceUnavailable title="Retention policy creation unavailable">
        Your current access does not include managing Privacy Governance records.
      </WorkspaceUnavailable>
    );
  }

  async function submit(values: RetentionFormValues) {
    const result = await action.run(
      () => create.mutateAsync({ data: retentionCreateRequest(values) }),
      "The retention policy could not be created.",
    );
    if (!result) return;
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceListRetentionPoliciesQueryKey(),
    });
    router.push(`/portal/privacy/retention-policies/${result.data.id}?created=1`);
  }

  return (
    <section>
      <PrivacyPageHeader
        title="Create retention policy"
        backHref="/portal/privacy/retention-policies"
        backLabel="Retention Policies"
      />
      <RetentionPolicyForm
        mode="create"
        initial={emptyRetentionValues}
        pending={create.isPending}
        submitLabel="Create retention policy"
        pendingLabel="Creating…"
        messages={<ActionMessages error={action.error} notice={action.notice} />}
        cancel={
          <Link href="/portal/privacy/retention-policies" className={secondaryLinkClass}>
            Cancel
          </Link>
        }
        onSubmit={(values) => void submit(values)}
      />
      {action.stepUpDialog}
    </section>
  );
}

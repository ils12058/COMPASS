"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import {
  ActionMessages,
  PrivacyPageHeader,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  emptyProcessingActivityValues,
  ProcessingActivityForm,
  processingActivityCreateRequest,
  processingActivityFieldLabels,
  type ProcessingActivityFormValues,
} from "@/features/privacy-governance/processing-activities/processing-activity-form";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  getPrivacyGovernanceListProcessingActivitiesQueryKey,
  usePrivacyGovernanceCreateProcessingActivity,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

export function ProcessingActivityCreatePage() {
  const { canManage } = usePrivacyAccess();
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = usePrivacyGovernanceCreateProcessingActivity();
  const action = usePrivacyAction(processingActivityFieldLabels);

  if (!canManage) {
    return (
      <WorkspaceUnavailable title="Processing activity creation unavailable">
        Your current access does not include managing Privacy Governance records.
      </WorkspaceUnavailable>
    );
  }

  async function submit(values: ProcessingActivityFormValues) {
    const result = await action.run(
      () => create.mutateAsync({ data: processingActivityCreateRequest(values) }),
      "The processing activity could not be created.",
    );
    if (!result) return;
    void queryClient.invalidateQueries({
      queryKey: getPrivacyGovernanceListProcessingActivitiesQueryKey(),
    });
    router.push(`/portal/privacy/processing-activities/${result.data.id}?created=1`);
  }

  return (
    <section>
      <PrivacyPageHeader
        title="Create processing activity"
        backHref="/portal/privacy/processing-activities"
        backLabel="Processing Activities"
      />
      <ProcessingActivityForm
        mode="create"
        initial={emptyProcessingActivityValues}
        currentPolicy={null}
        pending={create.isPending}
        submitLabel="Create processing activity"
        pendingLabel="Creating…"
        cancelHref="/portal/privacy/processing-activities"
        messages={<ActionMessages error={action.error} notice={action.notice} />}
        onSubmit={(values) => void submit(values)}
      />
      {action.stepUpDialog}
    </section>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  emptyIncidentValues,
  incidentCreateRequest,
  incidentFieldLabels,
  IncidentForm,
  type IncidentFormValues,
} from "@/features/privacy-governance/incidents/incident-form";
import {
  ActionMessages,
  invalidatePrivacyRecords,
  PrivacyPageHeader,
  privacyPaths,
  secondaryLinkClass,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import { getOverviewGetSummaryQueryKey } from "@/lib/api/generated/overview/overview";
import { usePrivacyGovernanceCreateIncident } from "@/lib/api/generated/privacy-governance/privacy-governance";

export function IncidentCreatePage() {
  const { canManage } = usePrivacyAccess();
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = usePrivacyGovernanceCreateIncident();
  const action = usePrivacyAction(incidentFieldLabels);

  if (!canManage) {
    return (
      <WorkspaceUnavailable title="Incident recording unavailable">
        Your current access does not include managing Privacy Governance records.
      </WorkspaceUnavailable>
    );
  }

  async function submit(values: IncidentFormValues) {
    const request = incidentCreateRequest(values);
    if (!request.ok) {
      action.setNotice(null);
      action.setError(request.error);
      return;
    }
    const result = await action.run(
      () => create.mutateAsync({ data: request.value }),
      "The privacy incident could not be recorded.",
    );
    if (!result) return;
    void invalidatePrivacyRecords(queryClient, privacyPaths.incidents);
    void queryClient.invalidateQueries({ queryKey: getOverviewGetSummaryQueryKey() });
    router.push(`/portal/privacy/incidents/${result.data.id}?created=1`);
  }

  return (
    <section>
      <PrivacyPageHeader
        title="Record privacy incident"
        backHref="/portal/privacy/incidents"
        backLabel="Privacy Incidents"
      />
      <IncidentForm
        initial={emptyIncidentValues}
        pending={create.isPending}
        submitLabel="Record privacy incident"
        pendingLabel="Recording…"
        messages={<ActionMessages error={action.error} notice={action.notice} />}
        cancel={
          <Link href="/portal/privacy/incidents" className={secondaryLinkClass}>
            Cancel
          </Link>
        }
        onSubmit={(values) => void submit(values)}
      />
      {action.stepUpDialog}
    </section>
  );
}

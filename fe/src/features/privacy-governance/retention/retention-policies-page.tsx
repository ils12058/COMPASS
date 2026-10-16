"use client";

import { Panel, PanelHeader } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { canViewRetention } from "@/features/privacy-governance/privacy-governance-access";
import { formatLongDate } from "@/features/privacy-governance/privacy-governance-presentation";
import {
  DetailValue,
  PrivacyBadge,
  PrivacyListSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
} from "@/features/privacy-governance/privacy-governance-shared";
import { RetentionHelp } from "@/features/privacy-governance/retention/retention-help";
import { usePrivacyGovernanceListRetentionPolicies } from "@/lib/api/generated/privacy-governance/privacy-governance";
import type { RetentionPolicyEntryResponse } from "@/lib/api/generated/model";

export const NOT_ADOPTED_COPY = "No adopted retention policy has been recorded in COMPASS for this category.";

// Read-only oversight of the code-owned register (ADR-115). Nothing here creates, edits, approves,
// or schedules anything: a policy changes only through institutional approval and a reviewed
// release, and COMPASS performs no records disposition.
export function RetentionPoliciesPage() {
  const { user } = usePortalSession();
  const canView = canViewRetention(user);
  const query = usePrivacyGovernanceListRetentionPolicies({ query: { enabled: canView, retry: false } });

  if (!canView)
    return (
      <WorkspaceUnavailable title="Retention Policies unavailable">
        This account can’t view retention policy oversight.
      </WorkspaceUnavailable>
    );

  const items = safeQueryData(query)?.data.items;

  return (
    <section>
      <PrivacyPageHeader
        title="Retention Policies"
        description="View the retention policy status recorded in COMPASS. Policy changes are governed through institutional approval and reviewed system updates."
        help={<RetentionHelp />}
      />
      {query.isError && items ? (
        <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} />
      ) : null}
      {query.isError && !items ? (
        <PrivacyQueryError
          error={query.error}
          fallback="Retention policies could not be loaded."
          onRetry={() => void query.refetch()}
        />
      ) : (
        <Panel aria-labelledby="retention-policies-heading">
          <PanelHeader title="Record categories" titleId="retention-policies-heading" />
          {!items ? (
            <PrivacyListSkeleton rows={3} label="Loading retention policies…" framed={false} />
          ) : (
            <ul className="divide-y divide-brand-line">
              {items.map((item) => (
                <RetentionPolicyRow key={item.category_code} item={item} />
              ))}
            </ul>
          )}
          <p className="border-t border-brand-line px-4 py-3 text-sm leading-6 text-muted sm:px-5">
            COMPASS doesn’t delete or anonymize records under these policies. Records disposition
            goes through the University’s authorized process outside COMPASS.
          </p>
        </Panel>
      )}
    </section>
  );
}

function RetentionPolicyRow({ item }: { item: RetentionPolicyEntryResponse }) {
  const headingId = `retention-policy-${item.category_code.toLowerCase()}`;
  const adopted = item.adoption_status === "ADOPTED";
  return (
    <li aria-labelledby={headingId} className="px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h3 id={headingId} className="font-heading text-base font-semibold text-ink">
          {item.category_label}
        </h3>
        <PrivacyBadge tone={adopted ? "success" : "neutral"}>
          {adopted ? "Adopted" : "Not adopted"}
        </PrivacyBadge>
      </div>
      {adopted ? (
        <dl className="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-3">
          <DetailValue label="Retention period">{item.retention_period}</DetailValue>
          <DetailValue label="Policy reference">{item.policy_reference}</DetailValue>
          <DetailValue label="Effective date">
            {item.effective_date ? formatLongDate(item.effective_date) : null}
          </DetailValue>
        </dl>
      ) : (
        <p className="mt-1 text-sm leading-6 text-muted">{NOT_ADOPTED_COPY}</p>
      )}
    </li>
  );
}

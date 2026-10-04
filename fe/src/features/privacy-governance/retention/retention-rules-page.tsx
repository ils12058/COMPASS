"use client";

import Link from "next/link";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { useState } from "react";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { usePrivacyGovernanceListRetentionRules } from "@/lib/api/generated/privacy-governance/privacy-governance";
import {
  PrivacyPageHeader,
  PrivacyListSkeleton,
  PrivacyQueryError,
  primaryLinkClass,
  textLinkClass,
} from "../privacy-governance-shared";
import { categoryLabels, useRetentionAccess } from "./retention-shared";

export function RetentionRulesPage() {
  const { canView, canManage } = useRetentionAccess();
  const [page, setPage] = useState(1);
  const rules = usePrivacyGovernanceListRetentionRules(
    { page, page_size: 20 },
    { query: { enabled: canView, retry: false } },
  );
  if (!canView)
    return (
      <WorkspaceUnavailable title="Retention rules unavailable">
        This account cannot view retention governance.
      </WorkspaceUnavailable>
    );
  const result = safeQueryData(rules)?.data;
  return (
    <section>
      <PrivacyPageHeader
        title="Retention rules"
        backHref="/portal/privacy/retention"
        backLabel="Retention & Disposition"
        action={
          canManage ? (
            <Link
              href="/portal/privacy/retention/rules/new"
              className={primaryLinkClass}
            >
              Create draft rule
            </Link>
          ) : null
        }
      />
      <Panel>
        <PanelHeader
          title="Institutional rules"
          description="Use an approved institutional policy reference and duration. COMPASS provides no default retention period."
        />
        {rules.isPending ? (
          <PrivacyListSkeleton
            label="Loading retention rules…"
            framed={false}
          />
        ) : !result ? (
          <PanelMessage>
            <PrivacyQueryError
              error={rules.error}
              fallback="Retention rules could not be loaded."
              onRetry={() => void rules.refetch()}
            />
          </PanelMessage>
        ) : (
          <>
            {rules.isError ? (
              <RefreshFailureNotice
                onRetry={() => void rules.refetch()}
                retrying={rules.isFetching}
              />
            ) : null}
            {result.items.length ? (
              <ul className="divide-y divide-border">
                {result.items.map((rule) => (
                  <li key={rule.id} className="px-4 py-4 sm:px-5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link
                        href={`/portal/privacy/retention/rules/${rule.id}`}
                        className={textLinkClass}
                      >
                        {rule.label}
                      </Link>
                      <span className="text-sm text-muted">
                        {rule.status === "DRAFT"
                          ? "Draft"
                          : rule.status === "ACTIVE"
                            ? "Active"
                            : "Retired"}
                      </span>
                    </div>
                    <p className="mt-1 text-sm">
                      {categoryLabels[rule.category]} · {rule.duration_days}{" "}
                      elapsed days · {rule.code}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <PanelMessage>
                No retention rules. Create a draft only from an approved
                institutional policy.
              </PanelMessage>
            )}
            <CanonicalPagination
              page={result.page}
              hasNext={result.has_next}
              onPageChange={setPage}
              label="Retention rule pages"
            />
          </>
        )}
      </Panel>
    </section>
  );
}

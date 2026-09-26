"use client";

import { keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  ActiveBadge,
  EmptyListState,
  LifecycleFilter,
  lifecycleFilterFrom,
  lifecycleParams,
  PRIVACY_PAGE_SIZE,
  PrivacyListSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
  primaryLinkClass,
  recordLinkClass,
  RefreshingNotice,
  tableCellClass,
  tableHeadClass,
  tableHeaderCellClass,
  tableRowHeaderClass,
  useListSearchParams,
  usePrivacyAccess,
} from "@/features/privacy-governance/privacy-governance-shared";
import type { ProcessingActivityResponse } from "@/lib/api/generated/model";
import { usePrivacyGovernanceListProcessingActivities } from "@/lib/api/generated/privacy-governance/privacy-governance";

function RetentionCell({ item }: { item: ProcessingActivityResponse }) {
  if (item.retention_policy) {
    return (
      <span>
        {item.retention_policy.name}
        {item.retention_policy.is_active ? null : (
          <span className="text-muted"> (retired)</span>
        )}
      </span>
    );
  }
  if (item.retention_policy_reference) {
    return (
      <span className="text-muted">
        External reference: {item.retention_policy_reference}
      </span>
    );
  }
  return <span className="text-muted">Not assigned</span>;
}

export function ProcessingActivitiesPage() {
  const { canManage } = usePrivacyAccess();
  const { searchParams, page, update, setPage } = useListSearchParams();
  const lifecycle = lifecycleFilterFrom(searchParams.get("status"));
  const query = usePrivacyGovernanceListProcessingActivities(
    { page, page_size: PRIVACY_PAGE_SIZE, ...lifecycleParams(lifecycle) },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const result = query.data?.data;
  const createLink = canManage ? (
    <Link href="/portal/privacy/processing-activities/new" className={primaryLinkClass}>
      Create processing activity
    </Link>
  ) : null;

  return (
    <section>
      <PrivacyPageHeader
        title="Processing Activities"
        description="Document how COMPASS uses, protects, and retains categories of personal information."
        action={createLink}
      />

      <LifecycleFilter
        id="processing-activity-status"
        value={lifecycle}
        onChange={(value) => update({ status: value === "active" ? null : value })}
      />

      {query.isPending ? (
        <div className="mt-5">
          <PrivacyListSkeleton label="Loading processing activities…" />
        </div>
      ) : query.isError && !result ? (
        <div className="mt-5">
          <PrivacyQueryError
            error={query.error}
            fallback="Processing activities could not be loaded."
            onRetry={() => void query.refetch()}
          />
        </div>
      ) : result && result.items.length === 0 ? (
        lifecycle === "all" && page === 1 ? (
          <EmptyListState
            message="No processing activities have been recorded."
            action={createLink}
          />
        ) : (
          <EmptyListState
            message={
              lifecycle === "retired"
                ? "No retired processing activities."
                : lifecycle === "active"
                  ? "No active processing activities."
                  : "No processing activities on this page."
            }
            action={
              <Button variant="secondary" onClick={() => update({ status: "all" })}>
                Show all processing activities
              </Button>
            }
          />
        )
      ) : result ? (
        <>
          <RefreshingNotice
            show={query.isFetching}
            label="Refreshing processing activities…"
          />
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
              <caption className="sr-only">Processing Activities</caption>
              <thead className={tableHeadClass}>
                <tr>
                  <th scope="col" className={tableHeaderCellClass}>
                    Activity
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Retention Policy
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {result.items.map((item) => (
                  <tr key={item.id}>
                    <th scope="row" className={tableRowHeaderClass}>
                      <Link
                        href={`/portal/privacy/processing-activities/${item.id}`}
                        className={recordLinkClass}
                      >
                        {item.name}
                      </Link>
                      <span className="mt-1 block break-all font-mono text-xs text-muted">
                        {item.code}
                      </span>
                    </th>
                    <td className={tableCellClass + " text-ink"}>
                      <RetentionCell item={item} />
                    </td>
                    <td className={tableCellClass}>
                      <ActiveBadge active={item.is_active} />
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
              label="Processing Activity pages"
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}

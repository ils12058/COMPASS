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
import { reviewDuePassed } from "@/features/privacy-governance/retention-policies/retention-policy-form";
import { formatDateOnly } from "@/lib/date-time";
import { usePrivacyGovernanceListRetentionPolicies } from "@/lib/api/generated/privacy-governance/privacy-governance";

export function RetentionPoliciesPage() {
  const { canManage } = usePrivacyAccess();
  const { searchParams, page, update, setPage } = useListSearchParams();
  const lifecycle = lifecycleFilterFrom(searchParams.get("status"));
  const query = usePrivacyGovernanceListRetentionPolicies(
    { page, page_size: PRIVACY_PAGE_SIZE, ...lifecycleParams(lifecycle) },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const result = query.data?.data;
  const createLink = canManage ? (
    <Link href="/portal/privacy/retention-policies/new" className={primaryLinkClass}>
      Create retention policy
    </Link>
  ) : null;

  return (
    <section>
      <PrivacyPageHeader
        title="Retention Policies"
        description="Document approved retention guidance used by COMPASS. These records do not automatically delete data."
        action={createLink}
      />

      <LifecycleFilter
        id="retention-policy-status"
        value={lifecycle}
        onChange={(value) => update({ status: value === "active" ? null : value })}
      />

      {query.isPending ? (
        <div className="mt-5">
          <PrivacyListSkeleton label="Loading retention policies…" />
        </div>
      ) : query.isError && !result ? (
        <div className="mt-5">
          <PrivacyQueryError
            error={query.error}
            fallback="Retention policies could not be loaded."
            onRetry={() => void query.refetch()}
          />
        </div>
      ) : result && result.items.length === 0 ? (
        lifecycle === "all" && page === 1 ? (
          <EmptyListState
            message="No retention policies have been recorded."
            action={createLink}
          />
        ) : (
          <EmptyListState
            message={
              lifecycle === "retired"
                ? "No retired retention policies."
                : lifecycle === "active"
                  ? "No active retention policies."
                  : "No retention policies on this page."
            }
            action={
              <Button variant="secondary" onClick={() => update({ status: "all" })}>
                Show all retention policies
              </Button>
            }
          />
        )
      ) : result ? (
        <>
          <RefreshingNotice show={query.isFetching} label="Refreshing retention policies…" />
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
              <caption className="sr-only">Retention Policies</caption>
              <thead className={tableHeadClass}>
                <tr>
                  <th scope="col" className={tableHeaderCellClass}>
                    Policy
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Records covered
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Review due
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {result.items.map((policy) => (
                  <tr key={policy.id}>
                    <th scope="row" className={tableRowHeaderClass + " min-w-48"}>
                      <Link
                        href={`/portal/privacy/retention-policies/${policy.id}`}
                        className={recordLinkClass}
                      >
                        {policy.name}
                      </Link>
                      <span className="mt-1 block break-all font-mono text-xs text-muted">
                        {policy.code}
                      </span>
                    </th>
                    <td className={tableCellClass + " max-w-md text-ink"}>
                      <p className="line-clamp-2 break-words">{policy.scope_summary}</p>
                    </td>
                    <td className={tableCellClass + " whitespace-nowrap text-ink"}>
                      {policy.review_due_on ? (
                        <>
                          {formatDateOnly(policy.review_due_on)}
                          {reviewDuePassed(policy.review_due_on) ? (
                            <span className="mt-1 block text-xs text-warning">
                              Review date passed
                            </span>
                          ) : null}
                        </>
                      ) : (
                        <span className="text-muted">Not set</span>
                      )}
                    </td>
                    <td className={tableCellClass}>
                      <ActiveBadge active={policy.is_active} />
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
              label="Retention Policy pages"
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}

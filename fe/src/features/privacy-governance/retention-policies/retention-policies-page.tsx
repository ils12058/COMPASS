"use client";

import { keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  privacySelectClass,
  recordLinkClass,
  RefreshingNotice,
  tableCellClass,
  tableHeadClass,
  tableHeaderCellClass,
  tableRowHeaderClass,
  useListSearchParams,
  usePrivacyAccess,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  retentionRecordCategoryLabels,
  retentionRecordCategoryOrder,
} from "@/features/privacy-governance/privacy-governance-presentation";
import { reviewDuePassed } from "@/features/privacy-governance/retention-policies/retention-policy-form";
import { usePrivacyGovernanceListRetentionPolicies } from "@/lib/api/generated/privacy-governance/privacy-governance";
import type { RetentionRecordCategoryValue } from "@/lib/api/generated/model";
import { formatDateOnly } from "@/lib/date-time";

function recordCategoryFrom(value: string | null): RetentionRecordCategoryValue | undefined {
  return retentionRecordCategoryOrder.find((category) => category === value);
}

export function RetentionPoliciesPage() {
  const { canManage } = usePrivacyAccess();
  const { searchParams, page, update, setPage } = useListSearchParams();
  const lifecycle = lifecycleFilterFrom(searchParams.get("status"));
  const search = searchParams.get("search") ?? "";
  const recordCategory = recordCategoryFrom(searchParams.get("record_category"));
  const query = usePrivacyGovernanceListRetentionPolicies(
    {
      page,
      page_size: PRIVACY_PAGE_SIZE,
      ...lifecycleParams(lifecycle),
      search: search || undefined,
      record_category: recordCategory,
    },
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
        description="Maintain institution-approved lifecycle guidance mapped to COMPASS record categories. These policies do not automatically delete, archive, or anonymize records."
        action={createLink}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[minmax(14rem,1fr)_14rem_18rem]">
        <div className="grid gap-2">
          <label htmlFor="retention-policy-search" className="text-sm font-medium text-ink">
            Search
          </label>
          <Input
            id="retention-policy-search"
            value={search}
            placeholder="Policy code or name"
            onChange={(event) => update({ search: event.target.value || null })}
          />
        </div>
        <LifecycleFilter
          id="retention-policy-status"
          value={lifecycle}
          onChange={(value) => update({ status: value === "active" ? null : value })}
        />
        <div className="grid gap-2">
          <label htmlFor="retention-policy-category" className="text-sm font-medium text-ink">
            Record category
          </label>
          <select
            id="retention-policy-category"
            className={privacySelectClass}
            value={recordCategory ?? ""}
            onChange={(event) =>
              update({ record_category: event.target.value || null })
            }
          >
            <option value="">All record categories</option>
            {retentionRecordCategoryOrder.map((category) => (
              <option key={category} value={category}>
                {retentionRecordCategoryLabels[category]}
              </option>
            ))}
          </select>
        </div>
      </div>

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
        lifecycle === "all" && !search && !recordCategory && page === 1 ? (
          <EmptyListState
            message="No retention policies have been recorded."
            action={createLink}
          />
        ) : (
          <EmptyListState
            message="No retention policies match the current filters."
            action={
              <Button
                variant="secondary"
                onClick={() =>
                  update({ status: "all", search: null, record_category: null })
                }
              >
                Clear filters
              </Button>
            }
          />
        )
      ) : result ? (
        <>
          <RefreshingNotice show={query.isFetching} label="Refreshing retention policies…" />
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[52rem] border-collapse text-left text-sm">
              <caption className="sr-only">Retention Policies</caption>
              <thead className={tableHeadClass}>
                <tr>
                  <th scope="col" className={tableHeaderCellClass}>
                    Policy
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    COMPASS record categories
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Scope
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
                    <td className={tableCellClass + " min-w-52"}>
                      {policy.record_categories.length > 0 ? (
                        <ul className="space-y-1 text-sm text-ink">
                          {policy.record_categories.map((category) => (
                            <li key={category}>{retentionRecordCategoryLabels[category]}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-muted">
                          No COMPASS record category has been assigned yet.
                        </span>
                      )}
                    </td>
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

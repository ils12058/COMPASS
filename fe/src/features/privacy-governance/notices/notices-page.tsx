"use client";

import { keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";

import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  ActiveBadge,
  EmptyListState,
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
import { formatDateTime } from "@/lib/date-time";
import { usePrivacyGovernanceListNotices } from "@/lib/api/generated/privacy-governance/privacy-governance";

// Notice families do not carry their current revision, so this index stays
// family-level; revisions load only on the selected notice.
export function NoticesPage() {
  const { canManage } = usePrivacyAccess();
  const { page, setPage } = useListSearchParams();
  const query = usePrivacyGovernanceListNotices(
    { page, page_size: PRIVACY_PAGE_SIZE },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const result = query.data?.data;
  const createLink = canManage ? (
    <Link href="/portal/privacy/notices/new" className={primaryLinkClass}>
      Create privacy notice
    </Link>
  ) : null;

  return (
    <section>
      <PrivacyPageHeader
        title="Privacy Notices"
        description="Manage notices shown to people using COMPASS."
        action={createLink}
      />

      {query.isPending ? (
        <PrivacyListSkeleton label="Loading privacy notices…" />
      ) : query.isError && !result ? (
        <PrivacyQueryError
          error={query.error}
          fallback="Privacy notices could not be loaded."
          onRetry={() => void query.refetch()}
        />
      ) : result && result.items.length === 0 ? (
        <EmptyListState
          message={
            page === 1
              ? "No privacy notices have been created."
              : "No privacy notices on this page."
          }
          action={page === 1 ? createLink : null}
        />
      ) : result ? (
        <>
          <RefreshingNotice show={query.isFetching} label="Refreshing privacy notices…" />
          <div className="overflow-x-auto border-y border-border">
            <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
              <caption className="sr-only">Privacy Notices</caption>
              <thead className={tableHeadClass}>
                <tr>
                  <th scope="col" className={tableHeaderCellClass}>
                    Notice
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Code
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Status
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Updated
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {result.items.map((notice) => (
                  <tr key={notice.id}>
                    <th scope="row" className={tableRowHeaderClass}>
                      <Link
                        href={`/portal/privacy/notices/${notice.id}`}
                        className={recordLinkClass}
                      >
                        {notice.name}
                      </Link>
                    </th>
                    <td className={tableCellClass + " break-all font-mono text-xs text-ink"}>
                      {notice.code}
                    </td>
                    <td className={tableCellClass}>
                      <ActiveBadge active={notice.is_active} />
                    </td>
                    <td className={tableCellClass + " text-ink"}>
                      {formatDateTime(notice.updated_at)}
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
              label="Privacy Notice pages"
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}

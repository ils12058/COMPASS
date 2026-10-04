"use client";

import { keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";

import { dataTable } from "@/components/ui/data-table";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import {
  ActiveBadge,
  EmptyListState,
  PRIVACY_PAGE_SIZE,
  PrivacyListSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
  primaryLinkClass,
  recordLinkClass,
  useListSearchParams,
  usePrivacyAccess,
} from "@/features/privacy-governance/privacy-governance-shared";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
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
  const result = query.isError && !canShowLastKnownData(query) ? undefined : query.data?.data;
  const createLink = canManage ? (
    <Link href="/portal/privacy/notices/new" className={primaryLinkClass}>
      Create privacy notice
    </Link>
  ) : null;

  return (
    <section>
      <PrivacyPageHeader
        title="Privacy Notices"
        action={createLink}
      />
      {query.isError && result ? <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}

      {query.isError && !result ? (
        <PrivacyQueryError
          error={query.error}
          fallback="Privacy notices could not be loaded."
          onRetry={() => void query.refetch()}
        />
      ) : (
        <Panel aria-labelledby="privacy-notices-results-heading">
          <PanelHeader
            title="Notice families"
            titleId="privacy-notices-results-heading"
            context={
              query.isFetching && !query.isPending
                ? "Refreshing privacy notices…"
                : result && !query.isError
                  ? describeResultPage({
                      count: result.items.length,
                      page: result.page,
                      hasNext: result.has_next,
                      noun: { one: "notice", other: "notices" },
                      filtered: false,
                    })
                  : null
            }
          />
          {query.isPending ? (
            <PrivacyListSkeleton label="Loading privacy notices…" framed={false} />
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
            <div className={dataTable.scroll}>
              <table className={`${dataTable.table} min-w-[36rem]`}>
                <caption className="sr-only">Privacy Notices</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>
                      Notice
                    </th>
                    <th scope="col" className={dataTable.headerCell}>
                      Code
                    </th>
                    <th scope="col" className={dataTable.headerCell}>
                      Status
                    </th>
                    <th scope="col" className={dataTable.headerCell}>
                      Updated
                    </th>
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {result.items.map((notice) => (
                    <tr key={notice.id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-normal`}>
                        <Link
                          href={`/portal/privacy/notices/${notice.id}`}
                          className={recordLinkClass}
                        >
                          {notice.name}
                        </Link>
                      </th>
                      <td className={`${dataTable.cell} break-all font-mono text-xs text-ink`}>
                        {notice.code}
                      </td>
                      <td className={dataTable.cell}>
                        <ActiveBadge active={notice.is_active} />
                      </td>
                      <td className={`${dataTable.cell} text-ink`}>
                        {formatInstitutionalDateTime(notice.updated_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {result ? (
            <CanonicalPagination
              className="border-brand-line px-4 py-3 sm:px-5"
              page={result.page}
              hasNext={result.has_next}
              onPageChange={setPage}
              label="Privacy Notice pages"
            />
          ) : null}
        </Panel>
      )}
    </section>
  );
}

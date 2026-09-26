"use client";

import { keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  incidentStatusLabels,
  notificationAssessmentLabels,
} from "@/features/privacy-governance/privacy-governance-presentation";
import {
  EmptyListState,
  IncidentStatusBadge,
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
import { formatDateTime } from "@/lib/date-time";
import { IncidentStatusValue } from "@/lib/api/generated/model";
import { usePrivacyGovernanceListIncidents } from "@/lib/api/generated/privacy-governance/privacy-governance";

function statusFilterFrom(value: string | null): IncidentStatusValue | undefined {
  return Object.values(IncidentStatusValue).find((status) => status === value);
}

export function IncidentsPage() {
  const { canManage } = usePrivacyAccess();
  const { searchParams, page, update, setPage } = useListSearchParams();
  const status = statusFilterFrom(searchParams.get("status"));
  const query = usePrivacyGovernanceListIncidents(
    { page, page_size: PRIVACY_PAGE_SIZE, ...(status ? { status } : {}) },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const result = query.data?.data;
  const recordLink = canManage ? (
    <Link href="/portal/privacy/incidents/new" className={primaryLinkClass}>
      Record privacy incident
    </Link>
  ) : null;

  return (
    <section>
      <PrivacyPageHeader title="Privacy Incidents" action={recordLink} />

      <div className="grid max-w-56 gap-2">
        <label htmlFor="incident-status-filter" className="text-sm font-medium text-ink">
          Status
        </label>
        <select
          id="incident-status-filter"
          className={privacySelectClass}
          value={status ?? ""}
          onChange={(event) => update({ status: statusFilterFrom(event.target.value) ?? null })}
        >
          <option value="">All</option>
          {Object.values(IncidentStatusValue).map((option) => (
            <option key={option} value={option}>
              {incidentStatusLabels[option]}
            </option>
          ))}
        </select>
      </div>

      {query.isPending ? (
        <div className="mt-5">
          <PrivacyListSkeleton label="Loading privacy incidents…" />
        </div>
      ) : query.isError && !result ? (
        <div className="mt-5">
          <PrivacyQueryError
            error={query.error}
            fallback="Privacy incidents could not be loaded."
            onRetry={() => void query.refetch()}
          />
        </div>
      ) : result && result.items.length === 0 ? (
        status ? (
          <EmptyListState
            message={`No ${incidentStatusLabels[status].toLowerCase()} privacy incidents.`}
            action={
              <Button variant="secondary" onClick={() => update({ status: null })}>
                Show all incidents
              </Button>
            }
          />
        ) : (
          <EmptyListState
            message={
              page === 1
                ? "No privacy incidents have been recorded."
                : "No privacy incidents on this page."
            }
          />
        )
      ) : result ? (
        <>
          <RefreshingNotice show={query.isFetching} label="Refreshing privacy incidents…" />
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[48rem] border-collapse text-left text-sm">
              <caption className="sr-only">Privacy Incidents</caption>
              <thead className={tableHeadClass}>
                <tr>
                  <th scope="col" className={tableHeaderCellClass}>
                    Reference
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Incident
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Status
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Discovered
                  </th>
                  <th scope="col" className={tableHeaderCellClass}>
                    Notification assessment
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {result.items.map((incident) => (
                  <tr key={incident.id}>
                    <th scope="row" className={tableRowHeaderClass + " whitespace-nowrap"}>
                      <Link
                        href={`/portal/privacy/incidents/${incident.id}`}
                        className={recordLinkClass + " font-mono"}
                      >
                        {incident.reference_code}
                      </Link>
                    </th>
                    <td className={tableCellClass + " max-w-sm break-words text-ink"}>
                      {incident.title}
                    </td>
                    <td className={tableCellClass}>
                      <IncidentStatusBadge status={incident.status} />
                    </td>
                    <td className={tableCellClass + " whitespace-nowrap text-ink"}>
                      {formatDateTime(incident.discovered_at)}
                    </td>
                    <td className={tableCellClass + " text-ink"}>
                      {notificationAssessmentLabels[incident.notification_assessment]}
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
              label="Privacy Incident pages"
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}

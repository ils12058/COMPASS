"use client";

import { ListChecks } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { PageActionLink } from "@/components/ui/page-action";
import {
  Panel,
  PanelBody,
  PanelHeader,
  PanelMessage,
} from "@/components/ui/panel";
import {
  FloatingListTools,
  ListToolField,
} from "@/components/ui/floating-list-tools";
import { FilterField } from "@/components/ui/filter-toolbar";
import { Select } from "@/components/ui/select";
import { dataTable } from "@/components/ui/data-table";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import {
  PrivacyPageHeader,
  PrivacyListSkeleton,
  PrivacyQueryError,
  textLinkClass,
} from "../privacy-governance-shared";
import {
  usePrivacyGovernanceListDispositionCases,
  usePrivacyGovernanceRetentionSummary,
} from "@/lib/api/generated/privacy-governance/privacy-governance";
import { DispositionState, RetentionCategory } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import {
  categoryLabels,
  stateLabels,
  useRetentionAccess,
} from "./retention-shared";

export function RetentionPage() {
  const { canView } = useRetentionAccess();
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<RetentionCategory>();
  const [state, setState] = useState<DispositionState>();
  const summary = usePrivacyGovernanceRetentionSummary({
    query: {
      enabled: canView,
      retry: false,
      refetchInterval: 10000,
      refetchIntervalInBackground: false,
    },
  });
  const cases = usePrivacyGovernanceListDispositionCases(
    { page, page_size: 20, category, state },
    {
      query: {
        enabled: canView,
        retry: false,
        refetchInterval: 10000,
        refetchIntervalInBackground: false,
      },
    },
  );
  if (!canView)
    return (
      <WorkspaceUnavailable title="Retention & Disposition unavailable">
        This account cannot view retention governance.
      </WorkspaceUnavailable>
    );
  const counts = safeQueryData(summary)?.data;
  const result = safeQueryData(cases)?.data;
  return (
    <section>
      <PrivacyPageHeader
        title="Retention & Disposition"
        action={
          <PageActionLink
            href="/portal/privacy/retention/rules"
            icon={ListChecks}
            variant="secondary"
            label="Retention rules"
          />
        }
      />
      <Panel className="mb-5">
        <PanelHeader title="Current disposition" />
        {summary.isPending ? (
          <PrivacyListSkeleton
            rows={2}
            label="Loading disposition counts…"
            framed={false}
          />
        ) : !counts ? (
          <PanelMessage>
            <PrivacyQueryError
              error={summary.error}
              fallback="Disposition counts could not be loaded."
              onRetry={() => void summary.refetch()}
            />
          </PanelMessage>
        ) : (
          <>
            {summary.isError ? (
              <RefreshFailureNotice
                onRetry={() => void summary.refetch()}
                retrying={summary.isFetching}
              />
            ) : null}
            <PanelBody>
              <dl className="flex flex-wrap gap-x-8 gap-y-3 text-sm">
                {[
                  ["Needs review", counts.needs_review],
                  ["On hold", counts.on_hold],
                  ["Processing", counts.processing],
                  ["Completed in the last 30 days", counts.recently_completed],
                ].map(([label, count]) => (
                  <div key={label}>
                    <dt className="text-muted">{label}</dt>
                    <dd className="font-semibold">{count}</dd>
                  </div>
                ))}
              </dl>
            </PanelBody>
            <ul className="divide-y divide-border">
              {counts.categories.map((item) => (
                <li
                  key={item.category}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5"
                >
                  <div>
                    <p className="text-sm font-semibold">{item.label}</p>
                    <p className="text-sm text-muted">
                      {item.ready_count} ready · {item.held_count} on hold ·{" "}
                      {item.blocked_count} unresolved
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setCategory(item.category);
                      setState("READY");
                      setPage(1);
                    }}
                  >
                    Review {item.label}
                  </Button>
                </li>
              ))}
            </ul>
          </>
        )}
      </Panel>
      <Panel>
        <PanelHeader
          title="Disposition cases"
          description="Each approval authorizes one fixed record. Eligibility alone never authorizes disposition."
        />
        {cases.isPending ? (
          <PrivacyListSkeleton
            label="Loading disposition cases…"
            framed={false}
          />
        ) : !result ? (
          <PanelMessage>
            <PrivacyQueryError
              error={cases.error}
              fallback="Disposition cases could not be loaded."
              onRetry={() => void cases.refetch()}
            />
          </PanelMessage>
        ) : (
          <>
            {cases.isError ? (
              <RefreshFailureNotice
                onRetry={() => void cases.refetch()}
                retrying={cases.isFetching}
              />
            ) : null}
            {result.items.length === 0 ? (
              <PanelMessage>
                {category || state
                  ? "No cases match these filters."
                  : "No disposition cases. An active institutional retention rule is required before eligibility is discovered."}
              </PanelMessage>
            ) : (
              <div className={dataTable.scroll}>
                <table className={dataTable.table}>
                  <thead className={dataTable.head}>
                    <tr>
                      <th className={dataTable.headerCell}>Category / case</th>
                      <th className={dataTable.headerCell}>Rule</th>
                      <th className={dataTable.headerCell}>Eligible</th>
                      <th className={dataTable.headerCell}>State</th>
                    </tr>
                  </thead>
                  <tbody className={dataTable.body}>
                    {result.items.map((item) => (
                      <tr key={item.id} className={dataTable.row}>
                        <td className={dataTable.cell}>
                          <Link
                            href={`/portal/privacy/retention/cases/${item.id}`}
                            className={textLinkClass}
                          >
                            {categoryLabels[item.category]}
                          </Link>
                          <p className="mt-1 font-mono text-xs text-muted break-all">
                            {item.id}
                          </p>
                        </td>
                        <td className={dataTable.cell}>{item.rule_code}</td>
                        <td className={dataTable.cell}>
                          {formatInstitutionalDateTime(item.eligible_at)}
                        </td>
                        <td className={dataTable.cell}>
                          {stateLabels[item.state]}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <CanonicalPagination
              page={result.page}
              hasNext={result.has_next}
              onPageChange={setPage}
              label="Disposition case pages"
            />
          </>
        )}
      </Panel>
      <FloatingListTools
        filterCount={Number(Boolean(state))}
        filters={
          <>
            <FilterField label="State" htmlFor="case-state">
              <Select
                id="case-state"
                value={state ?? ""}
                onChange={(event) => {
                  setState(
                    Object.values(DispositionState).find(
                      (value) => value === event.target.value,
                    ),
                  );
                  setPage(1);
                }}
              >
                <option value="">All states</option>
                {Object.values(DispositionState).map((value) => (
                  <option key={value} value={value}>
                    {stateLabels[value]}
                  </option>
                ))}
              </Select>
            </FilterField>
          </>
        }
        label="Disposition case filters"
        compact
        clear={
          category || state ? (
            <Button
              variant="secondary"
              onClick={() => {
                setCategory(undefined);
                setState(undefined);
                setPage(1);
              }}
            >
              Clear filters
            </Button>
          ) : undefined
        }
      >
        <ListToolField label="Category" htmlFor="case-category">
          <Select
            id="case-category"
            value={category ?? ""}
            onChange={(event) => {
              setCategory(
                Object.values(RetentionCategory).find(
                  (value) => value === event.target.value,
                ),
              );
              setPage(1);
            }}
          >
            <option value="">All categories</option>
            {Object.values(RetentionCategory).map((value) => (
              <option key={value} value={value}>
                {categoryLabels[value]}
              </option>
            ))}
          </Select>
        </ListToolField>
      </FloatingListTools>
    </section>
  );
}

"use client";

import { keepPreviousData, useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ActivityFilterTools, activityTypeLabel, enumValue, useActivitySearchParams } from "@/features/activity/activity-filters";
import { activityErrorMessage } from "@/features/activity/activity-errors";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { activityCategoryLabels } from "@/features/privacy-governance/privacy-governance-presentation";
import {
  EmptyListState,
  PRIVACY_PAGE_SIZE,
  PrivacyListSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
} from "@/features/privacy-governance/privacy-governance-shared";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import {
  PrivacyActivityCategory,
  PrivacyActivityType,
  type PrivacyGovernanceExportActivityParams,
  type PrivacyActivityItemResponse,
} from "@/lib/api/generated/model";
import { getPrivacyGovernanceListActivityQueryKey, privacyGovernanceExportActivity, usePrivacyGovernanceListActivity } from "@/lib/api/generated/privacy-governance/privacy-governance";

const artifactLabels: Record<string, string> = {
  graduate_tracer: "Graduate Tracer",
  student_profiling: "Student Profiling",
  good_moral_certificate: "Good Moral certificate",
};

function artifactLabel(value: string): string {
  const known = artifactLabels[value];
  if (known) return known;
  const words = value.replaceAll("_", " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function categoryFrom(value: string | null): PrivacyActivityCategory | undefined {
  return Object.values(PrivacyActivityCategory).find((category) => category === value);
}

// Only the curated fields the API returns are shown. Identity is omitted when
// the backend suppresses it, rather than shown as an unknown person.
function ActivityItem({ item }: { item: PrivacyActivityItemResponse }) {
  return (
    <li className="px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="font-semibold text-ink">{item.title}</p>
        <time dateTime={item.occurred_at} className="text-xs text-muted">
          {formatInstitutionalDateTime(item.occurred_at)}
        </time>
      </div>
      <p className="mt-1 max-w-3xl break-words text-sm text-ink">{item.description}</p>
      <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <div>
          <dt className="inline">Category: </dt>
          <dd className="inline">{activityCategoryLabels[item.category]}</dd>
        </div>
        {item.actor_display_name ? (
          <div>
            <dt className="inline">By: </dt>
            <dd className="inline">{item.actor_display_name}</dd>
          </div>
        ) : null}
        {item.artifact_type ? (
          <div>
            <dt className="inline">Artifact: </dt>
            <dd className="inline">
              {artifactLabel(item.artifact_type)}
              {item.artifact_format ? ` (${item.artifact_format})` : null}
            </dd>
          </div>
        ) : null}
        {item.scope ? (
          <div className="max-w-full">
            <dt className="inline">Scope: </dt>
            <dd className="inline break-words">{item.scope}</dd>
          </div>
        ) : null}
        {item.resource_reference ? (
          <div className="max-w-full">
            <dt className="inline">Reference: </dt>
            <dd className="inline break-all font-mono">{item.resource_reference}</dd>
          </div>
        ) : null}
      </dl>
    </li>
  );
}

export function PrivacyActivityPage() {
  const { searchParams, page, update, setPage } = useActivitySearchParams();
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const canExport = user.capabilities.includes("privacy_governance.activity.export");
  const category = categoryFrom(searchParams.get("category"));
  const search = searchParams.get("search") || undefined;
  const event_type = enumValue(searchParams.get("event_type"), Object.values(PrivacyActivityType));
  const actor = searchParams.get("actor") || undefined;
  const date_from = searchParams.get("date_from") || undefined;
  const date_to = searchParams.get("date_to") || undefined;
  const criteria = { search, category, event_type, actor, date_from, date_to } satisfies PrivacyGovernanceExportActivityParams;
  const filtered = Object.values(criteria).some(Boolean);
  const clear = () => update(Object.fromEntries(Object.keys(criteria).map((key) => [key, null])));
  const query = usePrivacyGovernanceListActivity(
    { ...criteria, page, page_size: PRIVACY_PAGE_SIZE },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const result = query.isError && !canShowLastKnownData(query) ? undefined : query.data?.data;

  const exportCsv = useMutation({
    mutationFn: (params: PrivacyGovernanceExportActivityParams) => privacyGovernanceExportActivity(params),
    retry: false,
    onSuccess: (response) => {
      downloadBinaryResponse(response, "COMPASS-Privacy-Activity.csv");
      void queryClient.invalidateQueries({ queryKey: getPrivacyGovernanceListActivityQueryKey() });
    },
  });

  return (
    <section>
      <PrivacyPageHeader
        title="Privacy & Security Activity"
        description="A curated record of privacy-relevant events. It is not the full audit trail."
        action={canExport ? <Button variant="secondary" disabled={exportCsv.isPending || query.isFetching || query.isError || query.isPlaceholderData || !result} onClick={() => exportCsv.mutate(criteria)}>{exportCsv.isPending ? "Exporting CSV…" : "Export CSV"}</Button> : undefined}
      />

      {exportCsv.isError ? <PanelMessage tone="danger" role="alert">{activityErrorMessage(exportCsv.error, "Activity CSV could not be exported.")}</PanelMessage> : null}
      {query.isError && result ? <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}

      {query.isError && !result ? (
        <div>
          <PrivacyQueryError
            error={query.error}
            fallback={activityErrorMessage(query.error, "Privacy and security activity could not be loaded.")}
            onRetry={() => void query.refetch()}
          />
        </div>
      ) : (
        <Panel aria-labelledby="privacy-activity-results-heading">
          <PanelHeader
            title="Recorded events"
            titleId="privacy-activity-results-heading"
            context={
              query.isFetching && !query.isPending
                ? "Refreshing activity…"
                : result && !query.isError
                  ? describeResultPage({
                      count: result.items.length,
                      page: result.page,
                      hasNext: result.has_next,
                      noun: { one: "event", other: "events" },
                      filtered,
                    })
                  : null
            }
          />
          {query.isPending ? (
            <PrivacyListSkeleton label="Loading privacy and security activity…" framed={false} />
          ) : result && result.items.length === 0 ? (
            <EmptyListState message={filtered ? "No matching activity." : "No activity has been recorded yet."}
              action={filtered ? <Button variant="secondary" onClick={clear}>Clear filters</Button> : undefined} />
          ) : result ? (
            <ol className="divide-y divide-border">
              {result.items.map((item) => (
                <ActivityItem key={item.id} item={item} />
              ))}
            </ol>
          ) : null}
          {result ? (
            <CanonicalPagination
              className="border-brand-line px-4 py-3 sm:px-5"
              page={result.page}
              hasNext={result.has_next}
              disabled={query.isFetching}
              onPageChange={setPage}
              label="Activity pages"
            />
          ) : null}
        </Panel>
      )}
      <ActivityFilterTools key={JSON.stringify(criteria)} applied={criteria} onApply={update} fields={[
        { name: "category", label: "Category", options: Object.values(PrivacyActivityCategory).map((type) => ({ value: type, label: activityCategoryLabels[type] })) },
        { name: "event_type", label: "Event type", options: Object.values(PrivacyActivityType).map((type) => ({ value: type, label: activityTypeLabel(type) })) },
        { name: "actor", label: "Actor" },
        { name: "date_from", label: "Date from", type: "date" }, { name: "date_to", label: "Date to", type: "date" },
      ]} />
    </section>
  );
}

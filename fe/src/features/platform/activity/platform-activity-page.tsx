"use client";

import { keepPreviousData } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ActivityFilterTools, activityTypeLabel, enumValue, useActivitySearchParams } from "@/features/activity/activity-filters";
import { activityErrorMessage } from "@/features/activity/activity-errors";

import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import {
  PlatformPageHeader,
  PlatformQueryError,
  PlatformRowsSkeleton,
  PlatformTimestamp,
} from "@/features/platform/platform-presentation";
import { TechnicalActivityActorType, TechnicalActivityType } from "@/lib/api/generated/model";
import { usePlatformOperationsListActivity } from "@/lib/api/generated/platform-operations/platform-operations";

const PAGE_SIZE = 20;

const actorTypeLabels: Record<TechnicalActivityActorType, string> = {
  [TechnicalActivityActorType.USER]: "operator",
  [TechnicalActivityActorType.SYSTEM]: "system",
  [TechnicalActivityActorType.ANONYMOUS]: "anonymous",
};

function actorLabel(name: string | null, type: TechnicalActivityActorType): string {
  return name || actorTypeLabels[type];
}

export function PlatformActivityPage() {
  const { searchParams, page, update, setPage } = useActivitySearchParams();
  const search = searchParams.get("search") || undefined;
  const event_type = enumValue(searchParams.get("event_type"), Object.values(TechnicalActivityType));
  const operator = searchParams.get("operator") || undefined;
  const date_from = searchParams.get("date_from") || undefined;
  const date_to = searchParams.get("date_to") || undefined;
  const criteria = { search, event_type, operator, date_from, date_to };
  const filtered = Object.values(criteria).some(Boolean);
  const clear = () => update(Object.fromEntries(Object.keys(criteria).map((key) => [key, null])));
  const activity = usePlatformOperationsListActivity(
    { ...criteria, page, page_size: PAGE_SIZE },
    { query: { retry: false, staleTime: 30_000, placeholderData: keepPreviousData } },
  );
  const result = activity.isError && !canShowLastKnownData(activity) ? undefined : activity.data?.data;

  return (
    <section aria-labelledby="platform-page-heading">
      <PlatformPageHeader
        title="Technical activity"
        description="A curated record of Platform Operations events. This is not the global Audit Trail."
      />

      {activity.isError && result ? <RefreshFailureNotice onRetry={() => void activity.refetch()} retrying={activity.isFetching} /> : null}

      {activity.isError && !result ? (
        <PlatformQueryError
          message={activityErrorMessage(activity.error, "Technical activity could not be loaded.")}
          onRetry={() => void activity.refetch()}
        />
      ) : (
        <Panel aria-labelledby="platform-activity-results-heading">
          <PanelHeader
            title="Recorded events"
            titleId="platform-activity-results-heading"
            context={
              activity.isFetching && !activity.isPending
                ? "Refreshing technical activity…"
                : result && !activity.isError
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
          {activity.isPending ? (
            <PlatformRowsSkeleton label="Loading technical activity…" rows={5} framed={false} />
          ) : result && result.items.length ? (
            <ol className="divide-y divide-border">
              {result.items.map((item) => (
                <li key={item.id} className="px-4 py-4 sm:px-5">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-ink">
                        {item.title}
                      </h3>
                      <p className="mt-1 break-words text-sm leading-6 text-muted">
                        {item.description}
                      </p>
                    </div>
                    <div className="shrink-0 text-xs text-muted">
                      <PlatformTimestamp value={item.occurred_at} />
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    Actor: {actorLabel(item.actor_display_name, item.actor_type)}
                  </p>
                </li>
              ))}
            </ol>
          ) : result ? (
            <PanelMessage action={filtered ? <Button variant="secondary" onClick={clear}>Clear filters</Button> : undefined}>{filtered ? "No matching activity." : "No activity has been recorded yet."}</PanelMessage>
          ) : null}
          {result ? (
            <CanonicalPagination
              className="border-brand-line px-4 py-3 sm:px-5"
              page={result.page}
              hasNext={result.has_next}
              disabled={activity.isFetching}
              label="Technical activity pages"
              onPageChange={setPage}
            />
          ) : null}
        </Panel>
      )}
      <ActivityFilterTools key={JSON.stringify(criteria)} applied={criteria} onApply={update} fields={[
        { name: "event_type", label: "Event type", options: Object.values(TechnicalActivityType).map((type) => ({ value: type, label: activityTypeLabel(type) })) },
        { name: "operator", label: "Operator" },
        { name: "date_from", label: "Date from", type: "date" }, { name: "date_to", label: "Date to", type: "date" },
      ]} />
    </section>
  );
}

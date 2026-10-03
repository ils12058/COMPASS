"use client";

import { useState } from "react";

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
import { TechnicalActivityActorType } from "@/lib/api/generated/model";
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
  const [page, setPage] = useState(1);
  const activity = usePlatformOperationsListActivity(
    { page, page_size: PAGE_SIZE },
    { query: { retry: false, staleTime: 30_000 } },
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
          message="Technical activity could not be loaded."
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
                      filtered: false,
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
            <PanelMessage>No technical activity is available yet.</PanelMessage>
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
    </section>
  );
}

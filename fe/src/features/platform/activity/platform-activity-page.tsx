"use client";

import { useState } from "react";

import {
  PlatformPageHeader,
  PlatformPagination,
  PlatformQueryError,
  PlatformRowsSkeleton,
  PlatformTimestamp,
} from "@/features/platform/platform-presentation";
import { usePlatformOperationsListActivity } from "@/lib/api/generated/platform-operations/platform-operations";

const PAGE_SIZE = 20;

function actorLabel(name: string | null, type: string): string {
  return name || type.replaceAll("_", " ").toLowerCase();
}

export function PlatformActivityPage() {
  const [page, setPage] = useState(1);
  const activity = usePlatformOperationsListActivity(
    { page, page_size: PAGE_SIZE },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const result = activity.data?.data;

  return (
    <section>
      <PlatformPageHeader
        title="Technical activity"
        description="A curated record of Platform Operations events. This is not the global Audit Trail."
      />

      {activity.isPending ? <PlatformRowsSkeleton rows={5} /> : null}
      {activity.isError && !result ? (
        <PlatformQueryError
          message="Technical activity could not be loaded."
          onRetry={() => void activity.refetch()}
        />
      ) : null}

      {result ? (
        result.items.length ? (
          <>
            <ol className="divide-y divide-border border-y border-border">
              {result.items.map((item) => (
                <li key={item.id} className="py-5">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <h2 className="text-sm font-semibold text-ink">
                        {item.title}
                      </h2>
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
            <div className="mt-4">
              <PlatformPagination
                page={result.page}
                hasNext={result.has_next}
                disabled={activity.isFetching}
                onPageChange={setPage}
              />
            </div>
          </>
        ) : (
          <p className="border-y border-border py-6 text-sm text-muted">
            No technical activity is available yet.
          </p>
        )
      ) : null}
    </section>
  );
}

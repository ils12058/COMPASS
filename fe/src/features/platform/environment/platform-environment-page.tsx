"use client";

import { PlatformHelp } from "@/features/platform/platform-help";
import { Panel, PanelHeader, PanelMessage, PanelSection } from "@/components/ui/panel";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import {
  PlatformPageHeader,
  PlatformQueryError,
  PlatformRowsSkeleton,
  PlatformTimestamp,
} from "@/features/platform/platform-presentation";
import { usePlatformOperationsEnvironment } from "@/lib/api/generated/platform-operations/platform-operations";

function environmentValue(value: boolean | number | string | null): string {
  if (value === null) return "Not available";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

export function PlatformEnvironmentPage() {
  const environment = usePlatformOperationsEnvironment({
    query: { retry: false, staleTime: 60_000 },
  });
  const result = environment.isError && !canShowLastKnownData(environment) ? undefined : environment.data?.data;

  return (
    <section aria-labelledby="platform-page-heading">
      <PlatformPageHeader
        title="Environment"
        description="Non-secret settings for this deployment."
        help={<PlatformHelp startupLimitation={result?.startup_limitation} />}
      />

      {environment.isPending ? <PlatformRowsSkeleton label="Loading environment details…" rows={5} /> : null}
      {environment.isError && !result ? (
        <PlatformQueryError
          message="Resolved environment diagnostics could not be loaded."
          onRetry={() => void environment.refetch()}
        />
      ) : null}
      {environment.isError && result ? <RefreshFailureNotice onRetry={() => void environment.refetch()} retrying={environment.isFetching} /> : null}

      {result ? (
        <>
          <Panel className="mt-5" aria-labelledby="environment-values-heading">
            <PanelHeader
              title="Resolved configuration"
              titleId="environment-values-heading"
              description={
                <>
                  Resolved{" "}
                  <PlatformTimestamp value={result.timestamp} />.
                </>
              }
            />
            {result.categories.length ? (
              result.categories.map((category) => (
                <PanelSection
                  key={category.code}
                  title={category.label}
                  titleId={`environment-${category.code}`}
                  level={3}
                >
                  {category.values.length ? (
                    <dl className="divide-y divide-border">
                      {category.values.map((item) => (
                        <div
                          key={item.code}
                          className="grid gap-x-6 gap-y-1 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[minmax(12rem,0.4fr)_minmax(0,1fr)]"
                        >
                          <dt className="text-sm font-medium text-muted">
                            {item.label}
                          </dt>
                          <dd className="break-words text-sm text-ink">
                            {environmentValue(item.value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <p className="text-sm text-muted">
                      No values are available for this category.
                    </p>
                  )}
                </PanelSection>
              ))
            ) : (
              <PanelMessage>No environment categories are available.</PanelMessage>
            )}
          </Panel>
        </>
      ) : null}
    </section>
  );
}

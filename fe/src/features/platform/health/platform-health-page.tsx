"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";

import { PageAction } from "@/components/ui/page-action";
import { Button } from "@/components/ui/button";
import { pageSheetWidth } from "@/components/ui/page-width";
import { Panel, PanelBody, PanelHeader, PanelMessage, PanelSection } from "@/components/ui/panel";
import { canShowLastKnownData, shouldHideProtectedData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { platformErrorMessage } from "@/features/platform/platform-actions";
import {
  PlatformPageHeader,
  PlatformQueryError,
  PlatformRowsSkeleton,
  PlatformStatusBadge,
  PlatformTimestamp,
} from "@/features/platform/platform-presentation";
import type { HealthCheckResponse } from "@/lib/api/generated/model";
import {
  usePlatformOperationsHealth,
  usePlatformOperationsWorkerSmoke,
} from "@/lib/api/generated/platform-operations/platform-operations";

export function PlatformHealthPage() {
  const [workerResult, setWorkerResult] = useState<HealthCheckResponse | null>(null);
  const [workerError, setWorkerError] = useState<string | null>(null);
  const health = usePlatformOperationsHealth({
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const workerSmoke = usePlatformOperationsWorkerSmoke();
  const result = health.isError && !canShowLastKnownData(health) ? undefined : health.data?.data;
  const visibleWorkerResult = shouldHideProtectedData(health.error) ? null : workerResult;

  async function checkWorker() {
    setWorkerError(null);
    setWorkerResult(null);
    try {
      const response = await workerSmoke.mutateAsync();
      setWorkerResult(response.data);
    } catch (error) {
      setWorkerError(
        platformErrorMessage(
          error,
          "The background worker diagnostic could not be completed.",
        ),
      );
    }
  }

  return (
    <section aria-labelledby="platform-page-heading" className={`${pageSheetWidth} @container/health`}>
      <PlatformPageHeader
        title="Health"
        action={
          <PageAction
            icon={RefreshCw}
            variant="secondary"
            label={health.isFetching ? "Refreshing…" : "Refresh"}
            labelDetail={health.isFetching ? undefined : "health"}
            disabled={health.isFetching}
            aria-busy={health.isFetching}
            onClick={() => void health.refetch()}
          />
        }
      />

      {/* The passive checks are the page's primary diagnostic; the on-demand worker check is
          secondary and sits beside them once the page itself is wide enough. */}
      <div className="grid items-start gap-5 @[60rem]/health:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
        <div className="min-w-0">
          {health.isPending ? <PlatformRowsSkeleton label="Loading platform health…" rows={5} /> : null}
          {health.isError && !result ? (
            <PlatformQueryError
              message="Platform health diagnostics could not be loaded."
              onRetry={() => void health.refetch()}
            />
          ) : null}
          {health.isError && result ? <RefreshFailureNotice onRetry={() => void health.refetch()} retrying={health.isFetching} /> : null}

          {result ? (
            <Panel aria-labelledby="platform-checks-heading">
              <PanelHeader title="Diagnostic checks" titleId="platform-checks-heading" />
              <PanelBody>
                <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[minmax(9rem,0.35fr)_minmax(0,1fr)]">
                  <dt className="text-sm font-semibold text-muted">Dependency status</dt>
                  <dd className="flex flex-col items-start gap-2">
                    <PlatformStatusBadge status={result.status} />
                    <span className="text-sm leading-6 text-ink">{result.summary}</span>
                  </dd>
                  <dt className="text-sm font-semibold text-muted">Checked</dt>
                  <dd className="text-sm text-ink">
                    <PlatformTimestamp value={result.timestamp} />
                  </dd>
                </dl>
              </PanelBody>
              {result.checks.length ? (
                <ul className="divide-y divide-border border-t border-brand-line">
                  {result.checks.map((check) => (
                    <li
                      key={check.code}
                      className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-start sm:justify-between sm:px-5"
                    >
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-ink">
                          {check.label}
                        </h3>
                        <p className="mt-1 break-words text-sm leading-6 text-muted">
                          {check.summary}
                        </p>
                      </div>
                      <PlatformStatusBadge status={check.status} />
                    </li>
                  ))}
                </ul>
              ) : (
                <PanelMessage className="border-t border-brand-line">
                  No diagnostic checks are available.
                </PanelMessage>
              )}
              <PanelSection
                title="Not checked by passive Health"
                titleId="health-unchecked-heading"
                level={3}
              >
                <p className="text-sm leading-6 text-muted">The checks above cover only the dependencies listed. Worker, scheduler, Daily provider, and Turnstile runtime reachability are not established by this result.</p>
              </PanelSection>
            </Panel>
          ) : null}
        </div>

        <Panel aria-labelledby="platform-worker-heading">
          <PanelHeader
            title="Background worker"
            titleId="platform-worker-heading"
            description="Run a harmless background task to verify that a worker can receive and complete queued work."
            actions={
              <Button
                variant="secondary"
                disabled={workerSmoke.isPending}
                aria-busy={workerSmoke.isPending}
                onClick={() => void checkWorker()}
              >
                {workerSmoke.isPending
                  ? "Checking…"
                  : visibleWorkerResult
                    ? "Check again"
                    : "Check worker"}
              </Button>
            }
          />
          <PanelBody>
            {visibleWorkerResult ? (
              <>
                <p className="mb-2 text-xs font-semibold text-muted">Most recent worker check in this page session</p>
                <PlatformStatusBadge status={visibleWorkerResult.status} />
                <p className="mt-2 text-sm leading-6 text-muted">
                  {visibleWorkerResult.summary}
                </p>
              </>
            ) : (
              <>
                <p className="text-sm font-semibold text-ink">Not checked</p>
                <p className="mt-1 text-sm leading-6 text-muted">
                  This page has not run a worker diagnostic in this session.
                </p>
              </>
            )}
            {workerError ? (
              <p role="alert" className="mt-2 text-sm leading-6 text-danger">
                {workerError}
              </p>
            ) : null}
          </PanelBody>
        </Panel>
      </div>
    </section>
  );
}

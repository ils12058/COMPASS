"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  PlatformPageHeader,
  PlatformQueryError,
  PlatformRowsSkeleton,
  PlatformStatusBadge,
  PlatformTimestamp,
} from "@/features/platform/platform-presentation";
import { platformErrorMessage } from "@/features/platform/platform-actions";
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
  const result = health.data?.data;

  async function checkWorker() {
    setWorkerError(null);
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
    <section>
      <PlatformPageHeader
        title="Health"
        action={
          <Button
            variant="secondary"
            disabled={health.isFetching}
            aria-busy={health.isFetching}
            onClick={() => void health.refetch()}
          >
            <RefreshCw size={16} aria-hidden="true" />
            {health.isFetching ? "Refreshing…" : "Refresh health"}
          </Button>
        }
      />

      {health.isPending ? <PlatformRowsSkeleton rows={5} /> : null}
      {health.isError && !result ? (
        <PlatformQueryError
          message="Platform health diagnostics could not be loaded."
          onRetry={() => void health.refetch()}
        />
      ) : null}

      {result ? (
        <>
          <dl className="grid gap-4 border-y border-border py-5 sm:grid-cols-[minmax(9rem,0.35fr)_minmax(0,1fr)]">
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

          <section className="mt-8" aria-labelledby="platform-checks-heading">
            <h2
              id="platform-checks-heading"
              className="mb-3 font-heading text-xl font-semibold text-ink"
            >
              Diagnostic checks
            </h2>
            {result.checks.length ? (
              <ul className="divide-y divide-border border-y border-border">
                {result.checks.map((check) => (
                  <li
                    key={check.code}
                    className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between"
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
              <p className="border-y border-border py-5 text-sm text-muted">
                No diagnostic checks were returned.
              </p>
            )}
          </section>

          <section className="mt-8 border-t border-border pt-6" aria-labelledby="platform-worker-heading">
            <h2
              id="platform-worker-heading"
              className="font-heading text-xl font-semibold text-ink"
            >
              Background worker
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
              Run a harmless background task to verify that a worker can receive
              and complete queued work.
            </p>

            <div className="mt-4 border-y border-border py-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  {workerResult ? (
                    <>
                      <PlatformStatusBadge status={workerResult.status} />
                      <p className="mt-2 text-sm leading-6 text-muted">
                        {workerResult.summary}
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
                </div>
                <Button
                  variant="secondary"
                  disabled={workerSmoke.isPending}
                  aria-busy={workerSmoke.isPending}
                  onClick={() => void checkWorker()}
                >
                  {workerSmoke.isPending
                    ? "Checking…"
                    : workerResult
                      ? "Check again"
                      : "Check worker"}
                </Button>
              </div>
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
}

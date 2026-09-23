"use client";

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
  const result = environment.data?.data;

  return (
    <section>
      <PlatformPageHeader title="Environment" />

      {environment.isPending ? <PlatformRowsSkeleton rows={5} /> : null}
      {environment.isError && !result ? (
        <PlatformQueryError
          message="Resolved environment diagnostics could not be loaded."
          onRetry={() => void environment.refetch()}
        />
      ) : null}

      {result ? (
        <>
          <p className="mb-6 border-l-2 border-warning pl-4 text-sm leading-6 text-muted">
            {result.startup_limitation}
          </p>
          <p className="mb-5 text-xs text-muted">
            Resolved values only. Secrets and raw environment configuration are
            not shown. Checked <PlatformTimestamp value={result.timestamp} />.
          </p>

          {result.categories.length ? (
            <div className="divide-y divide-border border-y border-border">
              {result.categories.map((category) => (
                <section key={category.code} className="py-5">
                  <h2 className="font-heading text-lg font-semibold text-ink">
                    {category.label}
                  </h2>
                  {category.values.length ? (
                    <dl className="mt-3">
                      {category.values.map((item) => (
                        <div
                          key={item.code}
                          className="grid gap-x-6 gap-y-1 border-t border-border py-3 sm:grid-cols-[minmax(12rem,0.4fr)_minmax(0,1fr)]"
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
                    <p className="mt-2 text-sm text-muted">
                      No resolved values were returned for this category.
                    </p>
                  )}
                </section>
              ))}
            </div>
          ) : (
            <p className="border-y border-border py-5 text-sm text-muted">
              No environment categories were returned.
            </p>
          )}
        </>
      ) : null}
    </section>
  );
}

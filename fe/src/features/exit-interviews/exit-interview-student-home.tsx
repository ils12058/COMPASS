"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import {
  ExitInterviewError,
  ExitInterviewHeading,
  ExitInterviewStatus,
  exitInterviewErrorCode,
  exitInterviewErrorMessage,
  isUncertainExitInterviewMutation,
  shouldHideExitInterviewCachedData,
} from "@/features/exit-interviews/exit-interview-shared";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";
import {
  exitInterviewsEnsureMyCurrent,
  getExitInterviewsGetMineQueryKey,
  getExitInterviewsGetMyCurrentQueryKey,
  getExitInterviewsListMineQueryKey,
  useExitInterviewsGetMyCurrent,
  useExitInterviewsListMine,
} from "@/lib/api/generated/exit-interviews/exit-interviews";

export function ExitInterviewStudentHome({
  access,
}: {
  access: ExitInterviewAccess;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const current = useExitInterviewsGetMyCurrent({
    query: { enabled: access.canViewSelf, retry: false },
  });
  const history = useExitInterviewsListMine({
    query: { enabled: access.canViewSelf, retry: false },
  });
  const start = useMutation({
    mutationFn: () => exitInterviewsEnsureMyCurrent(),
    retry: false,
  });
  const [startError, setStartError] = useState<unknown>();
  const [needsStatusCheck, setNeedsStatusCheck] = useState(false);

  if (!access.canViewSelf) {
    return (
      <section className="max-w-2xl space-y-5">
        <ExitInterviewHeading title="Exit Interview" />
        <p role="alert" className="border-y border-border py-5 text-sm leading-6 text-muted">
          Your current access does not allow you to view your Exit Interview records.
        </p>
      </section>
    );
  }

  const currentNotFound =
    current.isError && exitInterviewErrorCode(current.error) === "exit_interview_not_found";
  const currentCode = current.isError ? exitInterviewErrorCode(current.error) : undefined;
  const suppressStaleCurrent =
    (current.isError && shouldHideExitInterviewCachedData(current.error)) ||
    currentCode === "current_student_required";
  const suppressStaleHistory =
    history.isError && shouldHideExitInterviewCachedData(history.error);
  const currentRecord = suppressStaleCurrent ? undefined : current.data?.data;
  const historicalItems = (history.data?.data.items ?? []).filter(
    (item) => item.id !== currentRecord?.id,
  );

  async function handleStart() {
    setStartError(undefined);
    setNeedsStatusCheck(false);
    try {
      const result = await start.mutateAsync();
      queryClient.setQueryData(getExitInterviewsGetMyCurrentQueryKey(), result);
      queryClient.setQueryData(
        getExitInterviewsGetMineQueryKey(result.data.id),
        result,
      );
      void queryClient.invalidateQueries({
        queryKey: getExitInterviewsListMineQueryKey(),
      });
      router.push(`/portal/exit-interviews/${result.data.id}`);
    } catch (error) {
      setStartError(error);
      setNeedsStatusCheck(isUncertainExitInterviewMutation(error));
    }
  }

  async function checkCurrentStatus() {
    const result = await current.refetch();
    if (
      !result.isError ||
      exitInterviewErrorCode(result.error) === "exit_interview_not_found"
    ) {
      setNeedsStatusCheck(false);
      setStartError(undefined);
    }
  }

  return (
    <section className="space-y-2" aria-labelledby="exit-interview-home-heading">
      <ExitInterviewHeading
        id="exit-interview-home-heading"
        title="Exit Interview"
        description="Complete the Exit Interview for your current Academic Year and view earlier records."
      />

      <section aria-labelledby="exit-interview-current-heading" className="py-6">
        <h2 id="exit-interview-current-heading" className="font-heading text-xl font-semibold text-ink">
          Current Academic Year
        </h2>
        {current.isPending ? (
          <div className="mt-4 space-y-3" aria-busy="true" aria-label="Loading current Exit Interview">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-16 w-full max-w-2xl" />
          </div>
        ) : current.isError && !currentNotFound && (!current.data || suppressStaleCurrent) ? (
          <div className="mt-4 max-w-2xl">
            <ExitInterviewError
              error={current.error}
              fallback="The current Academic Year Exit Interview could not be loaded."
              onRetry={() => void current.refetch()}
            />
          </div>
        ) : currentRecord ? (
          <div className="mt-4 max-w-3xl border-y border-border py-5">
            {current.isError ? (
              <p role="alert" className="mb-4 text-sm text-danger">
                The current status could not be refreshed. Showing the last confirmed record.
              </p>
            ) : current.isFetching ? (
              <p role="status" className="mb-4 text-xs text-muted">Refreshing current status…</p>
            ) : null}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-semibold text-ink">{currentRecord.academic_year.label}</h3>
              <ExitInterviewStatus status={currentRecord.status} />
            </div>
            <p className="mt-2 text-sm leading-6 text-muted">
              {currentRecord.status === "DRAFT"
                ? "This is a saved working response. Its answers remain private from Head Guidance until you submit it."
                : "This response has been submitted and is available to Head Guidance for review."}
            </p>
            <p className="mt-2 text-xs text-muted">
              {currentRecord.status === "SUBMITTED"
                ? `Last submitted ${formatExitInterviewDateTime(currentRecord.last_submitted_at ?? currentRecord.first_submitted_at)}`
                : `Last updated ${formatExitInterviewDateTime(currentRecord.updated_at)}`}
            </p>
            <Link
              href={`/portal/exit-interviews/${currentRecord.id}`}
              className="mt-4 inline-flex min-h-10 items-center font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {currentRecord.status === "SUBMITTED"
                ? "View submitted Exit Interview"
                : access.canManageSelf
                  ? "Continue Exit Interview"
                  : "View draft Exit Interview"}
            </Link>
          </div>
        ) : currentNotFound ? (
          <div className="mt-4 max-w-3xl border-y border-border py-5">
            <p className="text-sm leading-6 text-muted">
              No Exit Interview has been started for the current Academic Year.
              {access.canManageSelf
                ? " Start only when you are ready to work on the form."
                : " A current Student account with Exit Interview management access is required to start one."}
            </p>
            {access.canManageSelf ? (
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button onClick={() => void handleStart()} disabled={start.isPending || needsStatusCheck}>
                  {start.isPending ? "Starting…" : "Start Exit Interview"}
                </Button>
                {needsStatusCheck ? (
                  <Button variant="secondary" onClick={() => void checkCurrentStatus()} disabled={current.isFetching}>
                    {current.isFetching ? "Checking…" : "Check current status"}
                  </Button>
                ) : null}
              </div>
            ) : null}
            {startError ? (
              <div className="mt-4 max-w-2xl">
                {exitInterviewErrorCode(startError) === "exit_interview_inventory_required" ? (
                  <p role="alert" className="text-sm leading-6 text-danger">
                    {exitInterviewErrorMessage(startError, "A submitted Individual Inventory is required before starting.")} {" "}
                    <Link href="/portal/inventory" className="font-semibold underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                      Open Individual Inventory
                    </Link>
                  </p>
                ) : (
                  <p role="alert" className="text-sm leading-6 text-danger">
                    {needsStatusCheck
                      ? "We could not confirm whether the Exit Interview started. Check the canonical current status before trying again."
                      : exitInterviewErrorMessage(startError, "The Exit Interview could not be started.")}
                  </p>
                )}
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section aria-labelledby="exit-interview-history-heading" className="border-t border-border py-6">
        <h2 id="exit-interview-history-heading" className="font-heading text-xl font-semibold text-ink">
          Exit Interview history
        </h2>
        {history.isPending ? (
          <div className="mt-4 space-y-3" aria-busy="true" aria-label="Loading Exit Interview history">
            <Skeleton className="h-14 w-full max-w-3xl" />
            <Skeleton className="h-14 w-full max-w-3xl" />
          </div>
        ) : history.isError &&
          (!history.data || suppressStaleHistory) ? (
          <div className="mt-4 max-w-2xl">
            <ExitInterviewError
              error={history.error}
              fallback="Exit Interview history could not be loaded."
              onRetry={() => void history.refetch()}
            />
          </div>
        ) : historicalItems.length === 0 ? (
          history.isError ? (
            <div className="mt-4 max-w-2xl">
              <ExitInterviewError
                error={history.error}
                fallback="Exit Interview history could not be refreshed."
                onRetry={() => void history.refetch()}
              />
            </div>
          ) : (
            <p className="mt-4 max-w-3xl border-y border-border py-5 text-sm text-muted">
              No earlier Exit Interviews are available.
            </p>
          )
        ) : (
          <>
            {history.isError ? (
              <div className="mt-4 max-w-2xl">
                <ExitInterviewError
                  error={history.error}
                  fallback="Exit Interview history could not be refreshed."
                  onRetry={() => void history.refetch()}
                />
              </div>
            ) : null}
            <ul className="mt-3 max-w-3xl divide-y divide-border border-y border-border">
              {historicalItems.map((item) => (
                <li key={item.id} className="py-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <Link
                        href={`/portal/exit-interviews/${item.id}`}
                        className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                      >
                        {item.academic_year.label}
                      </Link>
                      <p className="mt-1 text-xs text-muted">
                        Updated {formatExitInterviewDateTime(item.updated_at)}
                        {item.last_submitted_at
                          ? ` · Last submitted ${formatExitInterviewDateTime(item.last_submitted_at)}`
                          : ""}
                      </p>
                    </div>
                    <ExitInterviewStatus status={item.status} />
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </section>
  );
}

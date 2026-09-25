"use client";

import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { ExitInterviewForm } from "@/features/exit-interviews/exit-interview-form";
import { ExitInterviewReopenAction } from "@/features/exit-interviews/exit-interview-reopen-dialog";
import { ExitInterviewResponse } from "@/features/exit-interviews/exit-interview-response";
import {
  ExitInterviewError,
  ExitInterviewUnavailable,
  exitInterviewErrorCode,
  shouldHideExitInterviewCachedData,
} from "@/features/exit-interviews/exit-interview-shared";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import {
  useExitInterviewsGet,
  useExitInterviewsGetMine,
} from "@/lib/api/generated/exit-interviews/exit-interviews";
import { usePortalSession } from "@/features/portal/components/portal-session";

function DetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true"><span className="sr-only">Loading Exit Interview…</span>
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-12 w-2/3" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function StudentExitInterviewDetail({
  exitInterviewId,
  canManageSelf,
  isCurrentStudent,
}: {
  exitInterviewId: string;
  canManageSelf: boolean;
  isCurrentStudent: boolean;
}) {
  const detail = useExitInterviewsGetMine(exitInterviewId, {
    query: { retry: false },
  });

  if (detail.isPending) return <DetailSkeleton />;

  const hideCachedDetail =
    detail.isError &&
    shouldHideExitInterviewCachedData(detail.error);

  if (detail.isError && (!detail.data || hideCachedDetail)) {
    const code = exitInterviewErrorCode(detail.error);
    if (code === "permission_denied") {
      return (
        <div className="space-y-5">
          <Link href="/portal/exit-interviews" className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Exit Interviews</Link>
          <ExitInterviewUnavailable title="Exit Interview unavailable" message="Your current access does not allow you to view this Exit Interview." />
        </div>
      );
    }
    return (
      <section className="max-w-3xl space-y-5">
        <Link href="/portal/exit-interviews" className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Exit Interviews</Link>
        {code === "exit_interview_not_found" ? (
          <div role="alert" className="border-y border-border py-6">
            <h1 className="font-heading text-2xl font-semibold text-ink">Exit Interview not found</h1>
            <p className="mt-2 text-sm text-muted">This Exit Interview could not be found.</p>
          </div>
        ) : (
          <ExitInterviewError error={detail.error} fallback="The Exit Interview could not be loaded." onRetry={() => void detail.refetch()} />
        )}
      </section>
    );
  }

  const record = detail.data.data;
  if (record.status === "DRAFT" && canManageSelf && !detail.isError) {
    async function refreshRecord() {
      const result = await detail.refetch();
      return result.isError ? undefined : result.data?.data;
    }
    return <ExitInterviewForm key={record.id} detail={record} onRefreshRecord={refreshRecord} />;
  }

  return (
    <div className="space-y-4">
      {detail.isError ? (
        <div className="max-w-3xl">
          <ExitInterviewError
            error={detail.error}
            fallback="The latest Exit Interview status could not be confirmed. Showing the last confirmed, read-only response."
            onRetry={() => void detail.refetch()}
          />
        </div>
      ) : null}
    <section className="space-y-4">
      {record.status === "DRAFT" && detail.isError ? (
        <p role="status" className="border-l-4 border-warning bg-warning/5 px-4 py-3 text-sm leading-6 text-ink">
          The latest status could not be confirmed. This last-confirmed draft is read-only until it can be refreshed.
        </p>
      ) : record.status === "DRAFT" && !isCurrentStudent ? (
        <p role="status" className="border-l-4 border-warning bg-warning/5 px-4 py-3 text-sm leading-6 text-ink">
          This historical draft remains available to view, but correction is unavailable under the current Student lifecycle policy.
        </p>
      ) : record.status === "DRAFT" ? (
        <p role="status" className="border-l-4 border-border bg-surface-muted px-4 py-3 text-sm leading-6 text-muted">
          This draft is read-only because current Exit Interview management access is not available.
        </p>
      ) : null}
      <ExitInterviewResponse
        detail={record}
        studentFacing
        backHref="/portal/exit-interviews"
      />
    </section>
    </div>
  );
}

function HeadExitInterviewDetail({
  exitInterviewId,
  canReopen,
}: {
  exitInterviewId: string;
  canReopen: boolean;
}) {
  const detail = useExitInterviewsGet(exitInterviewId, {
    query: { retry: false },
  });

  if (detail.isPending) return <DetailSkeleton />;

  const hideCachedDetail =
    detail.isError &&
    (shouldHideExitInterviewCachedData(detail.error) ||
      exitInterviewErrorCode(detail.error) === "exit_interview_not_submitted");

  if (detail.isError && (!detail.data || hideCachedDetail)) {
    const code = exitInterviewErrorCode(detail.error);
    if (code === "exit_interview_not_submitted") {
      return (
        <section className="max-w-3xl space-y-5">
          <Link href="/portal/exit-interviews" className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Exit Interview queue</Link>
          <div role="status" className="border-y border-border py-6">
            <h1 className="font-heading text-2xl font-semibold text-ink">Exit Interview is not available for review</h1>
            <p className="mt-2 text-sm leading-6 text-muted">
              This Exit Interview is currently a draft and is not available for Head Guidance review until the Student submits it.
            </p>
          </div>
        </section>
      );
    }
    if (code === "permission_denied") {
      return (
        <section className="space-y-5">
          <Link href="/portal/exit-interviews" className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Exit Interview queue</Link>
          <ExitInterviewUnavailable title="Exit Interview unavailable" message="Your current access does not allow you to review this Exit Interview." />
        </section>
      );
    }
    return (
      <section className="max-w-3xl space-y-5">
        <Link href="/portal/exit-interviews" className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Exit Interview queue</Link>
        <ExitInterviewError error={detail.error} fallback="The submitted Exit Interview could not be loaded." onRetry={() => void detail.refetch()} />
      </section>
    );
  }

  const record = detail.data.data;
  if (record.status === "DRAFT") {
    return (
      <section className="max-w-3xl space-y-5">
        {detail.isError ? (
          <ExitInterviewError
            error={detail.error}
            fallback="The latest Exit Interview status could not be confirmed. This last-confirmed draft remains hidden from review."
            onRetry={() => void detail.refetch()}
          />
        ) : null}
        <Link href="/portal/exit-interviews" className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Exit Interview queue</Link>
        <div role="status" className="border-y border-border py-6">
          <h1 className="font-heading text-2xl font-semibold text-ink">Exit Interview is not available for review</h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            This Exit Interview is currently a draft and is not available for Head Guidance review until the Student submits it.
          </p>
        </div>
      </section>
    );
  }
  return (
    <div className="space-y-4">
      {detail.isError ? (
        <div className="max-w-3xl">
          <ExitInterviewError
            error={detail.error}
            fallback="The latest Exit Interview status could not be confirmed. Showing the last confirmed, read-only response."
            onRetry={() => void detail.refetch()}
          />
        </div>
      ) : null}
      <ExitInterviewResponse
        detail={record}
        studentFacing={false}
        backHref="/portal/exit-interviews"
        headerAction={canReopen && record.status === "SUBMITTED" && !detail.isError ? <ExitInterviewReopenAction exitInterviewId={record.id} /> : undefined}
      />
    </div>
  );
}

export function ExitInterviewDetailPage({
  exitInterviewId,
}: {
  exitInterviewId: string;
}) {
  const { user } = usePortalSession();
  const access = getExitInterviewAccess(user);

  if (access.isStudent) {
    if (!access.canViewSelf) {
      return <ExitInterviewUnavailable title="Exit Interview unavailable" message="Your current access does not include your Exit Interview records." />;
    }
    return (
      <StudentExitInterviewDetail
        exitInterviewId={exitInterviewId}
        canManageSelf={access.canManageSelf}
        isCurrentStudent={access.isCurrentStudent}
      />
    );
  }

  if (access.canViewOperational) {
    return <HeadExitInterviewDetail exitInterviewId={exitInterviewId} canReopen={access.canReopen} />;
  }

  return <ExitInterviewUnavailable title="Exit Interview unavailable" message="Your current access does not include the Exit Interview review workspace." />;
}

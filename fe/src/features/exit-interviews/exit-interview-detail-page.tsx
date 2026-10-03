"use client";

import Link from "next/link";

import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { ExitInterviewForm } from "@/features/exit-interviews/exit-interview-form";
import { ExitInterviewPdfDownload } from "@/features/exit-interviews/exit-interview-pdf-download";
import { ExitInterviewReopenAction } from "@/features/exit-interviews/exit-interview-reopen-dialog";
import { ExitInterviewResponse } from "@/features/exit-interviews/exit-interview-response";
import {
  ExitInterviewDetailSkeleton,
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

  if (detail.isPending) return <ExitInterviewDetailSkeleton />;

  const hideCachedDetail =
    detail.isError &&
    shouldHideExitInterviewCachedData(detail.error);

  if (detail.isError && (!detail.data || hideCachedDetail)) {
    const code = exitInterviewErrorCode(detail.error);
    if (code === "permission_denied") {
      return (
        <div className="space-y-5">
          <Link href="/portal/exit-interviews" className={pageBackLinkClass}>Back to Exit Interviews</Link>
          <ExitInterviewUnavailable title="Exit Interview unavailable" message="This Exit Interview is unavailable to this account." />
        </div>
      );
    }
    return (
      <section className="max-w-3xl space-y-5">
        <Link href="/portal/exit-interviews" className={pageBackLinkClass}>Back to Exit Interviews</Link>
        {code === "exit_interview_not_found" ? (
          <Notice role="alert" title={<h1 className="font-heading text-2xl font-semibold text-ink">Exit Interview not found</h1>}>
            This Exit Interview could not be found.
          </Notice>
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
        <Notice role="status" tone="warning">
          <span className="text-ink">The latest status could not be confirmed. This last-confirmed draft is read-only until it can be refreshed.</span>
        </Notice>
      ) : record.status === "DRAFT" && !isCurrentStudent ? (
        <Notice role="status" tone="warning">
          <span className="text-ink">You can view this historical draft, but can no longer change it.</span>
        </Notice>
      ) : record.status === "DRAFT" ? (
        <Notice role="status">
          You can view this draft, but cannot change it with this account.
        </Notice>
      ) : null}
      <ExitInterviewResponse
        detail={record}
        studentFacing
        backHref="/portal/exit-interviews"
        headerAction={record.status === "SUBMITTED" && !detail.isError ? <ExitInterviewPdfDownload exitInterviewId={record.id} studentFacing /> : undefined}
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

  if (detail.isPending) return <ExitInterviewDetailSkeleton />;

  const hideCachedDetail =
    detail.isError &&
    (shouldHideExitInterviewCachedData(detail.error) ||
      exitInterviewErrorCode(detail.error) === "exit_interview_not_submitted");

  if (detail.isError && (!detail.data || hideCachedDetail)) {
    const code = exitInterviewErrorCode(detail.error);
    if (code === "exit_interview_not_submitted") {
      return (
        <section className="max-w-3xl space-y-5">
          <Link href="/portal/exit-interviews" className={pageBackLinkClass}>Back to Exit Interview queue</Link>
          <Notice role="status" title={<h1 className="font-heading text-2xl font-semibold text-ink">Exit Interview is not available for review</h1>}>
            This Exit Interview is currently a draft and is not available for Head Guidance review until the Student submits it.
          </Notice>
        </section>
      );
    }
    if (code === "permission_denied") {
      return (
        <section className="space-y-5">
          <Link href="/portal/exit-interviews" className={pageBackLinkClass}>Back to Exit Interview queue</Link>
          <ExitInterviewUnavailable title="Exit Interview unavailable" message="You cannot review this Exit Interview with this account." />
        </section>
      );
    }
    return (
      <section className="max-w-3xl space-y-5">
        <Link href="/portal/exit-interviews" className={pageBackLinkClass}>Back to Exit Interview queue</Link>
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
        <Link href="/portal/exit-interviews" className={pageBackLinkClass}>Back to Exit Interview queue</Link>
        <Notice role="status" title={<h1 className="font-heading text-2xl font-semibold text-ink">Exit Interview is not available for review</h1>}>
          This Exit Interview is currently a draft and is not available for Head Guidance review until the Student submits it.
        </Notice>
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
        headerAction={!detail.isError ? <>
          <ExitInterviewPdfDownload exitInterviewId={record.id} studentFacing={false} />
          {canReopen ? <ExitInterviewReopenAction exitInterviewId={record.id} /> : null}
        </> : undefined}
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
      return <ExitInterviewUnavailable title="Exit Interview unavailable" message="Your Exit Interview records are unavailable to this account." />;
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

  return <ExitInterviewUnavailable title="Exit Interview unavailable" message="Exit Interview review is unavailable to this account." />;
}

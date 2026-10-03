"use client";

import { keepPreviousData, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingRegion } from "@/components/ui/loading-region";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import {
  hasPrivacyConflictCode,
  PrivacyConflictCode,
  privacyErrorMessage,
} from "@/features/privacy-governance/privacy-governance-errors";
import { audienceSummary } from "@/features/privacy-governance/privacy-governance-presentation";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";
import type { MyNoticeResponse } from "@/lib/api/generated/model";
import {
  getPrivacyGovernanceListMyNoticesQueryKey,
  usePrivacyGovernanceAcknowledgeMyNotice,
  usePrivacyGovernanceListMyNotices,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

const ACKNOWLEDGMENT_HELP =
  "Acknowledgment records that you have seen this notice. It is not consent to all data processing.";

function acknowledgeErrorMessage(caught: unknown): string {
  if (
    caught instanceof CompassApiError &&
    readApiErrorCode(caught.body) === "permission_denied"
  ) {
    return "Your account cannot acknowledge notices right now.";
  }
  return privacyErrorMessage(caught, "The notice could not be acknowledged.");
}

function NoticeArticle({
  notice,
  pending,
  disabled,
  onAcknowledge,
}: {
  notice: MyNoticeResponse;
  pending: boolean;
  disabled: boolean;
  onAcknowledge: () => void;
}) {
  const headingId = `notice-${notice.revision_id}`;
  return (
    <article aria-labelledby={headingId} className="px-4 py-5 sm:px-5">
      <h3 id={headingId} className="font-heading text-lg font-semibold text-ink">
        {notice.title}
      </h3>
      <p className="mt-1 text-xs leading-5 text-muted">
        {notice.name} · Revision {notice.revision_number} · Effective{" "}
        {formatDateOnly(notice.effective_on)} · For {audienceSummary(notice.audiences)}
      </p>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">{notice.summary}</p>
      <div className="mt-4">
        <PlainTextBlock text={notice.body} />
      </div>
      {notice.requires_acknowledgment ? (
        <div className="mt-5 max-w-3xl border-t border-border pt-4">
          {notice.acknowledged && notice.acknowledged_at ? (
            <p className="text-sm font-medium text-success">
              Acknowledged {formatInstitutionalDateTime(notice.acknowledged_at)}
            </p>
          ) : (
            <>
              <p className="text-xs leading-5 text-muted">{ACKNOWLEDGMENT_HELP}</p>
              <Button className="mt-3" disabled={disabled} onClick={onAcknowledge}>
                {pending ? "Acknowledging…" : "Acknowledge notice"}
              </Button>
            </>
          )}
        </div>
      ) : null}
    </article>
  );
}

export function AccountPrivacyPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const notices = usePrivacyGovernanceListMyNotices(
    { page, page_size: 20 },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const acknowledge = usePrivacyGovernanceAcknowledgeMyNotice();
  const [pendingRevision, setPendingRevision] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const result = safeQueryData(notices)?.data;

  // The acknowledged state shown comes from the refreshed notice list, never
  // from an optimistic update.
  async function acknowledgeNotice(notice: MyNoticeResponse) {
    setError(null);
    setStatus(null);
    setPendingRevision(notice.revision_id);
    try {
      await acknowledge.mutateAsync({ revisionId: notice.revision_id, data: {} });
      await queryClient.invalidateQueries({
        queryKey: getPrivacyGovernanceListMyNoticesQueryKey(),
      });
      setStatus(`“${notice.title}” acknowledged.`);
    } catch (caught) {
      setError(acknowledgeErrorMessage(caught));
      if (
        hasPrivacyConflictCode(caught, PrivacyConflictCode.noticeRevisionNotCurrent) ||
        hasPrivacyConflictCode(caught, PrivacyConflictCode.acknowledgmentNotApplicable)
      ) {
        void queryClient.invalidateQueries({
          queryKey: getPrivacyGovernanceListMyNoticesQueryKey(),
        });
      }
    } finally {
      setPendingRevision(null);
    }
  }

  return (
    <section aria-labelledby="account-privacy-heading">
      <PageHeader title="Privacy" headingId="account-privacy-heading" />

      {error ? (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {status ? (
        <p role="status" className="mb-4 text-sm text-success">
          {status}
        </p>
      ) : null}
      {notices.isError && result ? <RefreshFailureNotice onRetry={() => void notices.refetch()} retrying={notices.isFetching} /> : null}

      <Panel aria-labelledby="privacy-notices-heading">
        <PanelHeader
          title="Privacy notices"
          titleId="privacy-notices-heading"
          description="Current COMPASS privacy notices that apply to your account."
          context={notices.isFetching && !notices.isPending ? "Refreshing privacy notices…" : null}
        />
        {notices.isPending ? (
          <LoadingRegion label="Loading privacy notices…" className="space-y-4 px-4 py-5 sm:px-5">
            <Skeleton className="h-6 w-72 max-w-full" />
            <Skeleton className="h-4 w-56" />
            <Skeleton className="h-28 w-full" />
          </LoadingRegion>
        ) : notices.isError && !result ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={
              <Button variant="secondary" onClick={() => void notices.refetch()}>
                Retry
              </Button>
            }
          >
            {privacyErrorMessage(notices.error, "Privacy notices could not be loaded.")}
          </PanelMessage>
        ) : result && result.items.length === 0 ? (
          <PanelMessage>
            {page === 1
              ? "No privacy notices currently apply to your account."
              : "No privacy notices on this page."}
          </PanelMessage>
        ) : result ? (
          <div className="divide-y divide-border">
            {result.items.map((notice) => (
              <NoticeArticle
                key={notice.revision_id}
                notice={notice}
                pending={pendingRevision === notice.revision_id}
                disabled={pendingRevision !== null || notices.isError}
                onAcknowledge={() => void acknowledgeNotice(notice)}
              />
            ))}
          </div>
        ) : null}
        {result ? (
          <CanonicalPagination
            className="border-brand-line px-4 py-3 sm:px-5"
            page={result.page}
            hasNext={result.has_next}
            onPageChange={setPage}
            label="Privacy notice pages"
          />
        ) : null}
      </Panel>
    </section>
  );
}

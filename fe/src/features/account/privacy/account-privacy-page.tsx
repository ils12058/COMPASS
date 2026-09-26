"use client";

import { keepPreviousData, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import {
  isPrivacyConflict,
  privacyConflictMessages,
  privacyErrorMessage,
} from "@/features/privacy-governance/privacy-governance-errors";
import { audienceSummary } from "@/features/privacy-governance/privacy-governance-presentation";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { formatDateOnly, formatDateTime } from "@/lib/date-time";
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
    <article aria-labelledby={headingId} className="py-6">
      <h3 id={headingId} className="font-heading text-xl font-semibold text-ink">
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
              Acknowledged {formatDateTime(notice.acknowledged_at)}
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
  const result = notices.data?.data;

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
      if (isPrivacyConflict(caught, privacyConflictMessages.noticeNotCurrent)) {
        void queryClient.invalidateQueries({
          queryKey: getPrivacyGovernanceListMyNoticesQueryKey(),
        });
      }
    } finally {
      setPendingRevision(null);
    }
  }

  return (
    <section>
      <h1 className="font-heading text-3xl font-bold text-ink">Privacy</h1>

      <section aria-labelledby="privacy-notices-heading" className="mt-8">
        <h2 id="privacy-notices-heading" className="font-heading text-xl font-semibold text-ink">
          Privacy notices
        </h2>
        <p className="mt-1 text-sm leading-6 text-muted">
          Current COMPASS privacy notices that apply to your account.
        </p>

        {error ? (
          <p role="alert" className="mt-4 text-sm text-danger">
            {error}
          </p>
        ) : null}
        {status ? (
          <p role="status" className="mt-4 text-sm text-success">
            {status}
          </p>
        ) : null}

        <div className="mt-4">
          {notices.isPending ? (
            <div aria-busy="true" className="space-y-4 border-y border-border py-6">
              <Skeleton className="h-6 w-72 max-w-full" />
              <Skeleton className="h-4 w-56" />
              <Skeleton className="h-28 w-full" />
              <p className="sr-only">Loading privacy notices…</p>
            </div>
          ) : notices.isError && !result ? (
            <div role="alert" className="border-y border-border py-6">
              <p className="text-sm text-danger">
                {privacyErrorMessage(notices.error, "Privacy notices could not be loaded.")}
              </p>
              <Button variant="secondary" className="mt-4" onClick={() => void notices.refetch()}>
                Retry
              </Button>
            </div>
          ) : result && result.items.length === 0 ? (
            <p className="border-y border-border py-6 text-sm text-muted">
              {page === 1
                ? "No privacy notices currently apply to your account."
                : "No privacy notices on this page."}
            </p>
          ) : result ? (
            <>
              {notices.isFetching ? (
                <p role="status" className="mb-2 text-xs text-muted">
                  Refreshing privacy notices…
                </p>
              ) : null}
              <div className="divide-y divide-border border-y border-border">
                {result.items.map((notice) => (
                  <NoticeArticle
                    key={notice.revision_id}
                    notice={notice}
                    pending={pendingRevision === notice.revision_id}
                    disabled={pendingRevision !== null}
                    onAcknowledge={() => void acknowledgeNotice(notice)}
                  />
                ))}
              </div>
              {result.page > 1 || result.has_next ? (
                <CanonicalPagination
                  page={result.page}
                  hasNext={result.has_next}
                  onPageChange={setPage}
                  label="Privacy notice pages"
                />
              ) : null}
            </>
          ) : null}
        </div>
      </section>
    </section>
  );
}

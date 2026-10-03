"use client";

import { keepPreviousData } from "@tanstack/react-query";

import { Notice } from "@/components/ui/notice";
import { Panel } from "@/components/ui/panel";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import { formatPublicDate } from "@/features/public/shared/presentation";
import { PublicPagination } from "@/features/public/shared/public-pagination";
import { PublicListSkeleton, PublicPageError } from "@/features/public/shared/public-state";
import { usePrivacyGovernanceListPublicNotices } from "@/lib/api/generated/privacy-governance/privacy-governance";

// Notice text comes only from published PUBLIC revisions and is rendered as
// plain text; COMPASS adds no policy wording of its own.
export function PublicPrivacyNotices({ page }: { page: number }) {
  const query = usePrivacyGovernanceListPublicNotices(
    { page, page_size: 10 },
    { query: { placeholderData: keepPreviousData } },
  );

  if (query.isPending) return <PublicListSkeleton rows={2} />;

  if (query.isError) {
    return (
      <PublicPageError
        message="Privacy notices could not be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const result = query.data.data;

  if (result.items.length === 0) {
    return (
      <Notice>
        {page === 1
          ? "No public COMPASS privacy notice is currently published."
          : "No privacy notices on this page."}
      </Notice>
    );
  }

  return (
    <Panel as="div" aria-busy={query.isFetching}>
      <div className="divide-y divide-border">
        {result.items.map((notice) => (
          <article
            key={notice.revision_id}
            aria-labelledby={`public-notice-${notice.revision_id}`}
            className="px-5 py-6 sm:px-8 sm:py-7"
          >
            <h2
              id={`public-notice-${notice.revision_id}`}
              className="font-heading text-2xl font-semibold text-ink"
            >
              {notice.title}
            </h2>
            <p className="mt-2 text-sm text-muted">
              Effective{" "}
              <time dateTime={notice.effective_on}>{formatPublicDate(notice.effective_on)}</time>
            </p>
            <p className="mt-4 max-w-3xl text-base leading-7 text-ink">{notice.summary}</p>
            <div className="mt-5">
              <PlainTextBlock text={notice.body} className="text-base" />
            </div>
          </article>
        ))}
      </div>

      {query.isFetching && !query.isPending ? (
        <p role="status" className="border-t border-border px-5 py-2 text-xs text-muted sm:px-8">Refreshing privacy notices…</p>
      ) : null}

      <PublicPagination
        page={result.page}
        hasNext={result.has_next}
        buildHref={(nextPage) => `/privacy?page=${nextPage}`}
      />
    </Panel>
  );
}

"use client";

import { keepPreviousData } from "@tanstack/react-query";
import { Pin } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Panel, PanelMessage } from "@/components/ui/panel";
import {
  useAnnouncementsListPublic,
  useAnnouncementsListVisible,
} from "@/lib/api/generated/announcements/announcements";
import { cn } from "@/lib/utils/cn";
import { AnnouncementDate } from "@/features/announcements/announcement-date";
import { markdownPreview } from "@/features/public/shared/presentation";
import { PublicPagination } from "@/features/public/shared/public-pagination";
import { PublicRowsSkeleton, PublicSectionError } from "@/features/public/shared/public-state";
import {
  isSignedOutError,
  useReaderAudience,
  useSessionRecheck,
} from "@/features/public/shared/use-reader-audience";

type AnnouncementListProps =
  | { mode: "preview" }
  | { mode: "index"; page: number };

export function AnnouncementList(props: AnnouncementListProps) {
  const isPreview = props.mode === "preview";
  const page = isPreview ? 1 : props.page;
  const params = { page, page_size: isPreview ? 3 : 10 };
  const audience = useReaderAudience();
  const account = useAnnouncementsListVisible(params, {
    query: { enabled: audience === "account", placeholderData: keepPreviousData, retry: false },
  });
  const signedOut = isSignedOutError(account.error);
  useSessionRecheck(signedOut);
  const readsAccount = audience === "account" && !signedOut;
  const publicQuery = useAnnouncementsListPublic(params, {
    query: { enabled: audience === "public" || signedOut, placeholderData: keepPreviousData },
  });
  const query = readsAccount ? account : publicQuery;
  // The landing page's preview panel brings its own title band; the index page frames the list here.
  const frame = (content: ReactNode) =>
    isPreview ? content : <Panel as="div">{content}</Panel>;

  if (audience === "pending" || query.isPending) {
    return frame(<PublicRowsSkeleton rows={isPreview ? 3 : 5} label="Loading announcements…" />);
  }

  if (query.isError) {
    return frame(
      <PublicSectionError
        message={readsAccount ? "Announcements could not be loaded." : "Public announcements could not be loaded."}
        onRetry={() => void query.refetch()}
      />,
    );
  }

  const result = query.data.data;

  if (result.items.length === 0) {
    return frame(
      <PanelMessage>
        {readsAccount
          ? "No announcements are available right now."
          : "No public announcements are available right now."}
      </PanelMessage>,
    );
  }

  return frame(
    <div aria-busy={query.isFetching}>
      <ol className="divide-y divide-border">
        {result.items.map((announcement) => {
          const preview = markdownPreview(announcement.body_markdown);

          return (
            <li key={announcement.id}>
              <Link
                href={`/announcements/${announcement.id}`}
                className="group grid grid-cols-[3.5rem_minmax(0,1fr)] items-start gap-x-4 px-4 py-4 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:grid-cols-[4rem_minmax(0,1fr)_auto] sm:gap-x-5 sm:px-5"
              >
                <AnnouncementDate value={announcement.published_at} />
                <span className="min-w-0">
                  <span className="block font-heading text-lg font-semibold leading-6 text-ink transition-colors group-hover:text-brand">
                    {announcement.title}
                  </span>
                  {preview ? (
                    <span className="mt-1 line-clamp-2 text-sm leading-6 text-muted">{preview}</span>
                  ) : null}
                  {announcement.is_pinned ? (
                    <PinnedLabel className="mt-2 sm:hidden" />
                  ) : null}
                </span>
                {announcement.is_pinned ? <PinnedLabel className="hidden sm:inline-flex" /> : null}
              </Link>
            </li>
          );
        })}
      </ol>

      {query.isFetching && !query.isPending ? (
        <p role="status" className="border-t border-border px-4 py-2 text-xs text-muted sm:px-5">Refreshing announcements…</p>
      ) : null}

      {!isPreview ? (
        <PublicPagination
          page={result.page}
          hasNext={result.has_next}
          buildHref={(nextPage) => `/announcements?page=${nextPage}`}
        />
      ) : null}
    </div>,
  );
}

function PinnedLabel({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex w-fit items-center gap-1 text-xs font-semibold text-brand", className)}>
      <Pin size={14} aria-hidden="true" />
      Pinned
    </span>
  );
}

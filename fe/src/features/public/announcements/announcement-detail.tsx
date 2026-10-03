"use client";

import { Pin } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Notice } from "@/components/ui/notice";
import { Panel } from "@/components/ui/panel";
import { PublicMarkdown } from "@/features/public/shared/public-markdown";
import { formatPublicDate } from "@/features/public/shared/presentation";
import { PublicListSkeleton, PublicPageError } from "@/features/public/shared/public-state";
import {
  isSignedOutError,
  useReaderAudience,
  useSessionRecheck,
} from "@/features/public/shared/use-reader-audience";
import { CompassApiError } from "@/lib/api/errors";
import {
  useAnnouncementsGetPublic,
  useAnnouncementsGetVisible,
} from "@/lib/api/generated/announcements/announcements";

const MAX_TIMEOUT_MS = 2_147_000_000;

function AnnouncementUnavailable({ readsAccount }: { readsAccount: boolean }) {
  return (
    <Notice title={<h1 className="font-heading text-2xl font-bold text-ink">Announcement not found</h1>}>
      {readsAccount ? (
        <p>This announcement does not exist or is not available to your account.</p>
      ) : (
        <>
          <p>This announcement does not exist or is no longer publicly available.</p>
          <p className="mt-2">
            If it was shared with COMPASS account holders,{" "}
            <Link href="/login" className="font-semibold text-brand underline">
              sign in
            </Link>{" "}
            and open it again.
          </p>
        </>
      )}
    </Notice>
  );
}

export function AnnouncementDetail({ announcementId }: { announcementId: string }) {
  const audience = useReaderAudience();
  const account = useAnnouncementsGetVisible(announcementId, {
    query: { enabled: audience === "account", retry: false },
  });
  const signedOut = isSignedOutError(account.error);
  useSessionRecheck(signedOut);
  const readsAccount = audience === "account" && !signedOut;
  const publicQuery = useAnnouncementsGetPublic(announcementId, {
    query: { enabled: audience === "public" || signedOut },
  });
  const query = readsAccount ? account : publicQuery;
  const [reachedExpiry, setReachedExpiry] = useState<string | null>(null);
  const expiresAt = query.data?.data.expires_at ?? null;
  const refetchCurrent = readsAccount ? account.refetch : publicQuery.refetch;
  const expiryReached = expiresAt !== null && reachedExpiry === expiresAt;

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active = true;

    if (!expiresAt) {
      return () => {
        active = false;
      };
    }

    const expiryMs = Date.parse(expiresAt);
    const reconcileAtBoundary = () => {
      if (!active) return;
      const remaining = expiryMs - Date.now();
      if (!Number.isFinite(expiryMs) || remaining <= 0) {
        setReachedExpiry(expiresAt);
        void refetchCurrent();
        return;
      }
      timer = setTimeout(reconcileAtBoundary, Math.min(remaining, MAX_TIMEOUT_MS));
    };

    const initialDelay = Number.isFinite(expiryMs)
      ? Math.min(Math.max(expiryMs - Date.now(), 0), MAX_TIMEOUT_MS)
      : 0;
    timer = setTimeout(reconcileAtBoundary, initialDelay);

    return () => {
      active = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [expiresAt, refetchCurrent]);

  if (audience === "pending" || query.isPending) {
    return <PublicListSkeleton rows={4} />;
  }

  if (expiryReached) {
    if (query.isFetching) {
      return (
        <Notice role="status">
          This announcement has reached its expiry time. Checking availability…
        </Notice>
      );
    }

    if (query.error instanceof CompassApiError && query.error.status === 404) {
      return <AnnouncementUnavailable readsAccount={readsAccount} />;
    }

    return (
      <PublicPageError
        message="This announcement has reached its expiry time and its availability could not be confirmed."
        onRetry={() => void refetchCurrent()}
      />
    );
  }

  if (query.isError) {
    if (query.error instanceof CompassApiError && query.error.status === 404) {
      return <AnnouncementUnavailable readsAccount={readsAccount} />;
    }

    return (
      <PublicPageError
        message="This announcement could not be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const announcement = query.data.data;

  return (
    <Panel as="article" aria-busy={query.isFetching}>
      <header className="border-b border-brand-line px-5 py-5 sm:px-8 sm:py-6">
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          <time dateTime={announcement.published_at}>{formatPublicDate(announcement.published_at)}</time>
          {announcement.is_pinned ? (
            <span className="inline-flex items-center gap-1 font-semibold text-brand">
              <Pin size={14} aria-hidden="true" />
              Pinned
            </span>
          ) : null}
        </div>
        <h1 className="mt-3 font-heading text-3xl font-bold leading-tight tracking-tight text-ink sm:text-4xl">
          {announcement.title}
        </h1>
      </header>
      <div className="px-5 py-6 sm:px-8 sm:py-7">
        <PublicMarkdown>{announcement.body_markdown}</PublicMarkdown>
      </div>
      {query.isFetching ? <p role="status" className="border-t border-border px-5 py-2 text-xs text-muted sm:px-8">Refreshing announcement…</p> : null}
    </Panel>
  );
}

"use client";

import { Pin } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PublicMarkdown } from "@/features/public/shared/public-markdown";
import { formatPublicDate } from "@/features/public/shared/presentation";
import { PublicListSkeleton, PublicSectionError } from "@/features/public/shared/public-state";
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
    <div className="border-y border-border py-8">
      <h1 className="font-heading text-3xl font-bold text-ink">Announcement not found</h1>
      {readsAccount ? (
        <p className="mt-3 leading-7 text-muted">
          This announcement does not exist or is not available to your account.
        </p>
      ) : (
        <>
          <p className="mt-3 leading-7 text-muted">
            This announcement does not exist or is no longer publicly available.
          </p>
          <p className="mt-2 leading-7 text-muted">
            If it was shared with COMPASS account holders,{" "}
            <Link href="/login" className="font-semibold text-brand underline">
              sign in
            </Link>{" "}
            and open it again.
          </p>
        </>
      )}
    </div>
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
        <div role="status" className="border-y border-border py-8 text-sm leading-6 text-muted">
          This announcement has reached its expiry time. Checking availability…
        </div>
      );
    }

    if (query.error instanceof CompassApiError && query.error.status === 404) {
      return <AnnouncementUnavailable readsAccount={readsAccount} />;
    }

    return (
      <PublicSectionError
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
      <PublicSectionError
        message="This announcement could not be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const announcement = query.data.data;

  return (
    <article aria-busy={query.isFetching}>
      <div className="border-b border-border pb-7">
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          <time dateTime={announcement.published_at}>{formatPublicDate(announcement.published_at)}</time>
          {announcement.is_pinned ? (
            <span className="inline-flex items-center gap-1 font-semibold text-brand">
              <Pin size={14} aria-hidden="true" />
              Pinned
            </span>
          ) : null}
        </div>
        <h1 className="mt-4 font-heading text-4xl font-bold leading-tight tracking-tight text-ink sm:text-5xl">
          {announcement.title}
        </h1>
      </div>
      <div className="mt-8">
        <PublicMarkdown>{announcement.body_markdown}</PublicMarkdown>
      </div>
      {query.isFetching ? <p role="status" className="mt-6 text-xs text-muted">Refreshing announcement…</p> : null}
    </article>
  );
}

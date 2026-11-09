"use client";

import Link from "next/link";

import { AnnouncementUnavailable } from "@/features/announcements/announcement-detail-page";
import { shouldHideAnnouncementData } from "@/features/announcements/announcement-errors";
import { AnnouncementForm } from "@/features/announcements/announcement-form";
import {
  ContentDetailSkeleton,
  ContentNotice,
  ContentPageHeading,
  PublicationStatusBadge,
} from "@/features/content/content-shared";
import { useAnnouncementsGetManaged } from "@/lib/api/generated/announcements/announcements";
import { AnnouncementStatusValue } from "@/lib/api/generated/model";

export function AnnouncementEditPage({ announcementId }: { announcementId: string }) {
  const detail = useAnnouncementsGetManaged(announcementId, { query: { retry: false } });
  const backHref = `/portal/announcements/${announcementId}`;

  if (detail.isPending) return <ContentDetailSkeleton label="Loading Announcement…" />;
  // A failed refresh keeps the form; its unsaved text stays in place.
  if (!detail.data || (detail.isError && shouldHideAnnouncementData(detail.error))) {
    return <AnnouncementUnavailable error={detail.error} onRetry={() => void detail.refetch()} />;
  }

  const item = detail.data.data;

  return (
    <section>
      <ContentPageHeading title="Edit Announcement" backHref={backHref} backLabel="Back to Announcement">
        <div className="mt-3">
          <PublicationStatusBadge status={item.status} />
        </div>
      </ContentPageHeading>

      {item.status === AnnouncementStatusValue.ARCHIVED ? (
        <div className="mt-6 space-y-4">
          <ContentNotice tone="info">Archived Announcements cannot be edited.</ContentNotice>
          <Link href={backHref} className="text-sm font-semibold text-brand underline">
            View the Announcement
          </Link>
        </div>
      ) : (
        <>
          {item.status === AnnouncementStatusValue.PUBLISHED ? (
            <div className="mt-6">
              <ContentNotice tone="info">
                This Announcement is published. Saved changes are visible to readers immediately.
              </ContentNotice>
            </div>
          ) : null}
          <AnnouncementForm key={item.id} announcement={item} />
        </>
      )}
    </section>
  );
}

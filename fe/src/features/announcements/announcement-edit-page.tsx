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
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useAnnouncementsGetManaged } from "@/lib/api/generated/announcements/announcements";
import { AnnouncementStatusValue } from "@/lib/api/generated/model";

export function AnnouncementEditPage({ announcementId }: { announcementId: string }) {
  const { user } = usePortalSession();
  const isGoa = user.role === "GUIDANCE_OFFICE_ASSISTANT";
  const detail = useAnnouncementsGetManaged(announcementId, { query: { retry: false } });
  const backHref = `/portal/announcements/${announcementId}`;

  if (detail.isPending) return <ContentDetailSkeleton label="Loading Announcement…" />;
  // A failed refresh keeps the form; its unsaved text stays in place.
  if (!detail.data || (detail.isError && shouldHideAnnouncementData(detail.error))) {
    return <AnnouncementUnavailable error={detail.error} onRetry={() => void detail.refetch()} />;
  }

  const item = detail.data.data;
  const goaBlocked =
    isGoa &&
    (item.status === AnnouncementStatusValue.PUBLISHED ||
      item.status === AnnouncementStatusValue.PENDING_APPROVAL);

  return (
    <section>
      <ContentPageHeading title="Edit Announcement" backHref={backHref} backLabel="Back to Announcement">
        <div className="mt-3">
          <PublicationStatusBadge status={item.status} />
        </div>
      </ContentPageHeading>

      {item.status === AnnouncementStatusValue.ARCHIVED || goaBlocked ? (
        <div className="mt-6 space-y-4">
          <ContentNotice tone="info">
            {item.status === AnnouncementStatusValue.ARCHIVED
              ? "Archived Announcements cannot be edited."
              : item.status === AnnouncementStatusValue.PENDING_APPROVAL
                ? "This Announcement is waiting for approval and cannot be edited until your supervising Counselor reviews or returns it."
                : "A Guidance Office Assistant cannot edit a published Announcement."}
          </ContentNotice>
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

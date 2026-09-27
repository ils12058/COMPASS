"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { refreshAnnouncementQueries, storeManagedAnnouncement } from "@/features/announcements/announcement-cache";
import {
  announcementErrorCode,
  announcementErrorMessage,
  isUncertainAnnouncementMutation,
} from "@/features/announcements/announcement-errors";
import { displayTitle, publicationAudienceReaders } from "@/features/content/content-presentation";
import { ContentConfirmDialog } from "@/features/content/content-shared";
import {
  getAnnouncementsGetManagedQueryKey,
  useAnnouncementsArchive,
  useAnnouncementsPublish,
} from "@/lib/api/generated/announcements/announcements";
import { AnnouncementStatusValue, type AnnouncementManagementResponse } from "@/lib/api/generated/model";
import { formatDateTime } from "@/lib/date-time";

type LifecycleAction = "publish" | "archive";

export function AnnouncementLifecycleActions({
  announcement,
  publishBlocked,
  onCompleted,
}: {
  announcement: AnnouncementManagementResponse;
  publishBlocked: boolean;
  onCompleted: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const publish = useAnnouncementsPublish();
  const archive = useAnnouncementsArchive();
  const [open, setOpen] = useState<LifecycleAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const title = `“${displayTitle(announcement.title, "Untitled Announcement")}”`;
  const isDraft = announcement.status === AnnouncementStatusValue.DRAFT;
  const isArchived = announcement.status === AnnouncementStatusValue.ARCHIVED;

  async function run(action: LifecycleAction) {
    setError(null);
    try {
      const response =
        action === "publish"
          ? await publish.mutateAsync({ announcementId: announcement.id })
          : await archive.mutateAsync({ announcementId: announcement.id });
      storeManagedAnnouncement(queryClient, response);
      setOpen(null);
      onCompleted(action === "publish" ? "Announcement published." : "Announcement archived.");
      void refreshAnnouncementQueries(queryClient, announcement.id, { readers: true });
    } catch (caught) {
      const fallback =
        action === "publish"
          ? "The Announcement could not be published."
          : "The Announcement could not be archived.";
      if (isUncertainAnnouncementMutation(caught)) {
        setError(`${fallback} Check its current status before trying again.`);
      } else {
        setError(announcementErrorMessage(caught, fallback));
      }
      // Show the record's current state when the outcome is unknown or the
      // record changed elsewhere.
      if (isUncertainAnnouncementMutation(caught) || announcementErrorCode(caught) === "announcement_not_editable") {
        void queryClient.invalidateQueries({ queryKey: getAnnouncementsGetManagedQueryKey(announcement.id) });
      }
    }
  }

  function openDialog(action: LifecycleAction) {
    setError(null);
    setOpen(action);
  }

  return (
    <>
      {isDraft ? (
        <Button disabled={publishBlocked} onClick={() => openDialog("publish")}>
          Publish Announcement
        </Button>
      ) : null}
      {!isArchived ? (
        <Button variant="secondary" onClick={() => openDialog("archive")}>
          Archive Announcement
        </Button>
      ) : null}

      <ContentConfirmDialog
        open={open === "publish"}
        title={`Publish ${title}?`}
        description={
          <>
            <p>
              As soon as it is published, it will be visible to {publicationAudienceReaders[announcement.audience]}.
              {announcement.is_pinned ? " It is pinned, so it will be listed before other Announcements." : null}
            </p>
            {announcement.expires_at ? (
              <p>It will stop being shown after {formatDateTime(announcement.expires_at)}.</p>
            ) : null}
          </>
        }
        confirmLabel="Publish Announcement"
        pendingLabel="Publishing…"
        pending={publish.isPending}
        error={open === "publish" ? error : null}
        onOpenChange={(next) => setOpen(next ? "publish" : null)}
        onConfirm={() => void run("publish")}
      />
      <ContentConfirmDialog
        open={open === "archive"}
        title={`Archive ${title}?`}
        description={
          <p>
            {isDraft
              ? "The draft will be closed without being published."
              : "Readers will no longer see it."}{" "}
            Archived Announcements cannot be edited or published again.
          </p>
        }
        confirmLabel="Archive Announcement"
        pendingLabel="Archiving…"
        pending={archive.isPending}
        error={open === "archive" ? error : null}
        destructive
        onOpenChange={(next) => setOpen(next ? "archive" : null)}
        onConfirm={() => void run("archive")}
      />
    </>
  );
}

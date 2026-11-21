"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Archive, RotateCcw, Send } from "lucide-react";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { PageAction } from "@/components/ui/page-action";
import { Textarea } from "@/components/ui/textarea";
import { refreshAnnouncementQueries, storeManagedAnnouncement } from "@/features/announcements/announcement-cache";
import {
  announcementErrorCode,
  announcementErrorMessage,
  isUncertainAnnouncementMutation,
} from "@/features/announcements/announcement-errors";
import { displayTitle, publicationAudienceReaders } from "@/features/content/content-presentation";
import { ContentConfirmDialog } from "@/features/content/content-shared";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getAnnouncementsGetManagedQueryKey,
  useAnnouncementsArchive,
  useAnnouncementsPublish,
  useAnnouncementsReturnDraft,
  useAnnouncementsSubmitForApproval,
} from "@/lib/api/generated/announcements/announcements";
import { AnnouncementStatusValue, type AnnouncementManagementResponse } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

type LifecycleAction = "publish" | "submit" | "return" | "archive";

export function AnnouncementLifecycleActions({
  announcement,
  publishBlocked,
  onCompleted,
}: {
  announcement: AnnouncementManagementResponse;
  publishBlocked: boolean;
  onCompleted: (message: string) => void;
}) {
  const { user } = usePortalSession();
  const isGoa = user.role === "GUIDANCE_OFFICE_ASSISTANT";
  const queryClient = useQueryClient();
  const publish = useAnnouncementsPublish();
  const submit = useAnnouncementsSubmitForApproval();
  const returnDraft = useAnnouncementsReturnDraft();
  const archive = useAnnouncementsArchive();
  const [open, setOpen] = useState<LifecycleAction | null>(null);
  const [returnNote, setReturnNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const title = `“${displayTitle(announcement.title, "Untitled Announcement")}”`;
  const isDraft = announcement.status === AnnouncementStatusValue.DRAFT;
  const isPendingApproval = announcement.status === AnnouncementStatusValue.PENDING_APPROVAL;
  const isPublished = announcement.status === AnnouncementStatusValue.PUBLISHED;
  const isArchived = announcement.status === AnnouncementStatusValue.ARCHIVED;

  async function run(action: LifecycleAction) {
    setError(null);
    if (action === "return" && !returnNote.trim()) {
      setError("Enter a note explaining the needed changes.");
      return;
    }
    try {
      const response =
        action === "publish"
          ? await publish.mutateAsync({ announcementId: announcement.id })
          : action === "submit"
            ? await submit.mutateAsync({ announcementId: announcement.id })
            : action === "return"
              ? await returnDraft.mutateAsync({ announcementId: announcement.id, data: { note: returnNote.trim() } })
              : await archive.mutateAsync({ announcementId: announcement.id });
      storeManagedAnnouncement(queryClient, response);
      setOpen(null);
      if (action === "return") setReturnNote("");
      onCompleted(
        action === "publish"
          ? "Announcement published."
          : action === "submit"
            ? "Submitted to your supervising Counselor for approval."
            : action === "return"
              ? "Returned to the Guidance Office Assistant for changes."
              : "Announcement archived.",
      );
      void refreshAnnouncementQueries(queryClient, announcement.id, { readers: true });
      void invalidateGuidanceWork(queryClient);
    } catch (caught) {
      const fallback =
        action === "publish"
          ? "Couldn't publish Announcement. Try again."
          : action === "submit"
            ? "Couldn't submit Announcement for approval. Try again."
            : action === "return"
              ? "Couldn't return Announcement. Try again."
              : "Couldn't archive Announcement. Try again.";
      if (isUncertainAnnouncementMutation(caught)) {
        setError("Couldn't confirm whether the change was saved. Check its current status before trying again.");
      } else {
        setError(announcementErrorMessage(caught, fallback));
      }
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
      {isDraft && isGoa ? (
        <PageAction icon={Send} label="Submit for approval" disabled={publishBlocked} onClick={() => openDialog("submit")} />
      ) : null}
      {(isDraft || isPendingApproval) && !isGoa ? (
        <PageAction
          icon={Send}
          label={isPendingApproval ? "Approve and publish" : "Publish Announcement"}
          disabled={publishBlocked}
          onClick={() => openDialog("publish")}
        />
      ) : null}
      {isPendingApproval && !isGoa ? (
        <PageAction icon={RotateCcw} variant="secondary" label="Return for changes" onClick={() => openDialog("return")} />
      ) : null}
      {!isArchived && !(isGoa && (isPublished || isPendingApproval)) ? (
        <PageAction icon={Archive} variant="secondary" label="Archive Announcement" onClick={() => openDialog("archive")} />
      ) : null}

      <ContentConfirmDialog
        open={open === "submit"}
        title={`Submit ${title} for approval?`}
        description={
          <p>
            Your supervising Counselor will review this draft and can publish it or return it with a note. Readers will not see it until your supervising Counselor approves and publishes it.
          </p>
        }
        confirmLabel="Submit for approval"
        pendingLabel="Submitting…"
        pending={submit.isPending}
        error={open === "submit" ? error : null}
        onOpenChange={(next) => setOpen(next ? "submit" : null)}
        onConfirm={() => void run("submit")}
      />
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
              <p>It will stop being shown after {formatInstitutionalDateTime(announcement.expires_at)}.</p>
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
      <ConsequentialActionDialog
        open={open === "return"}
        title={`Return ${title} for changes?`}
        confirmLabel="Return for changes"
        pendingLabel="Returning…"
        pending={returnDraft.isPending}
        confirmDisabled={!returnNote.trim()}
        error={open === "return" ? error : null}
        onOpenChange={(next) => setOpen(next ? "return" : null)}
        onConfirm={() => void run("return")}
      >
        <p>The draft will return to the Guidance Office Assistant with your note so they can revise and resubmit it.</p>
        <div className="grid gap-2">
          <Label htmlFor="announcement-return-note">Return note</Label>
          <Textarea
            id="announcement-return-note"
            rows={3}
            maxLength={1_000}
            required
            value={returnNote}
            disabled={returnDraft.isPending}
            onChange={(event) => setReturnNote(event.target.value)}
          />
          <p className="text-xs text-muted">{returnNote.length} / 1,000 characters</p>
        </div>
      </ConsequentialActionDialog>
      <ContentConfirmDialog
        open={open === "archive"}
        title={`Archive ${title}?`}
        description={
          <p>
            {isDraft || isPendingApproval
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

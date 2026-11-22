"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Archive, RotateCcw, Send } from "lucide-react";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { PageAction } from "@/components/ui/page-action";
import { Textarea } from "@/components/ui/textarea";
import { displayTitle, publicationAudienceReaders } from "@/features/content/content-presentation";
import { ContentConfirmDialog } from "@/features/content/content-shared";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { refreshResourceQueries, storeManagedResource } from "@/features/resources/resource-cache";
import {
  isUncertainResourceMutation,
  resourceErrorCode,
  resourceErrorMessage,
} from "@/features/resources/resource-errors";
import {
  getResourcesGetManagedQueryKey,
  useResourcesArchive,
  useResourcesPublish,
  useResourcesReturnDraft,
  useResourcesSubmitForApproval,
} from "@/lib/api/generated/resources/resources";
import { ResourceStatusValue, type ResourceManagementResponse } from "@/lib/api/generated/model";

type LifecycleAction = "publish" | "submit" | "return" | "archive";

export function ResourceLifecycleActions({
  resource,
  publishBlocked,
  onCompleted,
}: {
  resource: ResourceManagementResponse;
  publishBlocked: boolean;
  onCompleted: (message: string) => void;
}) {
  const { user } = usePortalSession();
  const isGoa = user.role === "GUIDANCE_OFFICE_ASSISTANT";
  const queryClient = useQueryClient();
  const publish = useResourcesPublish();
  const submit = useResourcesSubmitForApproval();
  const returnDraft = useResourcesReturnDraft();
  const archive = useResourcesArchive();
  const [open, setOpen] = useState<LifecycleAction | null>(null);
  const [returnNote, setReturnNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const title = `“${displayTitle(resource.title, "Untitled Resource")}”`;
  const isDraft = resource.status === ResourceStatusValue.DRAFT;
  const isPendingApproval = resource.status === ResourceStatusValue.PENDING_APPROVAL;
  const isPublished = resource.status === ResourceStatusValue.PUBLISHED;
  const isArchived = resource.status === ResourceStatusValue.ARCHIVED;

  async function run(action: LifecycleAction) {
    setError(null);
    if (action === "return" && !returnNote.trim()) {
      setError("Enter a note explaining the needed changes.");
      return;
    }
    try {
      const response =
        action === "publish"
          ? await publish.mutateAsync({ resourceId: resource.id })
          : action === "submit"
            ? await submit.mutateAsync({ resourceId: resource.id })
            : action === "return"
              ? await returnDraft.mutateAsync({ resourceId: resource.id, data: { note: returnNote.trim() } })
              : await archive.mutateAsync({ resourceId: resource.id });
      storeManagedResource(queryClient, response);
      setOpen(null);
      if (action === "return") setReturnNote("");
      onCompleted(
        action === "publish"
          ? "Resource published."
          : action === "submit"
            ? "Submitted to your supervising Counselor for approval."
            : action === "return"
              ? "Returned to the Guidance Office Assistant for changes."
              : "Resource archived.",
      );
      void refreshResourceQueries(queryClient, resource.id, { readers: true });
      void invalidateGuidanceWork(queryClient);
    } catch (caught) {
      const fallback =
        action === "publish"
          ? "Couldn't publish Resource. Try again."
          : action === "submit"
            ? "Couldn't submit Resource for approval. Try again."
            : action === "return"
              ? "Couldn't return Resource. Try again."
              : "Couldn't archive Resource. Try again.";
      setError(
        isUncertainResourceMutation(caught)
          ? "Couldn't confirm whether the change was saved. Check its current status before trying again."
          : resourceErrorMessage(caught, fallback),
      );
      if (isUncertainResourceMutation(caught) || resourceErrorCode(caught) === "resource_conflict") {
        void queryClient.invalidateQueries({ queryKey: getResourcesGetManagedQueryKey(resource.id) });
      }
    }
  }

  function openDialog(action: LifecycleAction) {
    setError(null);
    setOpen(action);
  }

  const primaryAction =
    isDraft && isGoa
      ? { action: "submit" as const, label: "Submit for approval" }
      : (isDraft || isPendingApproval) && !isGoa
        ? {
            action: "publish" as const,
            label: isPendingApproval ? "Approve and publish" : "Publish Resource",
          }
        : null;

  return (
    <>
      {primaryAction ? (
        <PageAction
          icon={Send}
          label={primaryAction.label}
          disabled={publishBlocked}
          onClick={() => openDialog(primaryAction.action)}
        />
      ) : null}
      {isPendingApproval && !isGoa ? (
        <PageAction icon={RotateCcw} variant="secondary" label="Return for changes" onClick={() => openDialog("return")} />
      ) : null}
      {!isArchived && !(isGoa && (isPublished || isPendingApproval)) ? (
        <PageAction icon={Archive} variant="secondary" label="Archive Resource" onClick={() => openDialog("archive")} />
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
            <p>As soon as it is published, it will be visible to {publicationAudienceReaders[resource.audience]}.</p>
            <p>After publication, its type cannot be changed{resource.has_file ? " and its file cannot be replaced" : ""}.</p>
          </>
        }
        confirmLabel="Publish Resource"
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
          <Label htmlFor="resource-return-note">Return note</Label>
          <Textarea
            id="resource-return-note"
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
            Archived Resources cannot be edited or published again.
          </p>
        }
        confirmLabel="Archive Resource"
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

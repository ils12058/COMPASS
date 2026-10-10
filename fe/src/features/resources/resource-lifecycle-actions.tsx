"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Archive, Send } from "lucide-react";
import { PageAction } from "@/components/ui/page-action";
import { displayTitle, publicationAudienceReaders } from "@/features/content/content-presentation";
import { ContentConfirmDialog } from "@/features/content/content-shared";
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
} from "@/lib/api/generated/resources/resources";
import { ResourceStatusValue, type ResourceManagementResponse } from "@/lib/api/generated/model";

type LifecycleAction = "publish" | "archive";

export function ResourceLifecycleActions({
  resource,
  publishBlocked,
  onCompleted,
}: {
  resource: ResourceManagementResponse;
  publishBlocked: boolean;
  onCompleted: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const publish = useResourcesPublish();
  const archive = useResourcesArchive();
  const [open, setOpen] = useState<LifecycleAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const title = `“${displayTitle(resource.title, "Untitled Resource")}”`;
  const isDraft = resource.status === ResourceStatusValue.DRAFT;
  const isArchived = resource.status === ResourceStatusValue.ARCHIVED;

  async function run(action: LifecycleAction) {
    setError(null);
    try {
      const response =
        action === "publish"
          ? await publish.mutateAsync({ resourceId: resource.id })
          : await archive.mutateAsync({ resourceId: resource.id });
      storeManagedResource(queryClient, response);
      setOpen(null);
      onCompleted(action === "publish" ? "Resource published." : "Resource archived.");
      void refreshResourceQueries(queryClient, resource.id, { readers: true });
    } catch (caught) {
      const fallback =
        action === "publish" ? "The Resource could not be published." : "The Resource could not be archived.";
      setError(
        isUncertainResourceMutation(caught)
          ? `${fallback} Check its current status before trying again.`
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

  return (
    <>
      {isDraft ? (
        <PageAction icon={Send} label="Publish Resource" disabled={publishBlocked} onClick={() => openDialog("publish")} />
      ) : null}
      {!isArchived ? (
        <PageAction icon={Archive} variant="secondary" label="Archive Resource" onClick={() => openDialog("archive")} />
      ) : null}

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
      <ContentConfirmDialog
        open={open === "archive"}
        title={`Archive ${title}?`}
        description={
          <p>
            {isDraft ? "The draft will be closed without being published." : "Readers will no longer see it."}{" "}
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

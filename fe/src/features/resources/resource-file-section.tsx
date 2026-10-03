"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileDown, FileText } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { PanelSection } from "@/components/ui/panel";
import { displayTitle, formatFileSize } from "@/features/content/content-presentation";
import { ContentConfirmDialog } from "@/features/content/content-shared";
import { getSafeHttpUrl } from "@/features/public/shared/presentation";
import { refreshResourceQueries, storeManagedResource } from "@/features/resources/resource-cache";
import { isUncertainResourceMutation, resourceErrorMessage } from "@/features/resources/resource-errors";
import {
  getResourcesGetManagedQueryKey,
  resourcesDownloadManagedFile,
  useResourcesAttachDraftFile,
  useResourcesRemoveDraftFile,
} from "@/lib/api/generated/resources/resources";
import { ResourceStatusValue, type ResourceManagementResponse } from "@/lib/api/generated/model";

// Mirrors the backend upload rules so an unsuitable file is caught before it
// is sent; the backend still validates the content.
const PDF_TYPE = "application/pdf";
const MAX_FILE_BYTES = 10 * 1024 * 1024;

function localFileProblem(file: File): string | null {
  if (file.type !== PDF_TYPE) return "Only PDF files can be attached.";
  if (file.size === 0) return "The selected file is empty.";
  if (file.size > MAX_FILE_BYTES) return "The PDF must be 10 MB or smaller.";
  return null;
}

export function ResourceFileSection({ resource }: { resource: ResourceManagementResponse }) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const attach = useResourcesAttachDraftFile();
  const remove = useResourcesRemoveDraftFile();
  const download = useMutation({
    mutationFn: async () => {
      const response = await resourcesDownloadManagedFile(resource.id);
      const url = getSafeHttpUrl(response.data.url);
      if (!url) throw new Error("The download link returned by the service is not valid.");
      return url;
    },
    onSuccess: (url) => window.location.assign(url),
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [removeOpen, setRemoveOpen] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const isDraft = resource.status === ResourceStatusValue.DRAFT;
  const busy = attach.isPending || remove.isPending;
  const fileName = resource.original_filename ?? "the attached file";

  function showCurrentState(caught: unknown) {
    if (isUncertainResourceMutation(caught)) {
      void queryClient.invalidateQueries({ queryKey: getResourcesGetManagedQueryKey(resource.id) });
    }
  }

  async function upload(file: File) {
    setError(null);
    setNotice(null);
    download.reset();
    const problem = localFileProblem(file);
    if (problem) {
      setError(problem);
      return;
    }
    const replacing = resource.has_file;
    try {
      const response = await attach.mutateAsync({ resourceId: resource.id, data: { file } });
      storeManagedResource(queryClient, response);
      void refreshResourceQueries(queryClient, resource.id, { readers: false });
      setNotice(replacing ? "File replaced." : "File attached.");
    } catch (caught) {
      setError(resourceErrorMessage(caught, replacing ? "The file could not be replaced." : "The file could not be attached."));
      showCurrentState(caught);
    }
  }

  async function confirmRemove() {
    setRemoveError(null);
    try {
      const response = await remove.mutateAsync({ resourceId: resource.id });
      storeManagedResource(queryClient, response);
      void refreshResourceQueries(queryClient, resource.id, { readers: false });
      setRemoveOpen(false);
      setError(null);
      setNotice("File removed.");
    } catch (caught) {
      setRemoveError(resourceErrorMessage(caught, "The file could not be removed."));
      showCurrentState(caught);
    }
  }

  return (
    <PanelSection title="File" titleId="resource-file-heading">

      {resource.has_file ? (
        <div className="mt-4 flex flex-wrap items-start gap-3">
          <FileText size={20} aria-hidden="true" className="mt-0.5 shrink-0 text-support-strong" />
          <div className="min-w-0">
            <p className="break-all text-sm font-semibold text-ink">{fileName}</p>
            <p className="mt-0.5 text-xs text-muted">PDF · {formatFileSize(resource.size_bytes)}</p>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-muted">
          {isDraft
            ? "No file is attached. Attach a PDF of up to 10 MB before publishing."
            : "No file was attached."}
        </p>
      )}

      {!isDraft && resource.has_file && resource.status === ResourceStatusValue.PUBLISHED ? (
        <p className="mt-3 text-xs leading-5 text-muted">The file cannot be changed after the Resource is published.</p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {resource.has_file ? (
          <Button variant="secondary" disabled={download.isPending || busy} onClick={() => download.mutate()}>
            <FileDown size={17} aria-hidden="true" />
            {download.isPending ? "Preparing download…" : "Download file"}
          </Button>
        ) : null}
        {isDraft ? (
          <>
            <input
              ref={inputRef}
              type="file"
              accept={PDF_TYPE}
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void upload(file);
              }}
            />
            <Button variant="secondary" disabled={busy} onClick={() => inputRef.current?.click()}>
              {attach.isPending
                ? resource.has_file ? "Replacing file…" : "Attaching file…"
                : resource.has_file ? "Replace file" : "Attach file"}
            </Button>
            {resource.has_file ? (
              <Button
                variant="quiet"
                disabled={busy}
                onClick={() => {
                  setRemoveError(null);
                  setRemoveOpen(true);
                }}
              >
                Remove file
              </Button>
            ) : null}
          </>
        ) : null}
      </div>

      {error ? <p role="alert" className="mt-3 text-sm leading-6 text-danger">{error}</p> : null}
      {download.isError ? (
        <p role="alert" className="mt-3 text-sm leading-6 text-danger">
          {resourceErrorMessage(download.error, "The download could not be prepared. Try again.")}
        </p>
      ) : null}
      <div aria-live="polite">
        {notice ? <p className="mt-3 text-sm text-success">{notice}</p> : null}
      </div>

      <ContentConfirmDialog
        open={removeOpen}
        title={`Remove ${fileName} from “${displayTitle(resource.title, "Untitled Resource")}”?`}
        description={
          <p>The file will be deleted from this draft. Attach another PDF before publishing the Resource.</p>
        }
        confirmLabel="Remove file"
        pendingLabel="Removing…"
        pending={remove.isPending}
        error={removeError}
        destructive
        onOpenChange={setRemoveOpen}
        onConfirm={() => void confirmRemove()}
      />
    </PanelSection>
  );
}

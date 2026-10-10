"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  PDF_MAX_BYTES,
  contentMutationError,
  formatFileSize,
} from "@/features/content/presentation";
import {
  getResourcesGetManagedQueryKey,
  getResourcesListManagedQueryKey,
  useResourcesAttachDraftFile,
} from "@/lib/api/generated/resources/resources";
import type { ResourceManagementResponse } from "@/lib/api/generated/model";

export function ResourceFilePanel({
  item,
  disabled = false,
}: {
  item: ResourceManagementResponse;
  disabled?: boolean;
}) {
  const queryClient = useQueryClient();
  const upload = useResourcesAttachDraftFile();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (item.kind !== "FILE") {
    return null;
  }

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getResourcesListManagedQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getResourcesGetManagedQueryKey(item.id) }),
    ]);
  }

  async function attach(file: File) {
    setError(null);

    if (file.type !== "application/pdf") {
      setError("Choose a PDF file.");
      return;
    }
    if (file.size === 0) {
      setError("The PDF file is empty.");
      return;
    }
    if (file.size > PDF_MAX_BYTES) {
      setError("The PDF file must be 10 MiB or smaller.");
      return;
    }

    try {
      await upload.mutateAsync({
        resourceId: item.id,
        data: { file },
      });
      if (inputRef.current) {
        inputRef.current.value = "";
      }
      await invalidate();
    } catch (caught) {
      setError(contentMutationError(caught, "resource"));
    }
  }

  return (
    <section className="rounded-xl border bg-card p-5">
      <h2 className="font-heading text-lg font-bold">PDF file</h2>
      {item.has_file ? (
        <div className="mt-3 rounded-lg bg-muted p-3">
          <p className="break-words text-sm font-semibold">
            {item.original_filename || "Attached PDF"}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{formatFileSize(item.size_bytes)}</p>
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">No PDF attached yet.</p>
      )}

      <p className="mt-3 text-xs text-muted-foreground">PDF only · Maximum 10 MiB</p>

      {item.status === "DRAFT" ? (
        <>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="sr-only"
            disabled={disabled || upload.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void attach(file);
              }
            }}
          />
          <Button
            className="mt-4"
            variant="outline"
            disabled={disabled || upload.isPending}
            onClick={() => inputRef.current?.click()}
          >
            <FileUp aria-hidden="true" className="size-4" />
            {upload.isPending
              ? "Uploading PDF…"
              : item.has_file
                ? "Replace PDF"
                : "Choose PDF"}
          </Button>
          {item.has_file ? (
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              A PDF has already been attached to this draft. You can replace the PDF while it
              remains a draft, but the resource type can no longer be changed.
            </p>
          ) : null}
        </>
      ) : item.status === "PUBLISHED" ? (
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          Published PDF files cannot be replaced. Archive this resource and create a new one if
          the document itself must be replaced.
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>
      ) : null}
    </section>
  );
}

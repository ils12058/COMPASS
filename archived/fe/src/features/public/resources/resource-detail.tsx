"use client";

import { Download, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { MarkdownContent } from "@/features/public/components/markdown-content";
import { formatPublicDate, isUuid, labelFromEnum, safePublicUrl } from "@/features/public/utils";
import { CompassApiError } from "@/lib/api/client";
import { useResourcesGetPublic, resourcesDownloadPublicFile } from "@/lib/api/generated/resources/resources";

export function ResourceDetail({ resourceId }: { resourceId: string }) {
  const validId = isUuid(resourceId);
  const query = useResourcesGetPublic(resourceId, {
    query: {
      enabled: validId,
      retry: false,
      refetchOnWindowFocus: false,
    },
  });
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const notFound =
    !validId || (query.error instanceof CompassApiError && query.error.status === 404);

  async function downloadFile() {
    setDownloadError(null);
    setDownloading(true);

    try {
      const response = await resourcesDownloadPublicFile(resourceId);
      const url = safePublicUrl(response.data.url);
      if (!url || !/^https?:\/\//i.test(url)) {
        setDownloadError("The download link could not be opened safely.");
        return;
      }
      window.location.assign(url);
    } catch (error) {
      if (error instanceof CompassApiError && error.status === 404) {
        setDownloadError("This file is no longer available publicly.");
      } else {
        setDownloadError("The file could not be prepared for download. Please try again.");
      }
    } finally {
      setDownloading(false);
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto w-full max-w-3xl px-5 py-14 sm:px-8">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">Resources</p>
        <h1 className="mt-2 font-heading text-4xl font-bold">Resource not found</h1>
        <p className="mt-3 text-muted-foreground">This resource is not available publicly.</p>
        <Link href="/resources" className="mt-6 inline-flex font-semibold">
          Back to resources
        </Link>
      </div>
    );
  }

  if (query.isPending) {
    return (
      <div className="mx-auto w-full max-w-3xl px-5 py-14 sm:px-8">
        <p role="status" className="text-sm text-muted-foreground">
          Loading resource…
        </p>
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div className="mx-auto w-full max-w-3xl px-5 py-14 sm:px-8">
        <h1 className="font-heading text-3xl font-bold">Resource unavailable</h1>
        <p role="alert" className="mt-3 text-muted-foreground">
          This resource could not be loaded right now.
        </p>
        <button
          type="button"
          className="mt-5 text-sm font-semibold text-primary underline underline-offset-4"
          onClick={() => query.refetch()}
        >
          Try again
        </button>
      </div>
    );
  }

  const resource = query.data.data;
  const externalUrl = resource.kind === "EXTERNAL_LINK" ? safePublicUrl(resource.external_url) : null;

  return (
    <article className="mx-auto w-full max-w-3xl px-5 py-10 sm:px-8">
      <Link href="/resources" className="text-sm font-semibold">
        ← Resources
      </Link>
      <header className="mt-6 border-b pb-6">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">
          {labelFromEnum(resource.kind)} · {labelFromEnum(resource.category)}
        </p>
        <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight">{resource.title}</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Published {formatPublicDate(resource.published_at)}
        </p>
      </header>

      <div className="pt-4">
        <MarkdownContent source={resource.body_markdown} />
      </div>

      {resource.kind === "EXTERNAL_LINK" ? (
        externalUrl && /^https?:\/\//i.test(externalUrl) ? (
          <a
            href={externalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-6 inline-flex min-h-10 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground no-underline"
          >
            Open resource
            <ExternalLink aria-hidden="true" className="size-4" />
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        ) : (
          <p className="mt-6 text-sm text-destructive" role="alert">
            The external resource link is unavailable.
          </p>
        )
      ) : null}

      {resource.kind === "FILE" ? (
        <div className="mt-6">
          <Button onClick={downloadFile} disabled={downloading}>
            <Download aria-hidden="true" className="size-4" />
            {downloading ? "Preparing download…" : "Download PDF"}
          </Button>
          {downloadError ? (
            <p className="mt-3 text-sm text-destructive" role="alert" aria-live="polite">
              {downloadError}
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

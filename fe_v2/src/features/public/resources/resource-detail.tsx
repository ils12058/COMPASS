"use client";

import { ArrowLeft, Download, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { CompassApiError } from "@/lib/api/client";
import { MarkdownContent } from "@/features/public/components/markdown-content";
import { formatPublicDate, isUuid, labelFromEnum, safePublicUrl } from "@/features/public/utils";
import { useResourcesGetPublic, resourcesDownloadPublicFile } from "@/lib/api/generated/resources/resources";
import { ResourceKindValue as ResourceKinds } from "@/lib/api/generated/model";

export function ResourceDetail({ resourceId }: { resourceId: string }) {
  const validId = isUuid(resourceId);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const query = useResourcesGetPublic(resourceId, {
    query: {
      enabled: validId,
      retry: false,
      refetchOnWindowFocus: false,
    },
  });
  const resource = query.data?.data;
  const notFound = !validId || (query.error instanceof CompassApiError && query.error.status === 404);

  async function handleDownload() {
    if (!resource || resource.kind !== ResourceKinds.FILE) {
      return;
    }

    setDownloading(true);
    setDownloadError(null);

    try {
      const response = await resourcesDownloadPublicFile(resource.id);
      const url = safePublicUrl(response.data.url);

      if (!url || !/^https?:\/\//i.test(url)) {
        throw new Error("The download link is invalid.");
      }

      window.location.assign(url);
    } catch (error) {
      setDownloadError(
        error instanceof CompassApiError && [404, 409, 503].includes(error.status)
          ? "This file is not available for download right now."
          : "We could not prepare the file for download. Please try again.",
      );
    } finally {
      setDownloading(false);
    }
  }

  if (notFound) {
    return (
      <div className="public-shell landing-section">
        <Link className="landing-heading-link" href="/resources">
          <ArrowLeft aria-hidden="true" />
          Back to resources
        </Link>
        <div className="landing-data-state mt-6">
          <h1 className="font-heading text-2xl font-bold text-[var(--compass-brand-maroon-strong)]">
            Resource not found
          </h1>
          <p className="mt-2">This resource is no longer available.</p>
        </div>
      </div>
    );
  }

  if (query.isPending) {
    return (
      <div className="public-shell landing-section">
        <p role="status" className="landing-data-state">
          Loading resource…
        </p>
      </div>
    );
  }

  if (query.isError || !resource) {
    return (
      <div className="public-shell landing-section">
        <Link className="landing-heading-link" href="/resources">
          <ArrowLeft aria-hidden="true" />
          Back to resources
        </Link>
        <div className="landing-data-state mt-6">
          <h1 className="font-heading text-2xl font-bold text-[var(--compass-brand-maroon-strong)]">
            Resource unavailable
          </h1>
          <p className="mt-2">We couldn’t load this resource right now. Please try again.</p>
          <Button type="button" variant="link" className="mt-3 h-auto p-0" onClick={() => void query.refetch()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  const publishedDate = formatPublicDate(resource.published_at);
  const externalUrl = safePublicUrl(resource.external_url);
  const externalHref = externalUrl && /^https?:\/\//i.test(externalUrl) ? externalUrl : null;

  return (
    <div className="public-shell landing-section">
      <Link className="landing-heading-link" href="/resources">
        <ArrowLeft aria-hidden="true" />
        Back to resources
      </Link>

      <article className="landing-paper-sheet mt-6" data-tone="plain">
        <header className="border-b border-[var(--compass-border)] pb-5">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{labelFromEnum(resource.kind)}</span>
            <span aria-hidden="true">·</span>
            <span>{labelFromEnum(resource.category)}</span>
            <span aria-hidden="true">·</span>
            <time dateTime={resource.published_at}>{publishedDate || "Published"}</time>
          </div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-[var(--compass-brand-maroon-strong)] md:text-4xl">
            {resource.title}
          </h1>
        </header>

        <MarkdownContent source={resource.body_markdown} className="mt-6 max-w-3xl text-base" />

        {resource.kind === ResourceKinds.EXTERNAL_LINK && externalHref ? (
          <div className="mt-8">
            <Button asChild variant="outline">
              <a href={externalHref} target="_blank" rel="noopener noreferrer">
                Visit resource
                <ExternalLink aria-hidden="true" />
              </a>
            </Button>
          </div>
        ) : null}

        {resource.kind === ResourceKinds.FILE ? (
          <div className="mt-8">
            <Button type="button" variant="default" onClick={() => void handleDownload()} disabled={downloading}>
              <Download aria-hidden="true" />
              {downloading ? "Preparing download…" : "Download file"}
            </Button>
            {downloadError ? (
              <p role="alert" className="mt-2 text-sm text-destructive">
                {downloadError}
              </p>
            ) : null}
          </div>
        ) : null}
      </article>
    </div>
  );
}

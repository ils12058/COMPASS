"use client";

import { useMutation } from "@tanstack/react-query";
import { ExternalLink, FileDown } from "lucide-react";
import Link from "next/link";

import { ResourceIcon } from "@/features/public/resources/resource-icon";
import { PublicMarkdown } from "@/features/public/shared/public-markdown";
import {
  formatPublicDate,
  getSafeHttpUrl,
  resourceCategoryLabels,
  resourceKindLabels,
} from "@/features/public/shared/presentation";
import { PublicListSkeleton, PublicSectionError } from "@/features/public/shared/public-state";
import { CompassApiError } from "@/lib/api/errors";
import {
  resourcesDownloadPublicFile,
  useResourcesGetPublic,
} from "@/lib/api/generated/resources/resources";
import { ResourceKindValue } from "@/lib/api/generated/model";

export function ResourceDetail({ resourceId }: { resourceId: string }) {
  const query = useResourcesGetPublic(resourceId);
  const download = useMutation({
    mutationFn: async () => {
      const response = await resourcesDownloadPublicFile(resourceId);
      const safeUrl = getSafeHttpUrl(response.data.url);
      if (!safeUrl) throw new Error("The download link returned by the service is not valid.");
      return safeUrl;
    },
    onSuccess: (url) => window.location.assign(url),
  });

  if (query.isPending) return <PublicListSkeleton rows={5} />;

  if (query.isError) {
    if (query.error instanceof CompassApiError && query.error.status === 404) {
      return (
        <div className="border-y border-border py-8">
          <h1 className="font-heading text-3xl font-bold text-ink">Resource not found</h1>
          <p className="mt-3 leading-7 text-muted">
            This resource does not exist or is no longer publicly available.
          </p>
          <Link className="mt-5 inline-flex min-h-10 items-center font-semibold text-brand hover:underline" href="/resources">
            Return to resources
          </Link>
        </div>
      );
    }

    return (
      <PublicSectionError
        message="This resource could not be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const resource = query.data.data;
  const externalUrl = resource.kind === ResourceKindValue.EXTERNAL_LINK
    ? getSafeHttpUrl(resource.external_url)
    : null;

  return (
    <article aria-busy={query.isFetching}>
      <div className="border-b border-border pb-7">
        <div className="flex items-start gap-4">
          <span className="mt-1 text-support-strong"><ResourceIcon kind={resource.kind} size={26} /></span>
          <div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
              <span>{resourceCategoryLabels[resource.category]}</span>
              <span aria-hidden="true">·</span>
              <span>{resourceKindLabels[resource.kind]}</span>
              <span aria-hidden="true">·</span>
              <time dateTime={resource.published_at}>{formatPublicDate(resource.published_at)}</time>
            </div>
            <h1 className="mt-3 font-heading text-4xl font-bold leading-tight tracking-tight text-ink sm:text-5xl">
              {resource.title}
            </h1>
          </div>
        </div>
      </div>

      <div className="mt-8">
        <PublicMarkdown>{resource.body_markdown}</PublicMarkdown>
      </div>

      {resource.kind === ResourceKindValue.EXTERNAL_LINK ? (
        <div className="mt-8 border-t border-border pt-6">
          {externalUrl ? (
            <a
              href={externalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center gap-2 rounded-md bg-brand px-5 py-2.5 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Open resource
              <ExternalLink size={18} aria-hidden="true" />
            </a>
          ) : (
            <p className="text-sm text-danger">The external resource link is unavailable.</p>
          )}
        </div>
      ) : null}

      {resource.kind === ResourceKindValue.FILE ? (
        <div className="mt-8 border-t border-border pt-6">
          <button
            type="button"
            disabled={download.isPending}
            onClick={() => download.mutate()}
            className="inline-flex min-h-11 items-center gap-2 rounded-md bg-brand px-5 py-2.5 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FileDown size={18} aria-hidden="true" />
            {download.isPending ? "Preparing download…" : "Download resource"}
          </button>
          {download.isError ? (
            <p role="alert" className="mt-3 text-sm text-danger">
              The download could not be prepared. Please try again.
            </p>
          ) : null}
        </div>
      ) : null}

      {query.isFetching ? <p role="status" className="mt-6 text-xs text-muted">Refreshing resource…</p> : null}
    </article>
  );
}

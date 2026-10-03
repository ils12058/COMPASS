"use client";

import { useMutation } from "@tanstack/react-query";
import { ExternalLink, FileDown } from "lucide-react";
import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelFooter } from "@/components/ui/panel";
import { ResourceIcon } from "@/features/public/resources/resource-icon";
import { PublicMarkdown } from "@/features/public/shared/public-markdown";
import {
  formatPublicDate,
  getSafeHttpUrl,
  resourceCategoryLabels,
  resourceKindLabels,
} from "@/features/public/shared/presentation";
import { PublicListSkeleton, PublicPageError } from "@/features/public/shared/public-state";
import {
  isSignedOutError,
  useReaderAudience,
  useSessionRecheck,
} from "@/features/public/shared/use-reader-audience";
import { CompassApiError } from "@/lib/api/errors";
import {
  resourcesDownloadPublicFile,
  resourcesDownloadVisibleFile,
  useResourcesGetPublic,
  useResourcesGetVisible,
} from "@/lib/api/generated/resources/resources";
import { ResourceKindValue } from "@/lib/api/generated/model";

export function ResourceDetail({ resourceId }: { resourceId: string }) {
  const audience = useReaderAudience();
  const account = useResourcesGetVisible(resourceId, {
    query: { enabled: audience === "account", retry: false },
  });
  const signedOut = isSignedOutError(account.error);
  useSessionRecheck(signedOut);
  const readsAccount = audience === "account" && !signedOut;
  const publicQuery = useResourcesGetPublic(resourceId, {
    query: { enabled: audience === "public" || signedOut },
  });
  const query = readsAccount ? account : publicQuery;
  const download = useMutation({
    mutationFn: async () => {
      // Restricted files are available only through the account download.
      const response = readsAccount
        ? await resourcesDownloadVisibleFile(resourceId)
        : await resourcesDownloadPublicFile(resourceId);
      const safeUrl = getSafeHttpUrl(response.data.url);
      if (!safeUrl) throw new Error("The download link returned by the service is not valid.");
      return safeUrl;
    },
    onSuccess: (url) => window.location.assign(url),
  });

  if (audience === "pending" || query.isPending) return <PublicListSkeleton rows={5} />;

  if (query.isError) {
    if (query.error instanceof CompassApiError && query.error.status === 404) {
      return (
        <Notice title={<h1 className="font-heading text-2xl font-bold text-ink">Resource not found</h1>}>
          {readsAccount ? (
            <p>This resource does not exist or is not available to your account.</p>
          ) : (
            <>
              <p>This resource does not exist or is no longer publicly available.</p>
              <p className="mt-2">
                If it was shared with COMPASS account holders,{" "}
                <Link href="/login" className="font-semibold text-brand underline">
                  sign in
                </Link>{" "}
                and open it again.
              </p>
            </>
          )}
        </Notice>
      );
    }

    return (
      <PublicPageError
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
    <Panel as="article" aria-busy={query.isFetching}>
      <header className="border-b border-brand-line px-5 py-5 sm:px-8 sm:py-6">
        <div className="flex items-start gap-4">
          <span className="mt-1 text-support-strong"><ResourceIcon kind={resource.kind} size={24} /></span>
          <div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
              <span>{resourceCategoryLabels[resource.category]}</span>
              <span aria-hidden="true">·</span>
              <span>{resourceKindLabels[resource.kind]}</span>
              <span aria-hidden="true">·</span>
              <time dateTime={resource.published_at}>{formatPublicDate(resource.published_at)}</time>
            </div>
            <h1 className="mt-2 font-heading text-3xl font-bold leading-tight tracking-tight text-ink sm:text-4xl">
              {resource.title}
            </h1>
          </div>
        </div>
      </header>

      <div className="px-5 py-6 sm:px-8 sm:py-7">
        <PublicMarkdown>{resource.body_markdown}</PublicMarkdown>
      </div>

      {resource.kind === ResourceKindValue.EXTERNAL_LINK ? (
        <PanelFooter className="px-5 py-4 sm:px-8">
          {externalUrl ? (
            <a
              href={externalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "primary", className: "min-h-11 px-5 py-2.5" })}
            >
              Open resource
              <ExternalLink size={18} aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          ) : (
            <p className="text-sm text-danger">The external resource link is unavailable.</p>
          )}
        </PanelFooter>
      ) : null}

      {resource.kind === ResourceKindValue.FILE ? (
        <PanelFooter className="px-5 py-4 sm:px-8">
          <Button
            disabled={download.isPending}
            onClick={() => download.mutate()}
            className="min-h-11 px-5 py-2.5"
          >
            <FileDown size={18} aria-hidden="true" />
            {download.isPending ? "Preparing download…" : "Download resource"}
          </Button>
          {download.isError ? (
            <p role="alert" className="w-full text-sm text-danger">
              The download could not be prepared. Please try again.
            </p>
          ) : null}
        </PanelFooter>
      ) : null}

      {query.isFetching ? <p role="status" className="border-t border-border px-5 py-2 text-xs text-muted sm:px-8">Refreshing resource…</p> : null}
    </Panel>
  );
}

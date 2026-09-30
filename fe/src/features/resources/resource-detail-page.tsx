"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { displayTitle, publicationAudienceLabels } from "@/features/content/content-presentation";
import {
  ContentDetailSkeleton,
  ContentNotice,
  ContentPageHeading,
  ContentQueryError,
  PublicationStatusBadge,
  contentSecondaryLinkClass,
} from "@/features/content/content-shared";
import { PublicMarkdown } from "@/features/public/shared/public-markdown";
import {
  getSafeHttpUrl,
  resourceCategoryLabels,
  resourceKindLabels,
} from "@/features/public/shared/presentation";
import { resourceErrorCode, resourceErrorMessage, shouldHideResourceData } from "@/features/resources/resource-errors";
import { ResourceFileSection } from "@/features/resources/resource-file-section";
import { ResourceLifecycleActions } from "@/features/resources/resource-lifecycle-actions";
import { joinList, missingForPublication } from "@/features/resources/resource-presentation";
import { useResourcesGetManaged } from "@/lib/api/generated/resources/resources";
import { ResourceAudienceValue, ResourceKindValue, ResourceStatusValue } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 break-words text-sm text-ink">{children}</dd>
    </div>
  );
}

export function ResourceUnavailable({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const notFound = resourceErrorCode(error) === "resource_not_found";
  return (
    <section className="space-y-6">
      <ContentPageHeading
        title={notFound ? "Resource not found" : "Resource unavailable"}
        backHref="/portal/resources"
        backLabel="Resources"
      />
      {notFound ? (
        <p className="border-y border-border py-6 text-sm leading-6 text-muted">
          This Resource does not exist or is no longer available.
        </p>
      ) : (
        <ContentQueryError
          message={resourceErrorMessage(error, "This Resource could not be loaded.")}
          onRetry={shouldHideResourceData(error) ? undefined : onRetry}
        />
      )}
    </section>
  );
}

export function ResourceDetailPage({ resourceId }: { resourceId: string }) {
  const searchParams = useSearchParams();
  const detail = useResourcesGetManaged(resourceId, { query: { retry: false } });
  const [notice, setNotice] = useState<string | null>(() =>
    searchParams.get("notice") === "created" ? "Draft saved." : null,
  );

  if (detail.isPending) return <ContentDetailSkeleton label="Loading Resource…" />;
  if (!detail.data || (detail.isError && shouldHideResourceData(detail.error))) {
    return <ResourceUnavailable error={detail.error} onRetry={() => void detail.refetch()} />;
  }

  const item = detail.data.data;
  const title = displayTitle(item.title, "Untitled Resource");
  const isDraft = item.status === ResourceStatusValue.DRAFT;
  const missing = isDraft ? missingForPublication(item) : [];
  const externalUrl = getSafeHttpUrl(item.external_url);

  return (
    <article aria-busy={detail.isFetching}>
      <ContentPageHeading
        title={title}
        backHref="/portal/resources"
        backLabel="Resources"
        action={
          <>
            {item.status !== ResourceStatusValue.ARCHIVED ? (
              <Link href={`/portal/resources/${item.id}/edit`} className={contentSecondaryLinkClass}>
                Edit Resource
              </Link>
            ) : null}
            <ResourceLifecycleActions resource={item} publishBlocked={missing.length > 0} onCompleted={setNotice} />
          </>
        }
      >
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted">
          <PublicationStatusBadge status={item.status} />
          <span>{resourceKindLabels[item.kind]}</span>
          <span>{resourceCategoryLabels[item.category]}</span>
          <span>{publicationAudienceLabels[item.audience]}</span>
        </div>
      </ContentPageHeading>

      <div className="mt-6 space-y-3">
        {notice ? <ContentNotice tone="success">{notice}</ContentNotice> : null}
        {missing.length > 0 ? (
          <ContentNotice tone="warning">
            Add {joinList(missing)} before publishing.
          </ContentNotice>
        ) : null}
        {detail.isError ? (
          <ContentQueryError
            message={`${resourceErrorMessage(detail.error, "The latest Resource details could not be loaded.")} Showing the last loaded version.`}
            onRetry={() => void detail.refetch()}
          />
        ) : detail.isFetching ? (
          <p role="status" className="text-xs text-muted">Refreshing Resource…</p>
        ) : null}
      </div>

      <dl className="mt-6 grid gap-x-8 gap-y-4 border-y border-border py-5 sm:grid-cols-2 lg:grid-cols-3">
        <Detail label="Type">{resourceKindLabels[item.kind]}</Detail>
        <Detail label="Category">{resourceCategoryLabels[item.category]}</Detail>
        <Detail label="Audience">{publicationAudienceLabels[item.audience]}</Detail>
        <Detail label="Display order">{item.display_order}</Detail>
        {item.kind === ResourceKindValue.EXTERNAL_LINK ? (
          <Detail label="Link address">
            {externalUrl ? (
              <a
                href={externalUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="break-all font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                {externalUrl}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
            ) : (
              "Not added"
            )}
          </Detail>
        ) : null}
        <Detail label="Published">
          {item.published_at
            ? `${formatInstitutionalDateTime(item.published_at)}${item.published_by ? ` by ${item.published_by.display_name}` : ""}`
            : "Not published"}
        </Detail>
        <Detail label="Created">
          {formatInstitutionalDateTime(item.created_at)} by {item.created_by.display_name}
        </Detail>
        <Detail label="Last updated">
          {formatInstitutionalDateTime(item.updated_at)} by {item.updated_by.display_name}
        </Detail>
      </dl>

      {item.status === ResourceStatusValue.PUBLISHED && item.audience === ResourceAudienceValue.PUBLIC ? (
        <p className="mt-4 text-sm">
          <Link
            href={`/resources/${item.id}`}
            className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Open the public Resource page
          </Link>
        </p>
      ) : null}

      {item.kind === ResourceKindValue.FILE ? <ResourceFileSection key={item.status} resource={item} /> : null}

      <section aria-labelledby="resource-body-heading" className="mt-8 border-t border-border pt-6">
        <h2 id="resource-body-heading" className="font-heading text-xl font-semibold text-ink">Body</h2>
        <p className="mt-1 text-sm text-muted">As readers see it.</p>
        <div className="mt-4 max-w-3xl rounded-md border border-border bg-surface-raised px-5 py-5 sm:px-6">
          {item.body_markdown.trim() ? (
            <PublicMarkdown>{item.body_markdown}</PublicMarkdown>
          ) : (
            <p className="text-sm text-muted">No body text yet.</p>
          )}
        </div>
      </section>
    </article>
  );
}

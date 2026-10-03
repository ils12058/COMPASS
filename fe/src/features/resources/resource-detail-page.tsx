"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Notice } from "@/components/ui/notice";
import { Panel, PanelSection } from "@/components/ui/panel";
import { displayTitle, publicationAudienceLabels } from "@/features/content/content-presentation";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
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
    <section className="space-y-5">
      <ContentPageHeading
        title={notFound ? "Resource not found" : "Resource unavailable"}
        backHref="/portal/resources"
        backLabel="Resources"
      />
      {notFound ? (
        <Notice>
          This Resource does not exist or is no longer available.
        </Notice>
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
  if (!detail.data || (detail.isError && !canShowLastKnownData(detail))) {
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
        action={!detail.isError ?
          <>
            {item.status !== ResourceStatusValue.ARCHIVED ? (
              <Link href={`/portal/resources/${item.id}/edit`} className={contentSecondaryLinkClass}>
                Edit Resource
              </Link>
            ) : null}
            <ResourceLifecycleActions resource={item} publishBlocked={missing.length > 0} onCompleted={setNotice} />
          </>
        : null}
      >
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted">
          <PublicationStatusBadge status={item.status} />
          <span>{resourceKindLabels[item.kind]}</span>
          <span>{resourceCategoryLabels[item.category]}</span>
          <span>{publicationAudienceLabels[item.audience]}</span>
        </div>
      </ContentPageHeading>

      <div className="mt-5 space-y-3 empty:hidden">
        {notice ? <ContentNotice tone="success">{notice}</ContentNotice> : null}
        {missing.length > 0 ? (
          <ContentNotice tone="warning">
            Add {joinList(missing)} before publishing.
          </ContentNotice>
        ) : null}
        {detail.isError ? (
          <RefreshFailureNotice onRetry={() => void detail.refetch()} retrying={detail.isFetching} />
        ) : detail.isFetching ? (
          <p role="status" className="text-xs text-muted">Refreshing Resource…</p>
        ) : null}
      </div>

      {/* The record sheet: publication facts, then the file and body as readers get them. */}
      <Panel as="div" className="mt-5">
      <dl className="grid gap-x-8 gap-y-4 px-4 py-4 sm:grid-cols-2 sm:px-5 lg:grid-cols-3">
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
        <p className="border-t border-brand-line px-4 py-3 text-sm sm:px-5">
          <Link
            href={`/resources/${item.id}`}
            className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Open the public Resource page
          </Link>
        </p>
      ) : null}

      {item.kind === ResourceKindValue.FILE ? <ResourceFileSection key={item.status} resource={item} /> : null}

      <PanelSection title="Body" titleId="resource-body-heading">
        <p className="text-sm text-muted">As readers see it.</p>
        <div className="mt-4 max-w-3xl">
          {item.body_markdown.trim() ? (
            <PublicMarkdown>{item.body_markdown}</PublicMarkdown>
          ) : (
            <p className="text-sm text-muted">No body text yet.</p>
          )}
        </div>
      </PanelSection>
      </Panel>
    </article>
  );
}

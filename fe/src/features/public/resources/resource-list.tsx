"use client";

import { keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Panel, PanelMessage } from "@/components/ui/panel";

import { ResourceFilters } from "@/features/public/resources/resource-filters";
import { ResourceIcon } from "@/features/public/resources/resource-icon";
import {
  formatPublicDate,
  markdownPreview,
  resourceCategoryLabels,
  resourceKindLabels,
} from "@/features/public/shared/presentation";
import { PublicPagination } from "@/features/public/shared/public-pagination";
import { PublicRowsSkeleton, PublicSectionError } from "@/features/public/shared/public-state";
import {
  isSignedOutError,
  useReaderAudience,
  useSessionRecheck,
} from "@/features/public/shared/use-reader-audience";
import { useResourcesListPublic, useResourcesListVisible } from "@/lib/api/generated/resources/resources";
import type { ResourceCategoryValue, ResourceKindValue } from "@/lib/api/generated/model";

type ResourceListProps =
  | { mode: "preview" }
  | {
      mode: "index";
      category?: ResourceCategoryValue;
      kind?: ResourceKindValue;
      search?: string;
      page: number;
    };

export function ResourceList(props: ResourceListProps) {
  const isPreview = props.mode === "preview";
  const category = isPreview ? undefined : props.category;
  const kind = isPreview ? undefined : props.kind;
  const search = isPreview ? undefined : props.search;
  const page = isPreview ? 1 : props.page;
  const detailParams = new URLSearchParams();
  if (search) detailParams.set("search", search);
  if (category) detailParams.set("category", category);
  if (kind) detailParams.set("kind", kind);
  if (!isPreview && page > 1) detailParams.set("page", String(page));
  const detailQuery = detailParams.toString();
  const params = { category, kind, ...(search ? { search } : {}), page, page_size: isPreview ? 3 : 9 };
  const audience = useReaderAudience();
  const account = useResourcesListVisible(params, {
    query: { enabled: audience === "account", placeholderData: keepPreviousData, retry: false },
  });
  const signedOut = isSignedOutError(account.error);
  useSessionRecheck(signedOut);
  const readsAccount = audience === "account" && !signedOut;
  const publicQuery = useResourcesListPublic(params, {
    query: { enabled: audience === "public" || signedOut, placeholderData: keepPreviousData },
  });
  const query = readsAccount ? account : publicQuery;
  const loading = audience === "pending" || query.isPending;

  const buildPageHref = (nextPage: number) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (category) params.set("category", category);
    if (kind) params.set("kind", kind);
    params.set("page", String(nextPage));
    return `/resources?${params.toString()}`;
  };

  const filtered = Boolean(search || category || kind);
  let content: ReactNode = null;

  if (loading) {
    content = <PublicRowsSkeleton rows={isPreview ? 3 : 6} label="Loading resources…" />;
  } else if (query.isError) {
    content = (
      <PublicSectionError
        message={readsAccount ? "Resources could not be loaded." : "Public resources could not be loaded."}
        onRetry={() => void query.refetch()}
      />
    );
  } else if (query.isSuccess && query.data.data.items.length === 0) {
    content = (
      <PanelMessage
        action={filtered ? (
          <Link className={buttonVariants({ variant: "secondary" })} href="/resources">
            Clear filters
          </Link>
        ) : undefined}
      >
        {filtered
          ? search
            ? category || kind
              ? "No resources match this search and the selected filters."
              : "No resources match this search."
            : readsAccount
            ? "No resources match the selected filters."
            : "No public resources match the selected filters."
          : readsAccount
            ? "No resources are available right now."
            : "No public resources are available right now."}
      </PanelMessage>
    );
  } else if (query.isSuccess) {
    content = (
      <div aria-busy={query.isFetching}>
        <ul className="divide-y divide-border">
          {query.data.data.items.map((resource) => {
            const preview = isPreview ? null : markdownPreview(resource.body_markdown);

            return (
              <li key={resource.id}>
                <Link
                  href={`/resources/${resource.id}${detailQuery ? `?${detailQuery}` : ""}`}
                  className="group grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-3 px-4 py-3.5 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:grid-cols-[1.5rem_minmax(0,1fr)_auto] sm:gap-x-4 sm:px-5"
                >
                  <span className="pt-0.5 text-support-strong">
                    <ResourceIcon kind={resource.kind} size={18} />
                  </span>
                  <span className="min-w-0">
                    <span className="block font-semibold leading-6 text-ink transition-colors group-hover:text-brand">
                      {resource.title}
                    </span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs font-semibold text-support-strong">
                      <span>{resourceKindLabels[resource.kind]}</span>
                      <span aria-hidden="true" className="text-border-strong">·</span>
                      <span>{resourceCategoryLabels[resource.category]}</span>
                    </span>
                    {preview ? (
                      <span className="mt-1.5 line-clamp-2 text-sm leading-6 text-muted">{preview}</span>
                    ) : null}
                  </span>
                  <time
                    dateTime={resource.published_at}
                    className="col-start-2 mt-1 text-xs text-muted sm:col-start-auto sm:mt-0.5 sm:whitespace-nowrap"
                  >
                    {formatPublicDate(resource.published_at)}
                  </time>
                </Link>
              </li>
            );
          })}
        </ul>

        {query.isFetching && !query.isPending ? (
          <p role="status" className="border-t border-border px-4 py-2 text-xs text-muted sm:px-5">Refreshing resources…</p>
        ) : null}

        {!isPreview ? (
          <PublicPagination
            page={query.data.data.page}
            hasNext={query.data.data.has_next}
            buildHref={buildPageHref}
          />
        ) : null}
      </div>
    );
  }

  // The landing page's preview panel brings its own title band; the index page adds its filters
  // and frames the list here.
  if (isPreview) return content;

  return (
    <div className="grid gap-5">
      <ResourceFilters search={search} category={category} kind={kind} />
      <Panel as="div">{content}</Panel>
    </div>
  );
}

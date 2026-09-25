"use client";

import { keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";

import { ResourceFilters } from "@/features/public/resources/resource-filters";
import { ResourceIcon } from "@/features/public/resources/resource-icon";
import {
  formatPublicDate,
  resourceCategoryLabels,
  resourceKindLabels,
} from "@/features/public/shared/presentation";
import { PublicPagination } from "@/features/public/shared/public-pagination";
import { PublicListSkeleton, PublicSectionError } from "@/features/public/shared/public-state";
import { useResourcesListPublic } from "@/lib/api/generated/resources/resources";
import type { ResourceCategoryValue, ResourceKindValue } from "@/lib/api/generated/model";

type ResourceListProps =
  | { mode: "preview" }
  | {
      mode: "index";
      category?: ResourceCategoryValue;
      kind?: ResourceKindValue;
      page: number;
    };

export function ResourceList(props: ResourceListProps) {
  const isPreview = props.mode === "preview";
  const category = isPreview ? undefined : props.category;
  const kind = isPreview ? undefined : props.kind;
  const page = isPreview ? 1 : props.page;
  const query = useResourcesListPublic(
    { category, kind, page, page_size: isPreview ? 4 : 8 },
    { query: { placeholderData: keepPreviousData } },
  );

  const buildPageHref = (nextPage: number) => {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (kind) params.set("kind", kind);
    params.set("page", String(nextPage));
    return `/resources?${params.toString()}`;
  };

  return (
    <div>
      {!isPreview ? <ResourceFilters category={category} kind={kind} /> : null}

      {query.isPending ? <PublicListSkeleton rows={isPreview ? 4 : 6} /> : null}

      {query.isError ? (
        <PublicSectionError
          message="Public resources could not be loaded."
          onRetry={() => void query.refetch()}
        />
      ) : null}

      {query.isSuccess && query.data.data.items.length === 0 ? (
        <div className="border-y border-border py-6">
          <p className="text-sm leading-6 text-muted">
            {category || kind
              ? "No public resources match the selected filters."
              : "No public resources are available right now."}
          </p>
          {category || kind ? (
            <Link className="mt-3 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href="/resources">
              Clear filters
            </Link>
          ) : null}
        </div>
      ) : null}

      {query.isSuccess && query.data.data.items.length > 0 ? (
        <div aria-busy={query.isFetching}>
          <ul className={isPreview ? "grid gap-x-10 md:grid-cols-2" : "divide-y divide-border border-y border-border"}>
            {query.data.data.items.map((resource) => (
              <li key={resource.id} className={isPreview ? "border-t border-border first:border-t-0 md:[&:nth-child(2)]:border-t-0" : undefined}>
                <Link
                  href={`/resources/${resource.id}`}
                  className="group grid grid-cols-[1.5rem_1fr] gap-4 py-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  <span className="pt-1 text-support-strong">
                    <ResourceIcon kind={resource.kind} />
                  </span>
                  <span>
                    <span className="font-heading text-lg font-semibold leading-6 text-ink transition-colors group-hover:text-brand">
                      {resource.title}
                    </span>
                    <span className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
                      <span>{resourceCategoryLabels[resource.category]}</span>
                      <span aria-hidden="true">·</span>
                      <span>{resourceKindLabels[resource.kind]}</span>
                      <span aria-hidden="true">·</span>
                      <time dateTime={resource.published_at}>{formatPublicDate(resource.published_at)}</time>
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>

          {query.isFetching && !query.isPending ? (
            <p role="status" className="mt-3 text-xs text-muted">Refreshing resources…</p>
          ) : null}

          {!isPreview ? (
            <PublicPagination
              page={query.data.data.page}
              hasNext={query.data.data.has_next}
              buildHref={buildPageHref}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

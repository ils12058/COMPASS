"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ResourceCardSkeleton } from "@/features/public/components/public-content-skeletons";
import { PublicContentPagination } from "@/features/public/components/public-content-pagination";
import { ResourceCard } from "@/features/public/components/resource-card";
import { labelFromEnum } from "@/features/public/utils";
import type { ResourceCategoryValue, ResourceKindValue } from "@/lib/api/generated/model";
import {
  ResourceCategoryValue as ResourceCategories,
  ResourceKindValue as ResourceKinds,
} from "@/lib/api/generated/model";
import { useResourcesListPublic } from "@/lib/api/generated/resources/resources";

const PAGE_SIZE = 10;

export function ResourcesIndex() {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<ResourceCategoryValue | "">("");
  const [kind, setKind] = useState<ResourceKindValue | "">("");
  const query = useResourcesListPublic(
    {
      page,
      page_size: PAGE_SIZE,
      category: category || undefined,
      kind: kind || undefined,
    },
    { query: { retry: 1, refetchOnWindowFocus: false } },
  );
  const items = query.data?.data?.items ?? [];

  return (
    <div className="public-shell landing-section" aria-labelledby="resources-page-heading">
      <header className="mb-8 space-y-2">
        <h1 id="resources-page-heading" className="font-heading text-4xl font-bold tracking-tight">
          Resources
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          Guides, links, and downloadable materials to support UCNians in their studies, wellbeing,
          and next steps.
        </p>
      </header>

      <div className="mb-6 flex flex-wrap gap-3 rounded-xl border bg-card p-4">
        <label className="grid gap-1 text-sm font-semibold">
          Category
          <select
            className="min-h-10 rounded-lg border bg-white px-3 text-sm font-normal"
            value={category}
            onChange={(event) => {
              setCategory(event.target.value as ResourceCategoryValue | "");
              setPage(1);
            }}
          >
            <option value="">All categories</option>
            {Object.values(ResourceCategories).map((value) => (
              <option key={value} value={value}>
                {labelFromEnum(value)}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-1 text-sm font-semibold">
          Type
          <select
            className="min-h-10 rounded-lg border bg-white px-3 text-sm font-normal"
            value={kind}
            onChange={(event) => {
              setKind(event.target.value as ResourceKindValue | "");
              setPage(1);
            }}
          >
            <option value="">All types</option>
            {Object.values(ResourceKinds).map((value) => (
              <option key={value} value={value}>
                {labelFromEnum(value)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {query.isFetching && query.data ? (
        <p role="status" className="mb-4 text-sm text-muted-foreground">
          Updating resources…
        </p>
      ) : null}

      {query.isPending ? (
        <div className="grid gap-4 md:grid-cols-2" role="status" aria-busy="true">
          <span className="sr-only">Loading resources…</span>
          {Array.from({ length: 6 }, (_, index) => (
            <ResourceCardSkeleton key={index} />
          ))}
        </div>
      ) : query.isError ? (
        <div className="landing-data-state">
          <p role="alert">We couldn’t load resources right now. Please try again.</p>
          <Button
            type="button"
            variant="link"
            className="mt-3 h-auto p-0"
            onClick={() => void query.refetch()}
          >
            Try again
          </Button>
        </div>
      ) : items.length === 0 ? (
        <p className="landing-data-state">No resources match your filters.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <ResourceCard key={item.id} resource={item} />
          ))}
        </div>
      )}

      {query.data ? (
        <div className="mt-8">
          <PublicContentPagination
            page={page}
            hasNext={query.data.data.has_next}
            onPageChange={setPage}
          />
        </div>
      ) : null}
    </div>
  );
}

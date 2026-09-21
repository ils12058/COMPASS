"use client";

import { useState } from "react";

import { PublicContentPagination } from "@/features/public/components/public-content-pagination";
import { ResourceCard } from "@/features/public/components/resource-card";
import type { ResourceCategoryValue, ResourceKindValue } from "@/lib/api/generated/model";
import {
  ResourceCategoryValue as ResourceCategories,
  ResourceKindValue as ResourceKinds,
} from "@/lib/api/generated/model";
import { useResourcesListPublic } from "@/lib/api/generated/resources/resources";
import { labelFromEnum } from "@/features/public/utils";

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

  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-10 sm:px-8">
      <header className="mb-8 space-y-2">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">
          Guidance and Counseling Office
        </p>
        <h1 className="font-heading text-4xl font-bold tracking-tight">Resources</h1>
        <p className="max-w-2xl text-muted-foreground">
          Public articles, links, and downloadable materials curated by the Guidance and
          Counseling Office.
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

      {query.isPending ? (
        <p role="status" className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">
          Loading resources…
        </p>
      ) : query.isError ? (
        <div className="rounded-xl border bg-card p-6">
          <p role="alert" className="text-sm text-muted-foreground">
            Resources are temporarily unavailable.
          </p>
          <button
            type="button"
            className="mt-3 text-sm font-semibold text-primary underline underline-offset-4"
            onClick={() => query.refetch()}
          >
            Try again
          </button>
        </div>
      ) : query.data.data.items.length === 0 ? (
        <p className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">
          No public resources match these filters.
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {query.data.data.items.map((item) => (
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

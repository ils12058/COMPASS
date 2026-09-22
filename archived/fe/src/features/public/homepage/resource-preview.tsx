"use client";

import Link from "next/link";

import { ResourceCard } from "@/features/public/components/resource-card";
import { useResourcesListPublic } from "@/lib/api/generated/resources/resources";

export function ResourcePreview() {
  const query = useResourcesListPublic(
    { page: 1, page_size: 3 },
    { query: { retry: 1, refetchOnWindowFocus: false } },
  );

  return (
    <section className="bg-[var(--compass-surface-subtle)]">
      <div className="mx-auto w-full max-w-7xl px-5 py-12 sm:px-8" aria-labelledby="resources-heading">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-[var(--compass-brand-gold)]">Useful reading</p>
            <h2 id="resources-heading" className="mt-1 font-heading text-3xl font-bold">
              Resources
            </h2>
          </div>
          <Link href="/resources" className="text-sm font-semibold">
            Browse all resources
          </Link>
        </div>

        {query.isPending ? (
          <p role="status" className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">
            Loading resources…
          </p>
        ) : query.isError ? (
          <p role="status" className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">
            Resources are temporarily unavailable. You can still use the rest of this site.
          </p>
        ) : query.data.data.items.length === 0 ? (
          <p className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">
            There are no public resources right now.
          </p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {query.data.data.items.map((item) => (
              <ResourceCard key={item.id} resource={item} compact />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

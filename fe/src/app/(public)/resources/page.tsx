import type { Metadata } from "next";

import { ResourceList } from "@/features/public/resources/resource-list";
import { PublicPageHeader } from "@/features/public/shared/public-page-header";
import { isResourceCategory, isResourceKind } from "@/features/public/shared/presentation";
import { readOrdering } from "@/features/portal/components/list-ordering-params";
import { ResourceOrdering } from "@/lib/api/generated/model";

export const metadata: Metadata = { title: "Resources" };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function readPage(value: string | string[] | undefined): number {
  const parsed = Number(first(value));
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export default async function ResourcesPage({
  searchParams,
}: {
  searchParams: Promise<{
    category?: string | string[];
    kind?: string | string[];
    page?: string | string[];
    search?: string | string[];
    ordering?: string | string[];
  }>;
}) {
  const params = await searchParams;
  const categoryValue = first(params.category);
  const kindValue = first(params.kind);
  const category = isResourceCategory(categoryValue) ? categoryValue : undefined;
  const kind = isResourceKind(kindValue) ? kindValue : undefined;

  return (
    <main>
      <PublicPageHeader
        illustration={{ src: "/illustrations/gco-character-point-right.png", width: 338, height: 330 }}
      >
        <h1 className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">Resources</h1>
      </PublicPageHeader>
      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8 sm:py-9">
        <ResourceList
          mode="index"
          category={category}
          kind={kind}
          search={first(params.search)?.trim() || undefined}
          ordering={readOrdering(first(params.ordering) ?? null, ResourceOrdering)}
          page={readPage(params.page)}
        />
      </div>
    </main>
  );
}

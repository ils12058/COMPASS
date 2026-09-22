import type { Metadata } from "next";

import { ResourceList } from "@/features/public/resources/resource-list";
import { PublicPageHeader } from "@/features/public/shared/public-page-header";
import { isResourceCategory, isResourceKind } from "@/features/public/shared/presentation";

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
  }>;
}) {
  const params = await searchParams;
  const categoryValue = first(params.category);
  const kindValue = first(params.kind);
  const category = isResourceCategory(categoryValue) ? categoryValue : undefined;
  const kind = isResourceKind(kindValue) ? kindValue : undefined;

  return (
    <main>
      <PublicPageHeader>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-ink">Resources</h1>
      </PublicPageHeader>
      <div className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
        <ResourceList mode="index" category={category} kind={kind} page={readPage(params.page)} />
      </div>
    </main>
  );
}

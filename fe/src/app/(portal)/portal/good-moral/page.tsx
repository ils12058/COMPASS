import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { GoodMoralWorkspacePage } from "@/features/good-moral/good-moral-page";
import type { GoodMoralOperationalFilters } from "@/features/good-moral/good-moral-operational-list";
import { GoodMoralStatusValue, GoodMoralVariantValue } from "@/lib/api/generated/model";

type SearchValue = string | string[] | undefined;

function singleValue(value: SearchValue): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function positiveInteger(value: string): number | undefined {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function pageNumber(value: string): number {
  return positiveInteger(value) ?? 1;
}

export const metadata: Metadata = { title: "Good Moral" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, SearchValue>>;
}) {
  const query = await searchParams;
  const variantValue = singleValue(query.variant);
  const statusValue = singleValue(query.status);
  const filters: GoodMoralOperationalFilters = {
    search: singleValue(query.search),
    variant: variantValue === GoodMoralVariantValue.CURRENT_STUDENT || variantValue === GoodMoralVariantValue.GRADUATE
      ? variantValue
      : "",
    status: statusValue === GoodMoralStatusValue.REQUESTED || statusValue === GoodMoralStatusValue.ISSUED || statusValue === GoodMoralStatusValue.CANCELLED
      ? statusValue
      : "",
    page: pageNumber(singleValue(query.page)),
    pageSize: positiveInteger(singleValue(query.page_size)),
  };

  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <GoodMoralWorkspacePage key={JSON.stringify(filters)} filters={filters} />
    </Suspense>
  );
}

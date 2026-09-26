import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ReferralsPage, type ReferralListFilters } from "@/features/referrals/referrals-page";

type SearchValue = string | string[] | undefined;

function singleValue(value: SearchValue): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function pageNumber(value: string): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export const metadata: Metadata = { title: "Referrals" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, SearchValue>>;
}) {
  const query = await searchParams;
  const filters: ReferralListFilters = {
    search: singleValue(query.search),
    fromDate: singleValue(query.from_date),
    toDate: singleValue(query.to_date),
    includeVoided: singleValue(query.include_voided) === "true",
    page: pageNumber(singleValue(query.page)),
  };

  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ReferralsPage key={JSON.stringify(filters)} filters={filters} />
    </Suspense>
  );
}

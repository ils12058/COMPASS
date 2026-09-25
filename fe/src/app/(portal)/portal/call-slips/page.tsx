import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { CallSlipsPage, type CallSlipListFilters, type CallSlipStudentListFilters } from "@/features/call-slips/call-slips-page";
import { CallSlipDestinationTypeValue } from "@/lib/api/generated/model";

type SearchValue = string | string[] | undefined;

function singleValue(value: SearchValue): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function pageNumber(value: string): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export const metadata: Metadata = { title: "Call Slips" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, SearchValue>>;
}) {
  const query = await searchParams;
  const destinationValue = singleValue(query.destination);
  const destination = destinationValue === CallSlipDestinationTypeValue.GUIDANCE_OFFICE || destinationValue === CallSlipDestinationTypeValue.OTHER
    ? destinationValue
    : "";
  const page = pageNumber(singleValue(query.page));
  const fromDate = singleValue(query.from_date);
  const toDate = singleValue(query.to_date);
  const operationalFilters: CallSlipListFilters = {
    search: singleValue(query.search),
    destination,
    fromDate,
    toDate,
    includeVoided: singleValue(query.include_voided) === "true",
    page,
  };
  const studentFilters: CallSlipStudentListFilters = { fromDate, toDate, page };

  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <CallSlipsPage key={JSON.stringify([operationalFilters, studentFilters])} operationalFilters={operationalFilters} studentFilters={studentFilters} />
    </Suspense>
  );
}

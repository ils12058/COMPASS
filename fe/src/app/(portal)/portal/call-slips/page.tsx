import type { Metadata } from "next";
import { Suspense } from "react";

import { CallSlipListSkeleton } from "@/features/call-slips/call-slips-shared";
import { CallSlipsPage, type CallSlipListFilters, type CallSlipStudentListFilters } from "@/features/call-slips/call-slips-page";
import { readOrdering } from "@/features/portal/components/list-ordering-params";
import { CallSlipDestinationTypeValue, CallSlipLifecycleStateValue, CallSlipOrdering } from "@/lib/api/generated/model";

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
  const stateValue = singleValue(query.state);
  const state = Object.values(CallSlipLifecycleStateValue).find((value) => value === stateValue) ?? "";
  const page = pageNumber(singleValue(query.page));
  const fromDate = singleValue(query.from_date);
  const toDate = singleValue(query.to_date);
  const operationalFilters: CallSlipListFilters = {
    search: singleValue(query.search),
    formRevisionId: singleValue(query.form_revision_id),
    destination,
    fromDate,
    toDate,
    includeVoided: singleValue(query.include_voided) === "true",
    state,
    ordering: readOrdering(singleValue(query.ordering), CallSlipOrdering),
    page,
  };
  const studentFilters: CallSlipStudentListFilters = { fromDate, toDate, state, page };

  return (
    <Suspense fallback={<CallSlipListSkeleton />}>
      <CallSlipsPage key={JSON.stringify([operationalFilters, studentFilters])} operationalFilters={operationalFilters} studentFilters={studentFilters} />
    </Suspense>
  );
}

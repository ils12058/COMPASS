"use client";

import { useServerBoundary } from "@/features/freshness/use-server-boundary";
import { useReferralsFacultyAvailability } from "@/lib/api/generated/referrals/referrals";
import type { UserSummary } from "@/lib/api/generated/model";

export function useFacultyAvailability(user: UserSummary) {
  const query = useReferralsFacultyAvailability({ query: {
    enabled: user.role === "FACULTY", retry: false, staleTime: 0,
    refetchOnWindowFocus: "always", refetchOnReconnect: "always",
  } });
  useServerBoundary({
    boundary: query.data?.data.valid_until, serverDate: query.data?.headers.date,
    receivedAt: query.dataUpdatedAt, onBoundary: () => { void query.refetch(); },
  });
  // Even a transient availability failure cannot authorize a new consequential request.
  return { ...query, availability: query.isError ? undefined : query.data?.data };
}

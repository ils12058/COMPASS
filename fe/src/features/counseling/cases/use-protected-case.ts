"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useCoveragePrivacy } from "@/features/counseling/coverage/use-coverage-privacy";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { isTransientRefreshError } from "@/features/freshness/query-freshness";
import { counselingGetCase, getCounselingGetCaseQueryKey } from "@/lib/api/generated/counseling/counseling";

// The canonical case response now contains owner-only closure notes. All case readers use the
// existing confidential-content barrier, with the canonical query key so domain invalidation stays
// intact. A hidden/offline/session-changing view discards its data and rejects late responses.
export function useProtectedCase(caseId: string, enabled: boolean) {
  const { user } = usePortalSession();
  const queryKey = useMemo(() => getCounselingGetCaseQueryKey(caseId), [caseId]);
  const [failure, setFailure] = useState<unknown>(null);
  const privacy = useCoveragePrivacy(user.id, caseId, queryKey);
  const query = useQuery({
    queryKey,
    enabled: enabled && !privacy.blocked,
    retry: false,
    gcTime: 0,
    staleTime: 0,
    networkMode: "always",
    refetchInterval: 60_000,
    refetchOnWindowFocus: "always",
    refetchOnReconnect: "always",
    queryFn: async ({ signal }) => {
      const generation = privacy.barrier.current();
      try {
        if (!navigator.onLine || document.visibilityState !== "visible") throw new Error("Protected case access needs another check.");
        const response = await counselingGetCase(caseId, { signal });
        privacy.barrier.assertCurrent(generation, signal);
        if (!navigator.onLine || document.visibilityState !== "visible") throw new Error("Protected case access needs another check.");
        setFailure(null);
        return response;
      } catch (caught) {
        if (!signal.aborted && generation === privacy.barrier.current()) { setFailure(caught); if (!isTransientRefreshError(caught)) privacy.clear(); }
        throw caught;
      }
    },
  });
  return { ...query, queryKey, privacy, failure };
}

import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { isAuthorityError, isMutationAuthorityError, isSessionEndedError } from "@/features/freshness/query-freshness";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { getAuthGetSessionQueryKey } from "@/lib/api/generated/auth/auth";
import { requestSessionRevalidation } from "@/lib/auth/session-revalidation";

const NON_RETRYABLE_STATUSES = new Set([400, 401, 403, 404, 409, 422]);

export function createQueryClient() {
  return new QueryClient({
    queryCache: new QueryCache({
      onError(error, query) {
        if (query.queryKey[0] === getAuthGetSessionQueryKey()[0]) return;
        if (isSessionEndedError(error)) requestSessionRevalidation("session");
        else if (isAuthorityError(error)) requestSessionRevalidation("authority");
      },
    }),
    mutationCache: new MutationCache({
      onError(error) {
        if (isSessionEndedError(error)) requestSessionRevalidation("session");
        else if (isMutationAuthorityError(error)) requestSessionRevalidation("authority");
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry(failureCount, error) {
          if (
            error instanceof CompassApiError &&
            (NON_RETRYABLE_STATUSES.has(error.status) ||
              readApiErrorCode(error.body) === "maintenance_mode")
          ) {
            return false;
          }

          return failureCount < 2;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}

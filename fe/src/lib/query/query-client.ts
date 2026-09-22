import { QueryClient } from "@tanstack/react-query";

import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

const NON_RETRYABLE_STATUSES = new Set([400, 401, 403, 404, 409, 422]);

export function createQueryClient() {
  return new QueryClient({
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

import { QueryClient } from "@tanstack/react-query";

import { CompassApiError } from "@/lib/api/client";

const NON_RETRYABLE_HTTP_STATUSES = new Set([400, 401, 403, 404, 409, 422]);

export function createCompassQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry(failureCount, error) {
          if (
            error instanceof CompassApiError &&
            NON_RETRYABLE_HTTP_STATUSES.has(error.status)
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

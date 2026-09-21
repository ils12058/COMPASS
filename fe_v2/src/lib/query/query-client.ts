import { QueryClient } from "@tanstack/react-query";

import { CompassApiError } from "@/lib/api/client";
import { getStructuredApiErrorCode } from "@/lib/api/error-payload";

const NON_RETRYABLE_HTTP_STATUSES = new Set([400, 401, 403, 404, 409, 422]);

export function createCompassQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        staleTime: 30_000,
        retry(failureCount, error) {
          if (error instanceof CompassApiError) {
            if (NON_RETRYABLE_HTTP_STATUSES.has(error.status)) {
              return false;
            }

            if (getStructuredApiErrorCode(error.data) === "maintenance_mode") {
              return false;
            }
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

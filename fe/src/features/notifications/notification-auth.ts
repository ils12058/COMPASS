import type { QueryClient } from "@tanstack/react-query";

import { CompassApiError } from "@/lib/api/errors";
import { getAuthGetSessionQueryKey } from "@/lib/api/generated/auth/auth";

export function reconcileNotificationAuth(error: unknown, queryClient: QueryClient) {
  if (error instanceof CompassApiError && error.status === 401) {
    void queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() });
  }
}

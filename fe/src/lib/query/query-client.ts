import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { isAuthorityError, isMutationAuthorityError, isSessionEndedError } from "@/features/freshness/query-freshness";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { getAuthGetSessionQueryKey } from "@/lib/api/generated/auth/auth";
import { getPlatformPublicStatusQueryKey } from "@/lib/api/generated/platform-operations/platform-operations";
import { requestSessionRevalidation } from "@/lib/auth/session-revalidation";
import { createAccountOwnership } from "@/lib/query/account-ownership";

const NON_RETRYABLE_STATUSES = new Set([400, 401, 403, 404, 409, 422]);

function isMaintenanceRefusal(error: unknown): boolean {
  return error instanceof CompassApiError && readApiErrorCode(error.body) === "maintenance_mode";
}

function isSessionQuery(query: { queryKey: readonly unknown[] }): boolean {
  return query.queryKey[0] === getAuthGetSessionQueryKey()[0];
}

export function createQueryClient() {
  const ownership = createAccountOwnership({ isSessionQuery });
  // A request refused for Maintenance Mode means the public status may have changed: ask it again
  // now rather than at the next poll. The status endpoint, not the refusal, decides what is shown.
  const refreshMaintenanceStatus = () => {
    void client.refetchQueries(
      { queryKey: getPlatformPublicStatusQueryKey(), exact: true, type: "active" },
      { cancelRefetch: false },
    );
  };
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError(error, query) {
        if (isSessionQuery(query)) return;
        if (isMaintenanceRefusal(error)) refreshMaintenanceStatus();
        else if (isSessionEndedError(error)) requestSessionRevalidation("session");
        else if (isAuthorityError(error)) requestSessionRevalidation("authority");
      },
    }),
    mutationCache: new MutationCache({
      onMutate(_variables, mutation) {
        ownership.mutationStarted(mutation);
      },
      onSuccess(_data, _variables, _onMutateResult, mutation) {
        ownership.assertMutationOwner(mutation);
      },
      onError(error) {
        if (isMaintenanceRefusal(error)) refreshMaintenanceStatus();
        else if (isSessionEndedError(error)) requestSessionRevalidation("session");
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
            (NON_RETRYABLE_STATUSES.has(error.status) || isMaintenanceRefusal(error))
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
  ownership.attach(client);
  return client;
}

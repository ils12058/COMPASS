import type { QueryClient } from "@tanstack/react-query";

import {
  getPlatformOperationsGetMaintenanceQueryKey,
  getPlatformOperationsListActivityQueryKey,
  getPlatformPublicStatusQueryKey,
} from "@/lib/api/generated/platform-operations/platform-operations";

export function refreshMaintenanceQueries(queryClient: QueryClient) {
  void queryClient.invalidateQueries({
    queryKey: getPlatformOperationsGetMaintenanceQueryKey(),
  });
  void queryClient.invalidateQueries({
    queryKey: getPlatformPublicStatusQueryKey(),
  });
  void queryClient.invalidateQueries({
    queryKey: getPlatformOperationsListActivityQueryKey(),
  });
}

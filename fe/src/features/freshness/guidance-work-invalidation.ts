import type { QueryClient } from "@tanstack/react-query";

import { getGuidanceOperationsGetQueryKey } from "@/lib/api/generated/guidance-operations/guidance-operations";
import { getWorkQueueListQueryKey } from "@/lib/api/generated/work/work";

/** Confirmed source changes reconcile these two read-only staff projections over HTTP. */
export function invalidateGuidanceWork(client: Pick<QueryClient, "invalidateQueries">) {
  return Promise.all([
    client.invalidateQueries({ queryKey: getWorkQueueListQueryKey() }),
    client.invalidateQueries({ queryKey: getGuidanceOperationsGetQueryKey() }),
  ]);
}

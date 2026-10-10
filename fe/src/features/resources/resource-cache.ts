import type { QueryClient } from "@tanstack/react-query";

import {
  getResourcesGetManagedQueryKey,
  getResourcesGetPublicQueryKey,
  getResourcesGetVisibleQueryKey,
  getResourcesListManagedQueryKey,
  getResourcesListPublicQueryKey,
  getResourcesListVisibleQueryKey,
  type resourcesGetManagedResponseSuccess,
} from "@/lib/api/generated/resources/resources";

export function storeManagedResource(queryClient: QueryClient, response: resourcesGetManagedResponseSuccess) {
  queryClient.setQueryData(getResourcesGetManagedQueryKey(response.data.id), response);
}

// Reader lists and pages change only when published content changes.
export function refreshResourceQueries(
  queryClient: QueryClient,
  resourceId: string,
  { readers }: { readers: boolean },
) {
  const keys: readonly (readonly unknown[])[] = [
    getResourcesListManagedQueryKey(),
    ...(readers
      ? [
          getResourcesListVisibleQueryKey(),
          getResourcesListPublicQueryKey(),
          getResourcesGetVisibleQueryKey(resourceId),
          getResourcesGetPublicQueryKey(resourceId),
        ]
      : []),
  ];
  return Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}

"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import { AccessibilityPreferencesProvider } from "@/features/accessibility/accessibility-provider";
import { ServiceStatusLayer } from "@/features/system/components/service-status-layer";
import { getPlatformPublicStatusQueryKey } from "@/lib/api/generated/platform-operations/platform-operations";
import type { PlatformPublicStatusResponse } from "@/lib/api/generated/model";
import { createCompassQueryClient } from "@/lib/query/query-client";

export function Providers({
  children,
  initialPlatformStatus,
}: {
  children: ReactNode;
  initialPlatformStatus: PlatformPublicStatusResponse | null;
}) {
  const [queryClient] = useState(() => {
    const client = createCompassQueryClient();

    if (initialPlatformStatus) {
      client.setQueryData(getPlatformPublicStatusQueryKey(), {
        data: initialPlatformStatus,
        status: 200,
        headers: {},
      });
    }

    return client;
  });

  return (
    <AccessibilityPreferencesProvider>
      <QueryClientProvider client={queryClient}>
        <ServiceStatusLayer>{children}</ServiceStatusLayer>
      </QueryClientProvider>
      <AccessibilityControl />
    </AccessibilityPreferencesProvider>
  );
}

"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { AccessibilityPreferencesProvider } from "@/features/accessibility/accessibility-provider";
import { createCompassQueryClient } from "@/lib/query/query-client";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createCompassQueryClient);

  return (
    <AccessibilityPreferencesProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </AccessibilityPreferencesProvider>
  );
}

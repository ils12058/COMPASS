"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { createQueryClient } from "@/lib/query/query-client";
import { ServiceWorkerRegistration } from "@/features/pwa/service-worker-registration";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}><ServiceWorkerRegistration />{children}</QueryClientProvider>
  );
}

"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { createCompassQueryClient } from "@/lib/query/query-client";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createCompassQueryClient);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

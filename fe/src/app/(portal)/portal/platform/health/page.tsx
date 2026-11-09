import type { Metadata } from "next";

export const metadata: Metadata = { title: "Platform health" };

import { PlatformHealthPage } from "@/features/platform/health/platform-health-page";

export default function Page() {
  return <PlatformHealthPage />;
}

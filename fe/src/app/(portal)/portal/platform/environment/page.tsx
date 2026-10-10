import type { Metadata } from "next";

export const metadata: Metadata = { title: "Environment" };

import { PlatformEnvironmentPage } from "@/features/platform/environment/platform-environment-page";

export default function Page() {
  return <PlatformEnvironmentPage />;
}

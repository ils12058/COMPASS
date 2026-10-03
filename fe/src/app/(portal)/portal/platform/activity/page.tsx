import type { Metadata } from "next";

export const metadata: Metadata = { title: "Platform Activity" };

import { PlatformActivityPage } from "@/features/platform/activity/platform-activity-page";

export default function Page() {
  return <PlatformActivityPage />;
}

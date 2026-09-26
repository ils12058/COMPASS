import type { Metadata } from "next";

import { ActivityPage } from "@/features/account/activity/activity-page";

export const metadata: Metadata = { title: "Activity" };

export default function Page() {
  return <ActivityPage />;
}

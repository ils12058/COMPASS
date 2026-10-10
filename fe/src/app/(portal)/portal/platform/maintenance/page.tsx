import type { Metadata } from "next";

export const metadata: Metadata = { title: "Maintenance" };

import { PlatformMaintenancePage } from "@/features/platform/maintenance/platform-maintenance-page";

export default function Page() {
  return <PlatformMaintenancePage />;
}

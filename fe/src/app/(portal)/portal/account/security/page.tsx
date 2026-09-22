import type { Metadata } from "next";

import { SecurityOverview } from "@/features/account/security/security-overview";

export const metadata: Metadata = { title: "Security | COMPASS" };

export default function Page() {
  return <SecurityOverview />;
}

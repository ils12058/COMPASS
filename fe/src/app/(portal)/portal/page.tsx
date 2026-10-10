import type { Metadata } from "next";

import { PortalHome } from "@/features/portal/home/portal-home";

export const metadata: Metadata = { title: "Overview" };

export default function PortalPage() {
  return <PortalHome />;
}

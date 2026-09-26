import type { Metadata } from "next";

import { IncidentCreatePage } from "@/features/privacy-governance/incidents/incident-create-page";

export const metadata: Metadata = { title: "Record privacy incident" };

export default function Page() {
  return <IncidentCreatePage />;
}

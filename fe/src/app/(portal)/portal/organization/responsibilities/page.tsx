import { OrganizationRelationshipsGate } from "@/features/organization/components/organization-gate";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Responsibilities" };

import { ResponsibilitiesPage } from "@/features/organization/responsibilities/responsibilities-page";

export default function Page() {
  return <OrganizationRelationshipsGate><ResponsibilitiesPage /></OrganizationRelationshipsGate>;
}

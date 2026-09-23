import type { ReactNode } from "react";

import { OrganizationGate } from "@/features/organization/components/organization-gate";
import { OrganizationNavigation } from "@/features/organization/components/organization-navigation";

export default function OrganizationLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <OrganizationGate>
      <OrganizationNavigation />
      {children}
    </OrganizationGate>
  );
}

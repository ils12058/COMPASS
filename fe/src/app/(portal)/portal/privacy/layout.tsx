import type { Metadata } from "next";
import type { ReactNode } from "react";

import { PrivacyGovernanceGate } from "@/features/privacy-governance/privacy-governance-gate";
import { PrivacyGovernanceNavigation } from "@/features/privacy-governance/privacy-governance-navigation";

export const metadata: Metadata = { title: "Privacy Governance" };

export default function PrivacyGovernanceLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <PrivacyGovernanceGate>
      <PrivacyGovernanceNavigation />
      {children}
    </PrivacyGovernanceGate>
  );
}

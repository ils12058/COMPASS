import type { Metadata } from "next";

import { RetentionPoliciesPage } from "@/features/privacy-governance/retention/retention-policies-page";

export const metadata: Metadata = { title: "Retention Policies" };

export default function Page() {
  return <RetentionPoliciesPage />;
}

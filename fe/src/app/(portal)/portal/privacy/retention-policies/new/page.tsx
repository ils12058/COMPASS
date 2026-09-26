import type { Metadata } from "next";

import { RetentionPolicyCreatePage } from "@/features/privacy-governance/retention-policies/retention-policy-create-page";

export const metadata: Metadata = { title: "Create retention policy" };

export default function Page() {
  return <RetentionPolicyCreatePage />;
}

import type { Metadata } from "next";

import { ProcessingActivityCreatePage } from "@/features/privacy-governance/processing-activities/processing-activity-create-page";

export const metadata: Metadata = { title: "Create processing activity" };

export default function Page() {
  return <ProcessingActivityCreatePage />;
}

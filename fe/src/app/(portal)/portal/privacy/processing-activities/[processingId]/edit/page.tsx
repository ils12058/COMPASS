import type { Metadata } from "next";

import { ProcessingActivityEditPage } from "@/features/privacy-governance/processing-activities/processing-activity-edit-page";

export const metadata: Metadata = { title: "Edit processing activity" };

export default function Page() {
  return <ProcessingActivityEditPage />;
}

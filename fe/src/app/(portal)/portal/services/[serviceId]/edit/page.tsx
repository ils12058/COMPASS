import type { Metadata } from "next";

export const metadata: Metadata = { title: "Edit Service" };

import { EditServicePage } from "@/features/services/service-editor-page";

export default function Page() {
  return <EditServicePage />;
}

import type { Metadata } from "next";

export const metadata: Metadata = { title: "Create Service" };

import { CreateServicePage } from "@/features/services/service-editor-page";

export default function Page() {
  return <CreateServicePage />;
}

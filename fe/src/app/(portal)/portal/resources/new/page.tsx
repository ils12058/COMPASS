import type { Metadata } from "next";

import { ResourceCreatePage } from "@/features/resources/resource-create-page";

export const metadata: Metadata = { title: "Create Resource" };

export default function Page() {
  return <ResourceCreatePage />;
}

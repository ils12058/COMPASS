import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { ResourceCreatePage } from "@/features/resources/resource-create-page";

export const metadata: Metadata = { title: "Create Resource" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <ResourceCreatePage />
    </div>
  );
}

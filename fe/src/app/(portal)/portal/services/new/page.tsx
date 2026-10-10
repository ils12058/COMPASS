import type { Metadata } from "next";

export const metadata: Metadata = { title: "Create Service" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { CreateServicePage } from "@/features/services/service-editor-page";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <CreateServicePage />
    </div>
  );
}

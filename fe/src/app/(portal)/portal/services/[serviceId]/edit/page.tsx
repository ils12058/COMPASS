import type { Metadata } from "next";

export const metadata: Metadata = { title: "Edit Service" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { EditServicePage } from "@/features/services/service-editor-page";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <EditServicePage />
    </div>
  );
}

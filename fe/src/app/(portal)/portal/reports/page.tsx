import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { ReportsIndex } from "@/features/reports/reports-index";

export const metadata: Metadata = { title: "Reports" };

export default function ReportsPage() {
  return (
    <div className={pageSheetWidth}>
      <ReportsIndex />
    </div>
  );
}

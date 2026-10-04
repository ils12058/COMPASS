import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { AcademicYearsPage } from "@/features/institution-configuration/academic-years-page";

export const metadata: Metadata = { title: "Academic Years" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <AcademicYearsPage />
    </div>
  );
}

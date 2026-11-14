import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { StudentAcademicRosterImportGate } from "@/features/organization/components/organization-gate";
import { GraduationImportPage } from "@/features/student-academics/roster-import/graduation-import";

export const metadata: Metadata = { title: "Import graduations" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <StudentAcademicRosterImportGate>
        <GraduationImportPage />
      </StudentAcademicRosterImportGate>
    </div>
  );
}

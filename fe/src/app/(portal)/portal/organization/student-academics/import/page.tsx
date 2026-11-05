import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { StudentAcademicRosterImportGate } from "@/features/organization/components/organization-gate";
import { RosterImportPage } from "@/features/student-academics/roster-import/roster-import";

export const metadata: Metadata = { title: "Import Academic Roster" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <StudentAcademicRosterImportGate>
        <RosterImportPage />
      </StudentAcademicRosterImportGate>
    </div>
  );
}

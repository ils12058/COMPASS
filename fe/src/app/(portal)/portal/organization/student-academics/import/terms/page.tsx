import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { StudentAcademicRosterImportGate } from "@/features/organization/components/organization-gate";
import { TermRecordsImportPage } from "@/features/student-academics/roster-import/term-records-import";

export const metadata: Metadata = { title: "Import term records" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <StudentAcademicRosterImportGate>
        <TermRecordsImportPage />
      </StudentAcademicRosterImportGate>
    </div>
  );
}

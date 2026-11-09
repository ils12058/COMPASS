import { StudentAcademicRecordsGate } from "@/features/organization/components/organization-gate";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Student academic records" };

import { Suspense } from "react";

import { TableSkeleton } from "@/features/organization/components/organization-shared";
import { StudentAcademicRecordsPage } from "@/features/student-academics/student-academic-records/student-academic-records-page";

export default function Page() {
  return (
    <Suspense fallback={<TableSkeleton label="Loading Student placements…" framed />}>
      <StudentAcademicRecordsGate><StudentAcademicRecordsPage /></StudentAcademicRecordsGate>
    </Suspense>
  );
}

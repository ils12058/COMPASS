import type { Metadata } from "next";
import { Suspense } from "react";

import { pageSheetWidth } from "@/components/ui/page-width";
import { StudentAcademicRecordsGate } from "@/features/organization/components/organization-gate";
import { TableSkeleton } from "@/features/organization/components/organization-shared";
import { StudentAcademicRecordPage } from "@/features/student-academics/student-academic-record/student-academic-record-page";

export const metadata: Metadata = { title: "Student Academic Record" };

export default async function Page({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = await params;
  return (
    <div className={pageSheetWidth}>
      <StudentAcademicRecordsGate>
        <Suspense fallback={<TableSkeleton label="Loading Student academic record…" />}>
          <StudentAcademicRecordPage studentId={studentId} />
        </Suspense>
      </StudentAcademicRecordsGate>
    </div>
  );
}

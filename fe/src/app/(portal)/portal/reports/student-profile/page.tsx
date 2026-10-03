import type { Metadata } from "next";

export const metadata: Metadata = { title: "Student Profile Report" };

import { Suspense } from "react";

import { ReportsLoading } from "@/features/reports/reports-shared";
import { StudentProfileReportPage } from "@/features/reports/student-profile-report-page";

export default function StudentProfilePage() {
  return (
    <Suspense fallback={<ReportsLoading title="Student Profiling" />}>
      <StudentProfileReportPage />
    </Suspense>
  );
}

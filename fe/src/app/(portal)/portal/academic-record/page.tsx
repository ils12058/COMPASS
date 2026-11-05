import { MyAcademicRecordGate } from "@/features/organization/components/organization-gate";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Academic Record" };

import { Suspense } from "react";

import { TableSkeleton } from "@/features/organization/components/organization-shared";
import { MyAcademicRecordPage } from "@/features/student-academics/my-academic-record/my-academic-record-page";

export default function Page() {
  return (
    <Suspense fallback={<TableSkeleton label="Loading your academic record…" framed />}>
      <MyAcademicRecordGate><MyAcademicRecordPage /></MyAcademicRecordGate>
    </Suspense>
  );
}

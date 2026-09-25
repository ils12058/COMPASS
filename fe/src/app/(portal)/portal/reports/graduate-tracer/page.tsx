import { Suspense } from "react";

import { ReportsLoading } from "@/features/reports/reports-shared";
import { GraduateTracerReportPage } from "@/features/reports/graduate-tracer-report-page";

export default function GraduateTracerPage() {
  return (
    <Suspense fallback={<ReportsLoading title="Graduate Tracer" />}>
      <GraduateTracerReportPage />
    </Suspense>
  );
}

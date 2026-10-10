import { Suspense } from "react";
import { AssessmentListPage } from "@/features/assessment-records/assessment-records-list";
import { AssessmentLoading } from "@/features/assessment-records/assessment-records-shared";
export default function Page() {
  return (
    <Suspense fallback={<AssessmentLoading />}>
      <AssessmentListPage />
    </Suspense>
  );
}

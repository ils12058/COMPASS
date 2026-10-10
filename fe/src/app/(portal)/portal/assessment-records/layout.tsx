import type { ReactNode } from "react";
import { AssessmentGate } from "@/features/assessment-records/assessment-records-shared";
export default function Layout({ children }: { children: ReactNode }) {
  return <AssessmentGate>{children}</AssessmentGate>;
}

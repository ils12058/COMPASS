import type { Metadata } from "next";

import { AcademicYearsPage } from "@/features/institution-configuration/academic-years-page";

export const metadata: Metadata = { title: "Academic Years" };

export default function Page() {
  return <AcademicYearsPage />;
}

import { OrganizationRelationshipsGate } from "@/features/organization/components/organization-gate";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Student Affiliations" };

import { Suspense } from "react";

import { TableSkeleton } from "@/features/organization/components/organization-shared";
import { StudentAffiliationsPage } from "@/features/organization/student-affiliations/student-affiliations-page";

export default function Page() {
  return (
    <Suspense fallback={<TableSkeleton label="Loading student affiliations…" framed />}>
      <OrganizationRelationshipsGate><StudentAffiliationsPage /></OrganizationRelationshipsGate>
    </Suspense>
  );
}

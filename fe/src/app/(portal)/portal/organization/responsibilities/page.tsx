import type { Metadata } from "next";

export const metadata: Metadata = { title: "Responsibilities" };

import { ResponsibilitiesPage } from "@/features/organization/responsibilities/responsibilities-page";

export default function Page() {
  return <ResponsibilitiesPage />;
}

import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { InstitutionalFormsPage } from "@/features/institution-configuration/institutional-forms-page";

type InstitutionalFormsRouteProps = {
  searchParams: Promise<{ family?: string | string[] }>;
};

export const metadata: Metadata = { title: "Institutional Forms" };

export default async function Page({
  searchParams,
}: InstitutionalFormsRouteProps) {
  const params = await searchParams;
  const family = Array.isArray(params.family)
    ? params.family[0]
    : params.family;

  return (

    <div className={pageSheetWidth}>

      <InstitutionalFormsPage requestedFamily={family} />

    </div>

  );
}

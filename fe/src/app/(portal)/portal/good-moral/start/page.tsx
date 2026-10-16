import type { Metadata } from "next";
import { pageSheetWidth } from "@/components/ui/page-width";
import { GoodMoralAssistedRequestPage } from "@/features/good-moral/good-moral-assisted-request-page";

export const metadata: Metadata = { title: "Start Good Moral request for Student" };

export default function Page() {
  return <div className={pageSheetWidth}><GoodMoralAssistedRequestPage /></div>;
}

import type { Metadata } from "next";
import { pageSheetWidth } from "@/components/ui/page-width";
import { GoodMoralAssistedRequestPage } from "@/features/good-moral/good-moral-assisted-request-page";

export const metadata: Metadata = { title: "Start a Good Moral Certificate request" };

export default function Page() {
  return <div className={pageSheetWidth}><GoodMoralAssistedRequestPage /></div>;
}

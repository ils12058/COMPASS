import type { Metadata } from "next";

export const metadata: Metadata = { title: "Request Good Moral Certificate" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { GoodMoralRequestPage } from "@/features/good-moral/good-moral-request-page";

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <GoodMoralRequestPage />
    </div>
  );
}

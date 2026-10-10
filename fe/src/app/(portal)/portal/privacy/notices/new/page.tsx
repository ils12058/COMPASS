import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { NoticeCreatePage } from "@/features/privacy-governance/notices/notice-create-page";

export const metadata: Metadata = { title: "Create privacy notice" };

export default function Page() {
  return (
    <div className={pageSheetWidth}>
      <NoticeCreatePage />
    </div>
  );
}

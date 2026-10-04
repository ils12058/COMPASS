import type { Metadata } from "next";

export const metadata: Metadata = { title: "Current Individual Inventory" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { CurrentInventoryPage } from "@/features/inventory/student/current-inventory-page";

export default function CurrentInventoryRoute() {
  return (
    <div className={pageSheetWidth}>
      <CurrentInventoryPage />
    </div>
  );
}

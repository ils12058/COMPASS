import type { Metadata } from "next";

export const metadata: Metadata = { title: "Inventory History" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { InventoryHistoryDetail } from "@/features/inventory/student/inventory-history-detail";

export default async function InventoryHistoryPage({
  params,
}: {
  params: Promise<{ inventoryId: string }>;
}) {
  const { inventoryId } = await params;
  return (
    <div className={pageSheetWidth}>
      <InventoryHistoryDetail inventoryId={inventoryId} />
    </div>
  );
}

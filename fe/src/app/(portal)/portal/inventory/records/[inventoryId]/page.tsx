import type { Metadata } from "next";

export const metadata: Metadata = { title: "Inventory Record" };

import { pageSheetWidth } from "@/components/ui/page-width";
import { InventoryRecordDetail } from "@/features/inventory/counselor/inventory-record-detail";

export default async function InventoryRecordPage({
  params,
}: {
  params: Promise<{ inventoryId: string }>;
}) {
  const { inventoryId } = await params;
  return (
    <div className={pageSheetWidth}>
      <InventoryRecordDetail inventoryId={inventoryId} />
    </div>
  );
}

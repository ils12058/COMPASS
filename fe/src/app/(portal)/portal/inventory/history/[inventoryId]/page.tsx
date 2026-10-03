import type { Metadata } from "next";

export const metadata: Metadata = { title: "Inventory History" };

import { InventoryHistoryDetail } from "@/features/inventory/student/inventory-history-detail";

export default async function InventoryHistoryPage({
  params,
}: {
  params: Promise<{ inventoryId: string }>;
}) {
  const { inventoryId } = await params;
  return <InventoryHistoryDetail inventoryId={inventoryId} />;
}

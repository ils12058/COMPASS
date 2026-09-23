import { InventoryRecordDetail } from "@/features/inventory/counselor/inventory-record-detail";

export default async function InventoryRecordPage({
  params,
}: {
  params: Promise<{ inventoryId: string }>;
}) {
  const { inventoryId } = await params;
  return <InventoryRecordDetail inventoryId={inventoryId} />;
}

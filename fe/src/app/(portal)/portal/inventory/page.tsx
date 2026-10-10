import type { Metadata } from "next";

import { InventoryHome } from "@/features/inventory/inventory-home";

export const metadata: Metadata = { title: "Individual Inventory" };

export default function InventoryPage() {
  return <InventoryHome />;
}

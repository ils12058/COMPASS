import type { Metadata } from "next";

import { pageSheetWidth } from "@/components/ui/page-width";
import { NotificationCenter } from "@/features/notifications/notification-center/notification-center";

export const metadata: Metadata = { title: "Notifications" };

function safePage(value: string | string[] | undefined): number {
  const parsed = Number(Array.isArray(value) ? value[0] : value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

export default async function Page({ searchParams }: { searchParams: Promise<{ page?: string | string[] }> }) {
  const { page } = await searchParams;
  return (
    <div className={pageSheetWidth}>
      <NotificationCenter page={safePage(page)} />
    </div>
  );
}

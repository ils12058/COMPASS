import type { Metadata } from "next";

import { NotificationCenter } from "@/features/notifications/notification-center/notification-center";

export const metadata: Metadata = { title: "Notifications | COMPASS" };

function safePage(value: string | string[] | undefined): number {
  const parsed = Number(Array.isArray(value) ? value[0] : value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

export default async function Page({ searchParams }: { searchParams: Promise<{ page?: string | string[] }> }) {
  const { page } = await searchParams;
  return <NotificationCenter page={safePage(page)} />;
}

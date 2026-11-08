import type { Metadata } from "next";
import { Suspense } from "react";

import { RemindersPage, RemindersSkeleton } from "@/features/reminders/reminders-page";

export const metadata: Metadata = { title: "Reminders" };

export default function Page() {
  return (
    <Suspense fallback={<RemindersSkeleton />}>
      <RemindersPage />
    </Suspense>
  );
}

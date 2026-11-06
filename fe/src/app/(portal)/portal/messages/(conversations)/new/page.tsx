import type { Metadata } from "next";
import { Suspense } from "react";

import { GuidanceNewMessage } from "@/features/guidance-messages/guidance-new-message";

export const metadata: Metadata = { title: "New message" };

export default function Page() {
  return (
    <Suspense fallback={<p role="status" className="px-4 py-3 text-sm text-muted">Loading…</p>}>
      <GuidanceNewMessage />
    </Suspense>
  );
}

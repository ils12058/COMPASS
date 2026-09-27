import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AnnouncementsGate } from "@/features/announcements/announcements-gate";

export const metadata: Metadata = {
  title: { default: "Announcements", template: "%s | COMPASS" },
};

export default function AnnouncementsLayout({ children }: { children: ReactNode }) {
  return <AnnouncementsGate>{children}</AnnouncementsGate>;
}

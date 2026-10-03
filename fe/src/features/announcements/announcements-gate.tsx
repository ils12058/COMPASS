"use client";

import type { ReactNode } from "react";

import { canManageAnnouncements } from "@/features/announcements/announcements-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";

export function AnnouncementsGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canManageAnnouncements(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Announcements unavailable">
      Announcement management is unavailable to this account.
    </WorkspaceUnavailable>
  );
}

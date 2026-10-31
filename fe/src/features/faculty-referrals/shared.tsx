"use client";

import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { facultyReferralAccess } from "./access";

export function FacultyReferralGate({ submit = false, children }: { submit?: boolean; children: ReactNode }) {
  const { user } = usePortalSession();
  const access = facultyReferralAccess(user);
  return (submit ? access.submit : access.read) ? children
    : <WorkspaceUnavailable title="Faculty Referrals unavailable">This account cannot open this Faculty workspace.</WorkspaceUnavailable>;
}

export function FacultyUnavailable({ onRetry }: { onRetry?: () => void }) {
  return <Notice title="Digital Referrals are not available yet." action={onRetry ? <Button variant="secondary" onClick={onRetry}>Check availability</Button> : undefined}>
    You can continue to use Notifications and your Profile.
  </Notice>;
}

export function FacultyLoading({ label = "Loading Faculty Referrals…" }: { label?: string }) {
  return <RowsSkeleton label={label} rows={3} framed />;
}

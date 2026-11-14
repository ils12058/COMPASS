"use client";

import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { CounselingUnavailable } from "@/features/counseling/counseling-shared";
import { CounselorEncounters } from "@/features/counseling/counselor-encounters";
import { usePortalSession } from "@/features/portal/components/portal-session";

// Every session the Counselor recorded, whether or not it is in a case. Sessions recorded before
// cases existed stay here until the Counselor adds them to one.
export function SessionRecordsPage() {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  if (!access.canViewAssigned) return <CounselingUnavailable title="Session records" />;
  return <CounselorEncounters access={access} />;
}

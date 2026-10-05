"use client";

import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { GoodMoralCounselorDetail } from "@/features/good-moral/good-moral-counselor-detail";
import { GoodMoralStudentDetail } from "@/features/good-moral/good-moral-student-detail";
import { GoodMoralUnavailable } from "@/features/good-moral/good-moral-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function GoodMoralDetailPage({ requestId }: { requestId: string }) {
  const { user } = usePortalSession();
  const access = getGoodMoralAccess(user);

  if (access.isStudent) {
    if (!access.canViewSelf) {
      return <GoodMoralUnavailable title="Request unavailable" message="Good Moral request details are unavailable to this account." />;
    }
    return <GoodMoralStudentDetail requestId={requestId} canCancel={access.canRequestSelf} />;
  }

  if (access.hasOperationalWorkspace) {
    if (!access.canViewOperational) {
      return <GoodMoralUnavailable title="Request unavailable" message="This Good Moral request is unavailable to you." />;
    }
    return <GoodMoralCounselorDetail requestId={requestId} canManage={access.canManageOperational} canIssue={access.canIssue} canPrepare={access.canPrepare} />;
  }

  return <GoodMoralUnavailable title="Request unavailable" message="Good Moral request details are unavailable to this account." />;
}

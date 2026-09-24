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
      return <GoodMoralUnavailable title="Request unavailable" message="Your current access does not allow you to view Good Moral request details." />;
    }
    return <GoodMoralStudentDetail requestId={requestId} canCancel={access.canRequestSelf} />;
  }

  if (access.isCounselor) {
    if (!access.canViewOperational) {
      return <GoodMoralUnavailable title="Request unavailable" message="Your Counselor account does not have Good Moral request-view access." />;
    }
    return <GoodMoralCounselorDetail requestId={requestId} canManage={access.canManageOperational} canIssue={access.canIssue} />;
  }

  return <GoodMoralUnavailable title="Request unavailable" message="Your current access does not include Good Moral request details." />;
}

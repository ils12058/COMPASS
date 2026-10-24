"use client";

import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { GoodMoralCounselorDetail } from "@/features/good-moral/good-moral-counselor-detail";
import { GoodMoralStudentDetail } from "@/features/good-moral/good-moral-student-detail";
import { GoodMoralUnavailable } from "@/features/good-moral/good-moral-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function GoodMoralDetailPage({ requestId }: { requestId: string }) {
  const { user, session } = usePortalSession();
  const owner = `${user.id}:${session?.id ?? ""}:${user.role}:${user.capabilities.filter(code => code.startsWith("good_moral.")).sort().join(",")}`;
  const access = getGoodMoralAccess(user);

  if (access.isStudent) {
    if (!access.canViewSelf) {
      return <GoodMoralUnavailable title="Request unavailable" message="This Good Moral request is unavailable." />;
    }
    return <GoodMoralStudentDetail key={`${owner}:${requestId}`} requestId={requestId} canCancel={access.canRequestSelf} />;
  }

  if (access.hasOperationalWorkspace) {
    if (!access.canViewOperational) {
      return <GoodMoralUnavailable title="Request unavailable" message="This Good Moral request is unavailable to you." />;
    }
    return <GoodMoralCounselorDetail key={`${owner}:${requestId}`} requestId={requestId} canManage={access.canManageOperational} canIssue={access.canIssue} canPrepare={access.canPrepare} />;
  }

  return <GoodMoralUnavailable title="Request unavailable" message="This Good Moral request is unavailable." />;
}

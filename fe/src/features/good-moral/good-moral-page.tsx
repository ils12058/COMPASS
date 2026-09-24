"use client";

import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import type { GoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { GoodMoralOperationalFilters, GoodMoralOperationalList } from "@/features/good-moral/good-moral-operational-list";
import { GoodMoralStudentHistory } from "@/features/good-moral/good-moral-student-history";
import { GoodMoralUnavailable } from "@/features/good-moral/good-moral-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function GoodMoralWorkspacePage({ filters }: { filters: GoodMoralOperationalFilters }) {
  const { user } = usePortalSession();
  const access: GoodMoralAccess = getGoodMoralAccess(user);

  if (access.isStudent) {
    const requestHref = access.canRequestSelf && user.student_lifecycle_status === "CURRENT"
      ? "/portal/good-moral/request"
      : access.canRequestSelf && user.student_lifecycle_status === "GRADUATED"
        ? "/portal/good-moral/request"
        : null;
    const requestLabel = user.student_lifecycle_status === "CURRENT"
      ? "Request Current Student certificate"
      : user.student_lifecycle_status === "GRADUATED"
        ? "Request Graduate certificate"
        : null;

    return (
      <GoodMoralStudentHistory
        canView={access.canViewSelf}
        requestHref={requestHref}
        requestLabel={requestHref ? requestLabel : null}
      />
    );
  }

  if (access.isCounselor) {
    if (!access.canViewOperational) {
      return <GoodMoralUnavailable message="Your Counselor account does not have Good Moral request-view access." />;
    }
    return <GoodMoralOperationalList filters={filters} />;
  }

  return <GoodMoralUnavailable />;
}

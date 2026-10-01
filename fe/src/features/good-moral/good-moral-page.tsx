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

  if (access.isStudent && access.hasStudentWorkspace) {
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

  if (access.isCounselor && access.hasOperationalWorkspace) {
    return <GoodMoralOperationalList filters={filters} />;
  }

  return <GoodMoralUnavailable />;
}

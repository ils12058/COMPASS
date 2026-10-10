"use client";

import { pageSheetWidth } from "@/components/ui/page-width";
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
    return (
      <div className={pageSheetWidth}>
        <GoodMoralStudentHistory
          canView={access.canViewSelf}
          requestHref={requestHref}
          requestLabel={requestHref ? "Request Good Moral Certificate" : null}
        />
      </div>
    );
  }

  if (access.hasOperationalWorkspace) {
    return <GoodMoralOperationalList filters={filters} />;
  }

  return <GoodMoralUnavailable />;
}

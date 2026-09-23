"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function OrganizationIndex() {
  const router = useRouter();
  const { user } = usePortalSession();
  const canView = user.capabilities.includes("organization.view");
  const canManage = user.capabilities.includes("organization.manage");

  useEffect(() => {
    if (canView) {
      router.replace("/portal/organization/campuses");
    } else if (canManage) {
      router.replace("/portal/organization/responsibilities");
    }
  }, [canManage, canView, router]);

  return (
    <div aria-busy="true">
      <Skeleton className="h-9 w-52" />
      <Skeleton className="mt-5 h-20 w-full max-w-xl" />
      <p className="sr-only">Opening Organization…</p>
    </div>
  );
}

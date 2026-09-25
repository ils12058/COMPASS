"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { canViewOrganizationStructure } from "@/features/institution-configuration/institution-access";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function OrganizationIndex() {
  const router = useRouter();
  const { user } = usePortalSession();
  const canViewStructure = canViewOrganizationStructure(user);

  useEffect(() => {
    router.replace(
      canViewStructure
        ? "/portal/organization/campuses"
        : "/portal/organization/responsibilities",
    );
  }, [canViewStructure, router]);

  return (
    <div aria-busy="true">
      <Skeleton className="h-9 w-52" />
      <Skeleton className="mt-5 h-20 w-full max-w-xl" />
      <p className="sr-only">Opening Organization…</p>
    </div>
  );
}

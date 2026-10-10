import { ListChecks } from "lucide-react";

import type { PortalWorkspaceNavItem } from "@/features/portal/components/portal-workspace-nav";

export type PortalItAdminServicesSection = "catalog";

export const PORTAL_IT_ADMIN_SERVICES_NAV_ITEMS = [
  {
    href: "/portal/admin/services",
    label: "Service catalog",
    value: "catalog",
    icon: ListChecks,
  },
] satisfies readonly PortalWorkspaceNavItem[];

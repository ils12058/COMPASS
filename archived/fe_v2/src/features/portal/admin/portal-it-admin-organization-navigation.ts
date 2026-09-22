import { Building2, GraduationCap, Network, School, UserRoundCog } from "lucide-react";

import type { PortalWorkspaceNavItem } from "@/features/portal/components/portal-workspace-nav";

export type PortalItAdminOrganizationSection =
  | "overview"
  | "campuses"
  | "colleges"
  | "programs"
  | "assignments";

export const PORTAL_IT_ADMIN_ORGANIZATION_NAV_ITEMS = [
  {
    href: "/portal/admin/organization",
    label: "Overview",
    value: "overview",
    icon: Network,
  },
  {
    href: "/portal/admin/organization/campuses",
    label: "Campuses",
    value: "campuses",
    icon: Building2,
  },
  {
    href: "/portal/admin/organization/colleges",
    label: "Colleges",
    value: "colleges",
    icon: School,
  },
  {
    href: "/portal/admin/organization/programs",
    label: "Programs",
    value: "programs",
    icon: GraduationCap,
  },
  {
    href: "/portal/admin/organization/assignments",
    label: "Assignments",
    value: "assignments",
    icon: UserRoundCog,
  },
] satisfies readonly PortalWorkspaceNavItem[];

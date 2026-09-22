import {
  Building2,
  BriefcaseBusiness,
  CalendarClock,
  LayoutDashboard,
  UsersRound,
} from "lucide-react";

import type { PortalWorkspaceNavItem } from "@/features/portal/components/portal-workspace-nav";

export type PortalItAdminSection =
  | "overview"
  | "accounts"
  | "organization"
  | "services"
  | "availability";

export const PORTAL_IT_ADMIN_NAV_ITEMS = [
  {
    href: "/portal/admin",
    label: "Overview",
    value: "overview",
    icon: LayoutDashboard,
  },
  {
    href: "/portal/admin/accounts",
    label: "Accounts",
    value: "accounts",
    icon: UsersRound,
  },
  {
    href: "/portal/admin/organization",
    label: "Organization",
    value: "organization",
    icon: Building2,
  },
  {
    href: "/portal/admin/services",
    label: "Services",
    value: "services",
    icon: BriefcaseBusiness,
  },
  {
    href: "/portal/admin/availability",
    label: "Availability",
    value: "availability",
    icon: CalendarClock,
  },
] satisfies readonly PortalWorkspaceNavItem[];

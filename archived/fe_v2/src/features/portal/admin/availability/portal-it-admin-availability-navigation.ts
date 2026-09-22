import {
  CalendarClock,
  CalendarDays,
  ClipboardClock,
  Clock3,
  UsersRound,
} from "lucide-react";

import type { PortalWorkspaceNavItem } from "@/features/portal/components/portal-workspace-nav";

export type PortalItAdminAvailabilitySection =
  | "office-schedule"
  | "office-exceptions"
  | "provider-schedules"
  | "provider-exceptions"
  | "effective-availability";

export const PORTAL_IT_ADMIN_AVAILABILITY_NAV_ITEMS = [
  {
    href: "/portal/admin/availability",
    label: "Office schedule",
    value: "office-schedule",
    icon: CalendarClock,
  },
  {
    href: "/portal/admin/availability/office-exceptions",
    label: "Office exceptions",
    value: "office-exceptions",
    icon: CalendarDays,
  },
  {
    href: "/portal/admin/availability/provider-schedules",
    label: "Provider schedules",
    value: "provider-schedules",
    icon: UsersRound,
  },
  {
    href: "/portal/admin/availability/provider-exceptions",
    label: "Provider exceptions",
    value: "provider-exceptions",
    icon: ClipboardClock,
  },
  {
    href: "/portal/admin/availability/effective",
    label: "Effective availability",
    value: "effective-availability",
    icon: Clock3,
  },
] satisfies readonly PortalWorkspaceNavItem[];

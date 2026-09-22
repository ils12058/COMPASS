import {
  Bell,
  House,
  UserRound,
  type LucideIcon,
} from "lucide-react";

export type PortalNavigationItem = {
  id: "home" | "notifications" | "profile";
  href: string;
  label: string;
  icon: LucideIcon;
  requiredCapability?: string;
  requiredCapabilitiesAny?: readonly string[];
};

/**
 * Keep this registry limited to portal destinations that already exist.
 * New operational destinations can be added alongside their route surface and
 * capability projection instead of exposing links that lead to empty pages.
 */
export const PORTAL_NAVIGATION: readonly PortalNavigationItem[] = [
  {
    id: "home",
    href: "/portal",
    label: "Home",
    icon: House,
  },
  {
    id: "notifications",
    href: "/portal/notifications",
    label: "Notifications",
    icon: Bell,
  },
  {
    id: "profile",
    href: "/portal/account",
    label: "Profile",
    icon: UserRound,
  },
];

function hasRequiredCapability(
  item: PortalNavigationItem,
  capabilities: readonly string[],
) {
  if (
    item.requiredCapability &&
    !capabilities.includes(item.requiredCapability)
  ) {
    return false;
  }

  if (
    item.requiredCapabilitiesAny?.length &&
    !item.requiredCapabilitiesAny.some((capability) =>
      capabilities.includes(capability),
    )
  ) {
    return false;
  }

  return true;
}

export function getVisiblePortalNavigation(
  capabilities: readonly string[],
) {
  return PORTAL_NAVIGATION.filter((item) =>
    hasRequiredCapability(item, capabilities),
  );
}

export function isPortalNavigationItemActive(
  pathname: string | null,
  href: string,
) {
  if (!pathname) {
    return false;
  }

  return href === "/portal"
    ? pathname === href
    : pathname === href || pathname.startsWith(`${href}/`);
}

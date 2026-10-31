// Faculty has a separate intake namespace; GCO components never mount through this boundary.
export function facultyPortalPathAvailable(pathname: string): boolean {
  return pathname === "/portal" || pathname === "/portal/notifications" ||
    pathname === "/portal/account" || pathname.startsWith("/portal/account/") ||
    pathname === "/portal/faculty/referrals" || pathname === "/portal/faculty/referrals/new" ||
    /^\/portal\/faculty\/referrals\/[0-9a-f-]{36}$/i.test(pathname);
}

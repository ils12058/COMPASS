// Faculty has a separate intake namespace; GCO components never mount through this boundary.
// Messages is the Guidance Office inquiry path only: templates stay staff-only, and the
// workspace gate decides which of these the account can actually use.
export function facultyPortalPathAvailable(pathname: string): boolean {
  return pathname === "/portal" || pathname === "/portal/notifications" ||
    pathname === "/portal/account" || pathname.startsWith("/portal/account/") ||
    pathname === "/portal/faculty/referrals" || pathname === "/portal/faculty/referrals/new" ||
    /^\/portal\/faculty\/referrals\/[0-9a-f-]{36}$/i.test(pathname) ||
    pathname === "/portal/messages" || pathname === "/portal/messages/new" ||
    /^\/portal\/messages\/[0-9a-f-]{36}$/i.test(pathname);
}

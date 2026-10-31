// FAC-1 supports identity and own account services only. Backend authorization is final.
export function facultyPortalPathAvailable(pathname: string): boolean {
  return pathname === "/portal" || pathname === "/portal/notifications" ||
    pathname === "/portal/account" || pathname.startsWith("/portal/account/");
}

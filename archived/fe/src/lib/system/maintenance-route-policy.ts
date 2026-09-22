const MAINTENANCE_EXEMPT_PREFIXES = ["/login", "/password"] as const;

function matchesPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

export function isMaintenanceExemptPath(pathname: string): boolean {
  return MAINTENANCE_EXEMPT_PREFIXES.some((prefix) =>
    matchesPrefix(pathname, prefix),
  );
}

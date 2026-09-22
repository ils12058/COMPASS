const PORTAL_FALLBACK = "/portal";
const SAFE_BASE = "https://compass.invalid";

export function safePortalDestination(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return PORTAL_FALLBACK;
  }

  try {
    const target = new URL(value, SAFE_BASE);
    const isPortalPath =
      target.pathname === PORTAL_FALLBACK || target.pathname.startsWith(`${PORTAL_FALLBACK}/`);

    if (target.origin !== SAFE_BASE || !isPortalPath) return PORTAL_FALLBACK;

    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return PORTAL_FALLBACK;
  }
}

export function loginPathForPortal(value: string): string {
  const destination = safePortalDestination(value);
  return `/login?next=${encodeURIComponent(destination)}`;
}

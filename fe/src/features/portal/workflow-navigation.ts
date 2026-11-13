/** Record journeys keep their originating filters inside a bounded portal return URL. */
const portalBase = "https://compass.invalid";

export function portalReturnHref(value: string | null | undefined, fallback: string): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u001f]/.test(value)) return fallback;
  try {
    const url = new URL(value, portalBase);
    if (url.origin !== portalBase || (url.pathname !== "/portal" && !url.pathname.startsWith("/portal/"))) return fallback;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
}

export function withWorkflowReturn(href: string, returnTo: string): string {
  const url = new URL(href, portalBase);
  url.searchParams.set("return_to", portalReturnHref(returnTo, "/portal"));
  return `${url.pathname}${url.search}${url.hash}`;
}

export function workflowBackLabel(href: string): string {
  const pathname = new URL(href, portalBase).pathname;
  if (pathname === "/portal/work") return "Back to My work";
  if (pathname.startsWith("/portal/follow-ups")) return "Back to Follow-Ups";
  if (pathname.startsWith("/portal/counseling/cases/")) return "Back to case";
  if (pathname === "/portal/counseling/encounters") return "Back to session records";
  if (pathname.startsWith("/portal/counseling/encounters/")) return "Back to session record";
  if (pathname.startsWith("/portal/appointments")) return "Back to Appointments";
  if (pathname === "/portal/routine-interviews") return "Back to Routine Interviews";
  if (pathname.startsWith("/portal/routine-interviews")) return "Back to Routine Interview";
  if (pathname.startsWith("/portal/referrals")) return "Back to Referral";
  if (pathname.startsWith("/portal/counseling")) return "Back to Counseling";
  return "Back to Overview";
}

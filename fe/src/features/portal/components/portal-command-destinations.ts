import { Bell, LayoutDashboard, UserRound, type LucideIcon } from "lucide-react";

import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { canManageAvailability, canUseSelfAvailability } from "@/features/availability/availability-shared";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { canViewOrganizationStructure } from "@/features/institution-configuration/institution-access";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { canManagePrivacyGovernance, canManageRetention, canViewPrivacyGovernance, canViewRetention } from "@/features/privacy-governance/privacy-governance-access";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { portalWorkspaceGroups } from "@/features/portal/components/portal-workspaces";
import type { UserSummary } from "@/lib/api/generated/model";

export type PortalCommandDestination = {
  href: string;
  label: string;
  breadcrumb: string;
  group: string;
  icon: LucideIcon;
  keywords: readonly string[];
};

const workspaceKeywords: Readonly<Record<string, readonly string[]>> = {
  Appointments: ["calendar", "schedule", "booking"],
  Availability: ["calendar", "schedule"],
  "Individual Inventory": ["student information", "inventory"],
  "Institutional Forms": ["form", "forms", "form revision", "controlled form"],
};

// Code-owned destinations only. Root visibility comes directly from the dock's registry. Deep
// entries also require the workspace and the helper used by the actual page/tab. No record context.
export function portalCommandDestinations(user: UserSummary): PortalCommandDestination[] {
  const groups = portalWorkspaceGroups(user);
  const roots = groups.flatMap((group) => group.links.map((link) => ({
    ...link, group: group.label, breadcrumb: link.label,
    keywords: workspaceKeywords[link.label] ?? [],
  })));
  const destinations: PortalCommandDestination[] = [
    { href: "/portal", label: "Overview", breadcrumb: "Overview", group: "General", icon: LayoutDashboard, keywords: ["home"] },
    ...roots,
    { href: "/portal/notifications", label: "Notifications", breadcrumb: "Notifications", group: "General", icon: Bell, keywords: ["alerts"] },
  ];
  for (const [slug, label, keywords] of [
    ["profile", "Profile", ["account details"]],
    ["security", "Security", ["password", "mfa", "2fa", "authenticator", "sessions", "sign in"]],
    ["activity", "Activity", ["my activity", "security activity", "supervised staff activity"]],
    ["preferences", "Preferences", ["settings"]],
    ["privacy", "Privacy", ["my privacy notices"]],
  ] as const) {
    destinations.push({ href: `/portal/account/${slug}`, label, breadcrumb: `Account › ${label}`, group: "Account", icon: UserRound, keywords });
  }

  function deep(parentHref: string, path: string, label: string, allowed = true, keywords: readonly string[] = []) {
    const parent = roots.find((root) => root.href === parentHref);
    if (!parent || !allowed) return;
    destinations.push({ href: parentHref + path, label, breadcrumb: `${parent.label} › ${label}`, group: parent.group, icon: parent.icon, keywords });
  }
  const appointments = getAppointmentAccess(user);
  deep("/portal/appointments", "/my", "My appointments", appointments.canViewSelf, ["calendar", "schedule"]);
  deep("/portal/appointments", "/book", "Book appointment", appointments.canBook, ["booking"]);
  deep("/portal/appointments", "/manage", "Manage appointments", appointments.canManage, ["calendar", "schedule"]);
  deep("/portal/availability", "/me", "My availability", canUseSelfAvailability(user), ["schedule"]);
  deep("/portal/availability", "/office", "Office", canManageAvailability(user), ["office availability", "schedule"]);
  deep("/portal/availability", "/providers", "Counselors", canManageAvailability(user), ["counselor availability", "schedule"]);
  deep("/portal/services", "/new", "Create Service"); // Services layout uses the same workspace gate.
  deep("/portal/referrals", "/new", "Record referral", getReferralAccess(user).canManage, ["new referral"]);
  deep("/portal/call-slips", "/new", "Issue Call Slip", getCallSlipAccess(user).canManageOperational);
  deep("/portal/inventory", "/current", "Current Individual Inventory", getInventoryAccess(user).canViewSelf);
  deep("/portal/good-moral", "/request", "Request Good Moral", getGoodMoralAccess(user).canRequestSelf);
  const feedback = getFeedbackAccess(user);
  deep("/portal/feedback", "/customer-feedback/responses", "Customer Feedback responses", feedback.canViewCustomerFeedback);
  deep("/portal/feedback", "/csm/responses", "CSM responses", feedback.canViewCsm, ["customer satisfaction measurement"]);
  deep("/portal/announcements", "/new", "Create Announcement");
  deep("/portal/resources", "/new", "Create Resource");
  deep("/portal/reports", "/student-profile", "Student Profiling", true, ["student profile report"]);
  deep("/portal/reports", "/graduate-tracer", "Graduate Tracer", true, ["graduate tracer report"]);
  deep("/portal/organization", "", "Structure", canViewOrganizationStructure(user), ["campus", "college", "program"]);
  deep("/portal/organization", "/responsibilities", "Responsibilities", true, ["responsibility", "supervision", "staff assignment"]);
  deep("/portal/organization", "/student-affiliations", "Student affiliations", true, ["student affiliation", "college", "program"]);
  deep("/portal/accounts", "/new", "Create account"); // Accounts layout requires accounts.manage.
  deep("/portal/accounts", "/import", "Import accounts");
  const privacyView = canViewPrivacyGovernance(user);
  const retentionView = canViewRetention(user);
  deep("/portal/privacy", "/notices", "Privacy Notices", privacyView, ["privacy notice"]);
  deep("/portal/privacy", "/notices/new", "Create Privacy Notice", privacyView && canManagePrivacyGovernance(user));
  deep("/portal/privacy", "/retention", "Retention & Disposition", retentionView, ["retention", "disposition", "hold"]);
  deep("/portal/privacy", "/retention/rules", "Retention Rules", retentionView, ["retention rule"]);
  deep("/portal/privacy", "/retention/rules/new", "Create Retention Rule", retentionView && canManageRetention(user));
  deep("/portal/privacy", "/activity", "Privacy & Security Activity", privacyView, ["privacy activity"]);
  // Platform Operations' root already opens Health. Keep its dock label and a canonical Health
  // entry; both address the same stable route (as Organization and Structure do).
  const platform = roots.find((root) => root.href === "/portal/platform/health");
  if (platform) {
    for (const [slug, label, keywords] of [
      ["health", "Health", ["worker", "celery", "health", "diagnostic"]],
      ["maintenance", "Maintenance", ["maintenance"]],
      ["email-delivery", "Email delivery", ["email delivery", "smtp", "mail"]],
      ["environment", "Environment", ["environment", "build", "runtime"]],
      ["activity", "Technical activity", ["technical activity", "platform activity"]],
    ] as const) {
      destinations.push({ href: `/portal/platform/${slug}`, label, breadcrumb: `Platform Operations › ${label}`, group: platform.group, icon: platform.icon, keywords });
    }
  }
  return destinations;
}

export function normalizeCommandQuery(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

export function searchPortalCommands(destinations: readonly PortalCommandDestination[], query: string): PortalCommandDestination[] {
  const term = normalizeCommandQuery(query);
  if (!term) return [...destinations];
  return destinations.map((destination, index) => {
    const label = normalizeCommandQuery(destination.label);
    const rank = label === term ? 0 : label.startsWith(term) ? 1 : label.includes(term) ? 2
      : [destination.breadcrumb, destination.group].some((value) => normalizeCommandQuery(value).includes(term)) ? 3
      : destination.keywords.some((value) => normalizeCommandQuery(value).includes(term)) ? 4 : 5;
    return { destination, rank, index };
  }).filter(({ rank }) => rank < 5)
    .sort((left, right) => left.rank - right.rank || left.index - right.index)
    .map(({ destination }) => destination);
}

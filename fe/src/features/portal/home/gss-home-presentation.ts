import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { followupAccess } from "@/features/guidance-followups/followups-access";
import { getGuidanceMessagesAccess } from "@/features/guidance-messages/guidance-messages-access";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { portalWorkspaceGroups, type PortalWorkspaceLink } from "@/features/portal/components/portal-workspaces";
import { AppointmentListOrdering, AppointmentStatus, type GuidanceOperationsResponse, type UserSummary, type WorkItem } from "@/lib/api/generated/model";
import { presentWork } from "@/features/work-queue/work-queue-presentation";

export const GSS_HOME_PREVIEW_SIZE = 5;

export function getGssManagedAppointmentParams(today: string) {
  return {
    status: AppointmentStatus.SCHEDULED,
    from_date: today,
    to_date: today,
    ordering: AppointmentListOrdering.EARLIEST_START,
    page: 1,
    page_size: GSS_HOME_PREVIEW_SIZE,
  };
}

export function presentGssWork(item: WorkItem, user: UserSummary, generatedAt?: string) {
  const goodMoral = getGoodMoralAccess(user);
  switch (item.kind) {
    case "ROUTINE_EVALUATION":
      // This workspace is Counselor-only. A malformed or newly broadened projection must not
      // introduce Counselor evaluation records into the GSS Home.
      if (!getRoutineInterviewAccess(user).canViewAssigned) return null;
      break;
    case "GOOD_MORAL_PREPARATION":
      if (!goodMoral.canPrepare) return null;
      break;
    case "GOOD_MORAL_ISSUANCE":
      if (!goodMoral.canViewOperational) return null;
      if (!goodMoral.canIssue) {
        const row = presentWork(item, generatedAt);
        return {
          title: "Good Moral request awaiting Counselor issuance",
          detail: row?.detail ?? "Awaiting Counselor review",
          href: `/portal/good-moral/${item.source_id}`,
          actionLabel: "View request",
        };
      }
      break;
    case "GUIDANCE_MESSAGE_REPLY":
      if (!getGuidanceMessagesAccess(user).hasWorkspace) return null;
      break;
    case "CALL_SLIP_DUE":
      if (!getCallSlipAccess(user).hasWorkspace) return null;
      break;
    case "GUIDANCE_FOLLOW_UP":
      if (!followupAccess(user).view) return null;
      break;
  }
  return presentWork(item, generatedAt) ?? null;
}

export type GssOperationalMetric = {
  key: string;
  label: string;
  count: number;
  oldest?: { label: "Oldest waiting" | "Oldest due"; instant: string };
  href?: string;
};

/** These are scoped office facts, not assignments. Null means the source did not return a metric. */
export function presentGssOperations(data: GuidanceOperationsResponse, user: UserSummary): GssOperationalMetric[] {
  const metrics: GssOperationalMetric[] = [];
  const messages = data.backlog.guidance_messages;
  if (messages !== null) {
    metrics.push({
      key: "messages",
      label: "Messages awaiting reply",
      count: messages.count,
      ...(messages.oldest_waiting_since ? { oldest: { label: "Oldest waiting", instant: messages.oldest_waiting_since } } : {}),
      ...(getGuidanceMessagesAccess(user).hasWorkspace ? { href: "/portal/messages" } : {}),
    });
  }

  const preparation = data.backlog.good_moral_preparation;
  if (preparation !== null) {
    const access = getGoodMoralAccess(user);
    metrics.push({
      key: "good-moral-preparation",
      label: "Good Moral requests awaiting preparation",
      count: preparation.count,
      ...(preparation.oldest_waiting_since ? { oldest: { label: "Oldest waiting", instant: preparation.oldest_waiting_since } } : {}),
      ...(access.canPrepare ? { href: "/portal/good-moral?status=REQUESTED" } : {}),
    });
  }

  const issuance = data.backlog.good_moral_issuance;
  if (issuance !== null) {
    metrics.push({
      key: "good-moral-issuance",
      label: "Good Moral requests awaiting Counselor issuance",
      count: issuance.count,
      ...(issuance.oldest_waiting_since ? { oldest: { label: "Oldest waiting", instant: issuance.oldest_waiting_since } } : {}),
    });
  }

  const callSlips = data.backlog.call_slips_due;
  if (callSlips !== null) {
    metrics.push({
      key: "call-slips",
      label: "Call Slips due",
      count: callSlips.count,
      ...(callSlips.oldest_due_at ? { oldest: { label: "Oldest due", instant: callSlips.oldest_due_at } } : {}),
      ...(getCallSlipAccess(user).hasWorkspace ? { href: "/portal/call-slips" } : {}),
    });
  }

  // The shared schema also serves Counselors. GSS must not infer access to their evaluations.
  const evaluations = data.backlog.routine_evaluations;
  if (evaluations !== null && getRoutineInterviewAccess(user).canViewAssigned) {
    metrics.push({
      key: "routine-evaluations",
      label: "Routine evaluations pending",
      count: evaluations.count,
      ...(evaluations.oldest_waiting_since ? { oldest: { label: "Oldest waiting", instant: evaluations.oldest_waiting_since } } : {}),
      href: "/portal/routine-interviews",
    });
  }
  return metrics;
}

type GssDestinationCopy = { description: string; label?: string };

const DESTINATIONS: Record<string, GssDestinationCopy> = {
  "/portal/appointments": { label: "Manage Appointments", description: "Coordinate scheduled Appointments in your authorized scope." },
  "/portal/operations": { description: "Review scoped office workload and schedule context." },
  "/portal/good-moral": { description: "Continue authorized Good Moral request work." },
  "/portal/call-slips": { description: "Review Call Slips in your operational scope." },
  "/portal/messages": { description: "Continue authorized Guidance conversations." },
  "/portal/referrals": { description: "Review Referrals available to you." },
  "/portal/follow-ups": { description: "Review Guidance Follow-Ups available to you." },
  "/portal/group-sessions": { description: "Open Group Sessions within your operational scope." },
  "/portal/availability": { description: "Review the availability workspace available to you." },
  "/portal/services": { description: "Open the Services workspace available to you." },
};

const DESTINATION_ORDER = Object.keys(DESTINATIONS);

export type GssHomeDestination = PortalWorkspaceLink & GssDestinationCopy;

/** A short office continuation list derived only from the existing capability-aware destinations. */
export function getGssHomeDestinations(user: UserSummary): GssHomeDestination[] {
  const available = new Map(portalWorkspaceGroups(user).flatMap((group) => group.links).map((link) => [link.href, link]));
  return DESTINATION_ORDER.flatMap((href) => {
    const link = available.get(href);
    const copy = DESTINATIONS[href];
    return link && copy ? [{ ...link, ...copy }] : [];
  }).slice(0, 6);
}

import type {
  GuidanceHandlerRole,
  GuidanceMessageResponse,
  GuidancePerson,
  GuidanceThreadResponse,
  ThreadKind,
  ThreadStatus,
} from "@/lib/api/generated/model";

// Human wording for Guidance Messages. Backend enums, IDs and sequence cursors never reach the
// screen; a Student addresses the Guidance Office as an office, while staff see the Student.

export type GuidanceViewer = "student" | "faculty" | "staff";

export const GUIDANCE_OFFICE_LABEL = "Guidance Office";

const KIND_LABELS: Record<ThreadKind, string> = {
  OFFICE: GUIDANCE_OFFICE_LABEL,
  COUNSELING: "Counseling",
  FACULTY_INQUIRY: "Faculty inquiry",
  REFERRAL_COORDINATION: "Referral coordination",
  COUNSELOR_DIRECT: "Counselor conversation",
  COUNSELOR_CASE_COORDINATION: "Case coordination",
};

const STATUS_LABELS: Record<ThreadStatus, string> = {
  OPEN: "Open",
  RESOLVED: "Resolved",
};

const HANDLER_ROLE_LABELS: Record<GuidanceHandlerRole, string> = {
  COUNSELOR: "Counselor",
  GUIDANCE_OFFICE_ASSISTANT: "Guidance Office Assistant",
};

export function handlerRoleLabel(role: GuidanceHandlerRole): string {
  return HANDLER_ROLE_LABELS[role];
}

export function threadKindLabel(kind: ThreadKind): string {
  return KIND_LABELS[kind];
}

export function threadStatusLabel(status: ThreadStatus): string {
  return STATUS_LABELS[status];
}

export function personName(person: GuidancePerson | null | undefined, fallback: string): string {
  const name = person?.display_name.trim();
  return name ? name : fallback;
}

/** Who the conversation is with, from the reader's side. */
export function threadTitle(
  thread: GuidanceThreadResponse,
  viewer: GuidanceViewer,
  currentUserId?: string,
): string {
  if (thread.kind === "COUNSELOR_DIRECT") {
    let other = thread.direct_first_user ?? thread.direct_second_user;
    if (currentUserId && thread.direct_first_user?.id === currentUserId) {
      other = thread.direct_second_user;
    }
    return personName(other, "Counselor");
  }
  if (thread.kind === "COUNSELOR_CASE_COORDINATION") {
    return personName(thread.student_subject, "Case coordination");
  }
  if (viewer === "staff") {
    if (thread.kind === "FACULTY_INQUIRY") return personName(thread.requester, "Faculty");
    if (thread.kind === "REFERRAL_COORDINATION") return personName(thread.requester, "Faculty");
    return personName(thread.student, "Student");
  }
  return thread.kind === "COUNSELING"
    ? personName(thread.counselor, "Counselor")
    : GUIDANCE_OFFICE_LABEL;
}

/**
 * The short line under the title. A Student's Office conversation and a Faculty member's own
 * inquiry are already titled "Guidance Office", so they have none; everything else names the kind.
 */
export function threadSubtitle(
  thread: GuidanceThreadResponse,
  viewer: GuidanceViewer,
): string | null {
  if (viewer === "student" && thread.kind === "OFFICE") return null;
  if (viewer === "faculty" && thread.kind === "FACULTY_INQUIRY") return null;
  if (thread.kind === "REFERRAL_COORDINATION") {
    const reference = thread.relationship_referral_reference?.trim();
    return reference ? `Referral ${reference}` : threadKindLabel(thread.kind);
  }
  return threadKindLabel(thread.kind);
}

/** Staff-only routing facts for an Office conversation: the routing College and its handler. */
export function threadRoutingFacts(thread: GuidanceThreadResponse, viewer: GuidanceViewer): {
  college: string | null;
  assignedTo: string | null;
} {
  // A referral thread's College is the submission snapshot, not current routing.
  if (thread.kind === "REFERRAL_COORDINATION") return { college: null, assignedTo: null };
  if (thread.kind === "COUNSELOR_DIRECT") return { college: null, assignedTo: null };
  if (thread.kind === "COUNSELOR_CASE_COORDINATION") return { college: null, assignedTo: null };
  if (viewer !== "staff" || thread.kind !== "OFFICE") return { college: null, assignedTo: null };
  return {
    college: thread.routing_college?.name.trim() || thread.routing_college?.code.trim() || null,
    assignedTo: thread.assigned_to ? personName(thread.assigned_to, "Guidance staff") : null,
  };
}

export function unreadLabel(count: number): string | null {
  return count > 0 ? `${count} unread` : null;
}

export function senderLabel(sender: GuidancePerson, currentUserId: string): string {
  return sender.id === currentUserId ? "You" : personName(sender, "Unnamed participant");
}

// Provisional wording pending GCO copy (D-GMSG-15). Engineering default, not institutional approval.
export const COUNSELOR_DIRECT_NOTICE =
  "Counselor conversations are for coordination between Counselors. Do not include confidential Student case details.";

// The case-coordination surface's three exact copies. The ended copy is the proposal-specified
// placeholder pending GCO wording (D-GMSG-15); do not substitute alternative institutional promises.
export const CASE_COORDINATION_ENTRY_COPY = "Coordinate on this authorized case.";
export const CASE_COORDINATION_ENDED_COPY = "Your case coordination access has ended.";
export const CASE_COORDINATION_UNAVAILABLE_COPY =
  "This conversation is no longer available for new messages.";

// ── Receipts and typing (GMSG-6/7) ───────────────────────────────────────────────────────────
// "Seen" means the other side genuinely viewed a Message: the backend derives it from read cursors
// that move only while a conversation is open in a visible tab. Nothing here says "Delivered", and
// a conversation without a receipt shows nothing rather than "Not seen".

/**
 * Whether a Message was written from the reader's side. Office staff write as the Guidance Office,
 * so in a Student Office conversation every staff Message is theirs; everyone else writes as
 * themselves.
 */
export function isOwnSide(
  thread: GuidanceThreadResponse,
  viewer: GuidanceViewer,
  currentUserId: string,
  message: GuidanceMessageResponse,
): boolean {
  if (viewer === "staff" && thread.kind === "OFFICE") return message.sender.id !== thread.student?.id;
  return message.sender.id === currentUserId;
}

/** The receipt to show under the reader's latest Message, or null when there is none to show. */
export function seenReceipt(
  thread: GuidanceThreadResponse,
  messages: readonly GuidanceMessageResponse[],
  viewer: GuidanceViewer,
  currentUserId: string,
): { sequence: number; label: string } | null {
  if (thread.seen_scope == null || thread.seen_sequence == null) return null;
  const last = messages.at(-1);
  // A reply from the other side already shows they read it.
  if (!last || !isOwnSide(thread, viewer, currentUserId, last)) return null;
  if (thread.seen_sequence < last.sequence) return null;
  return {
    sequence: last.sequence,
    label: thread.seen_scope === "OFFICE" ? `Seen by ${GUIDANCE_OFFICE_LABEL}` : "Seen",
  };
}

/** The newest sequence the other side wrote, so their next Message can clear "is typing". */
export function latestCounterpartSequence(
  thread: GuidanceThreadResponse,
  messages: readonly GuidanceMessageResponse[],
  viewer: GuidanceViewer,
  currentUserId: string,
): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (!isOwnSide(thread, viewer, currentUserId, message)) return message.sequence;
  }
  return 0;
}

/** Who is writing, from the reader's side; the case pair is never named here. */
export function typingLabel(
  thread: GuidanceThreadResponse,
  viewer: GuidanceViewer,
  currentUserId: string,
): string {
  if (thread.kind === "COUNSELOR_CASE_COORDINATION") return "The other Counselor is typing…";
  return `${threadTitle(thread, viewer, currentUserId)} is typing…`;
}

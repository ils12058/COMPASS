import type { GuidancePerson, GuidanceThreadResponse, ThreadKind, ThreadStatus } from "@/lib/api/generated/model";

// Human wording for Guidance Messages. Backend enums, IDs and sequence cursors never reach the
// screen; a Student addresses the Guidance Office as an office, while staff see the Student.

export type GuidanceViewer = "student" | "staff";

export const GUIDANCE_OFFICE_LABEL = "Guidance Office";

const KIND_LABELS: Record<ThreadKind, string> = {
  OFFICE: GUIDANCE_OFFICE_LABEL,
  COUNSELING: "Counseling",
};

const STATUS_LABELS: Record<ThreadStatus, string> = {
  OPEN: "Open",
  RESOLVED: "Resolved",
};

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
export function threadTitle(thread: GuidanceThreadResponse, viewer: GuidanceViewer): string {
  if (viewer === "staff") return personName(thread.student, "Student");
  return thread.kind === "OFFICE" ? GUIDANCE_OFFICE_LABEL : personName(thread.counselor, "Counselor");
}

/**
 * The short line under the title. A Student's Office conversation is already titled "Guidance
 * Office", so it has none; everything else names the kind of conversation.
 */
export function threadSubtitle(thread: GuidanceThreadResponse, viewer: GuidanceViewer): string | null {
  if (viewer === "student" && thread.kind === "OFFICE") return null;
  return threadKindLabel(thread.kind);
}

/** Staff-only routing facts for an Office conversation: the routing College and its handler. */
export function threadRoutingFacts(thread: GuidanceThreadResponse, viewer: GuidanceViewer): {
  college: string | null;
  assignedTo: string | null;
} {
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

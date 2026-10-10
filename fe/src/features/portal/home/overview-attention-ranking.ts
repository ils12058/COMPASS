// How "Needs your attention" orders what it shows (ADR-090). Items come from domain-owned,
// authorized previews; the Overview only ranks them, so the order never depends on the order in
// which the code happens to assemble them.
//
// Ranking: priority class, then the earliest due time, then the longest waiting, then a stable
// key. Ranking never adds or removes items, so it cannot widen what the reader may see.

export const AttentionPriority = {
  // A failed operation that needs someone to intervene, such as failed email deliveries.
  CRITICAL: "CRITICAL",
  // Work with a real approaching or passed business deadline. Reserved: no current item has one.
  TIME_SENSITIVE: "TIME_SENSITIVE",
  // Operational work waiting on the reader: pending evaluations, requests awaiting preparation.
  ACTION_REQUIRED: "ACTION_REQUIRED",
  // The reader's own unfinished drafts.
  INCOMPLETE_SELF_SERVICE: "INCOMPLETE_SELF_SERVICE",
} as const;

export type AttentionPriority = (typeof AttentionPriority)[keyof typeof AttentionPriority];

const PRIORITY_ORDER: readonly AttentionPriority[] = [
  AttentionPriority.CRITICAL,
  AttentionPriority.TIME_SENSITIVE,
  AttentionPriority.ACTION_REQUIRED,
  AttentionPriority.INCOMPLETE_SELF_SERVICE,
];

export type AttentionRank = {
  priority: AttentionPriority;
  // A business deadline, when the item has one.
  dueAt?: string | null;
  // When the item started waiting, measured from the owning domain's queue anchor.
  waitingSince?: string | null;
  // Deterministic last resort; also keeps a domain's own preview order for undated items.
  stableKey: string;
};

function instant(value: string | null | undefined): number | null {
  if (!value) return null;
  const time = Date.parse(value);
  return Number.isNaN(time) ? null : time;
}

// Present values sort before missing ones; among present values, earlier first.
function compareInstants(left: string | null | undefined, right: string | null | undefined): number {
  const a = instant(left);
  const b = instant(right);
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return a - b;
}

export function compareAttention(left: AttentionRank, right: AttentionRank): number {
  return (
    PRIORITY_ORDER.indexOf(left.priority) - PRIORITY_ORDER.indexOf(right.priority) ||
    compareInstants(left.dueAt, right.dueAt) ||
    compareInstants(left.waitingSince, right.waitingSince) ||
    (left.stableKey < right.stableKey ? -1 : left.stableKey > right.stableKey ? 1 : 0)
  );
}

export function rankAttention<T extends { rank: AttentionRank }>(items: readonly T[]): T[] {
  return [...items].sort((left, right) => compareAttention(left.rank, right.rank));
}

// Keeps a domain's own preview order among items without times, for example "routine:001:<id>".
export function attentionKey(domain: string, position: number, id: string): string {
  return `${domain}:${String(position).padStart(3, "0")}:${id}`;
}

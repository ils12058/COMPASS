export const TEN_MINUTES_MS = 10 * 60 * 1000;
export const FIVE_MINUTES_MS = 5 * 60 * 1000;

export type SessionTimingPhase =
  | "NORMAL"
  | "APPROACHING_END"
  | "FINAL_REMINDER"
  | "SCHEDULED_END_REACHED"
  | "OVERTIME";

export type SessionTimingNotice = {
  phase: SessionTimingPhase;
  title: string;
  message: string;
  compactLabel: string;
  announcement: string;
};

export type ActiveECounselingTiming = {
  phase: SessionTimingPhase;
  notice: SessionTimingNotice | null;
  endsAt: string | null;
};

// Recommended user-facing copy (EC-1 Option A, pending GCO wording review)
export const TIMING_COPY = {
  APPROACHING_END: {
    title: "Appointment ending soon",
    message: "Your appointment is scheduled to end in 10 minutes. Please prepare to wrap up and coordinate any next steps.",
    compactLabel: "10 min left",
    announcement: "Appointment ending soon. Your appointment is scheduled to end in 10 minutes. Please prepare to wrap up and coordinate any next steps.",
  },
  FINAL_REMINDER: {
    title: "5 minutes remaining",
    message: "Your scheduled appointment ends in 5 minutes.",
    compactLabel: "5 min left",
    announcement: "5 minutes remaining. Your scheduled appointment ends in 5 minutes.",
  },
  SCHEDULED_END_REACHED: {
    title: "Scheduled time reached",
    message: "The scheduled appointment time has ended. If your discussion is still ongoing, please coordinate the next steps.",
    compactLabel: "Past scheduled end",
    announcement: "Scheduled time reached. The scheduled appointment time has ended. If your discussion is still ongoing, please coordinate the next steps.",
  },
  OVERTIME: {
    title: "Past scheduled end",
    message: "The scheduled appointment time has passed.",
    compactLabel: "Past scheduled end",
    announcement: "Past scheduled end. The scheduled appointment time has passed.",
  },
} as const;

export const ONE_MINUTE_MS = 60 * 1000;

export function calculateTimingPhase({
  endsAt,
  now,
  connected = true,
}: {
  endsAt: string | null | undefined;
  now: number | Date;
  connected?: boolean;
}): SessionTimingPhase {
  if (!endsAt) return "NORMAL";
  const endsAtMs = typeof endsAt === "string" ? Date.parse(endsAt) : Number(endsAt);
  if (!Number.isFinite(endsAtMs)) return "NORMAL";

  const nowMs = typeof now === "number" ? now : now.getTime();
  if (!Number.isFinite(nowMs)) return "NORMAL";

  const remainingMs = endsAtMs - nowMs;

  if (remainingMs > TEN_MINUTES_MS) {
    return "NORMAL";
  }
  if (remainingMs > FIVE_MINUTES_MS) {
    // 10 to more than 5 minutes remaining (at exactly ends_at - 10 minutes, enters APPROACHING_END)
    return "APPROACHING_END";
  }
  if (remainingMs > 0) {
    // 5 minutes to just before scheduled end (at exactly ends_at - 5 minutes, enters FINAL_REMINDER)
    return "FINAL_REMINDER";
  }
  if (remainingMs >= -ONE_MINUTE_MS) {
    // At scheduled end (the scheduled end minute window, e.g. at 3:00 PM)
    return connected ? "SCHEDULED_END_REACHED" : "NORMAL";
  }
  // After scheduled end, while connected (past scheduled end minute)
  return connected ? "OVERTIME" : "NORMAL";
}

export function getSessionTimingNotice(phase: SessionTimingPhase): SessionTimingNotice | null {
  if (phase === "NORMAL") return null;
  return {
    phase,
    ...TIMING_COPY[phase],
  };
}

export function getNextTimingDelayMs({
  endsAt,
  now,
}: {
  endsAt: string | null | undefined;
  now: number | Date;
}): number | null {
  if (!endsAt) return null;
  const endsAtMs = typeof endsAt === "string" ? Date.parse(endsAt) : Number(endsAt);
  if (!Number.isFinite(endsAtMs)) return null;

  const nowMs = typeof now === "number" ? now : now.getTime();
  if (!Number.isFinite(nowMs)) return null;

  const remainingMs = endsAtMs - nowMs;

  if (remainingMs > TEN_MINUTES_MS) {
    return remainingMs - TEN_MINUTES_MS;
  }
  if (remainingMs > FIVE_MINUTES_MS) {
    return remainingMs - FIVE_MINUTES_MS;
  }
  if (remainingMs > 0) {
    return remainingMs;
  }
  if (remainingMs >= -ONE_MINUTE_MS) {
    // Delay until scheduled end window transitions to OVERTIME
    return remainingMs + ONE_MINUTE_MS + 1;
  }
  return null;
}

export function getTimingTransitionAnnouncement({
  previousPhase,
  currentPhase,
}: {
  previousPhase: SessionTimingPhase | null;
  currentPhase: SessionTimingPhase;
}): string | null {
  if (currentPhase === "NORMAL") return null;
  if (currentPhase === previousPhase) return null;

  // The at-end transition should provide the scheduled-end announcement
  if (
    (currentPhase === "SCHEDULED_END_REACHED" || currentPhase === "OVERTIME") &&
    previousPhase !== "SCHEDULED_END_REACHED" &&
    previousPhase !== "OVERTIME"
  ) {
    return TIMING_COPY.SCHEDULED_END_REACHED.announcement;
  }

  // If transitioning from SCHEDULED_END_REACHED to OVERTIME, no repeated announcement
  if (previousPhase === "SCHEDULED_END_REACHED" && currentPhase === "OVERTIME") {
    return null;
  }

  return TIMING_COPY[currentPhase].announcement;
}

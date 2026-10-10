"use client";

import { useState } from "react";

import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

// Appointment times change whenever anyone books, cancels, or reschedules, so an open time picker
// rechecks them itself rather than keeping the portal's 30-second cache: every 15 seconds while
// the page is visible, as soon as the window regains focus, and when the connection returns. The
// server still revalidates every booking and reschedule; this keeps the picker from offering
// times that are already gone. It applies only to the booking and reschedule slot queries.
export const APPOINTMENT_SLOT_REFRESH_MS = 15_000;

export const appointmentSlotFreshness = {
  staleTime: 0,
  refetchInterval: APPOINTMENT_SLOT_REFRESH_MS,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: true,
  refetchOnReconnect: true,
} as const;

export const SLOT_NO_LONGER_AVAILABLE =
  "The selected time is no longer available. Choose another available time.";
export const SLOT_JUST_TAKEN = "That time was just taken. Choose another available time.";
export const SLOTS_NOT_RECHECKED =
  "Available times could not be rechecked. Retry before choosing a time.";

type Slot = { starts_at: string };

export function slotIsOffered(items: readonly Slot[] | undefined, startsAt: string): boolean {
  return Boolean(startsAt) && (items ?? []).some((slot) => slot.starts_at === startsAt);
}

// After a fresh slot list arrives, a selection it no longer offers is dropped rather than kept for
// a review the server would refuse.
export function reconcileSlotSelection(
  selected: string,
  items: readonly Slot[] | undefined,
): { selected: string; lost: boolean } {
  if (!selected || items === undefined || slotIsOffered(items, selected)) {
    return { selected, lost: false };
  }
  return { selected: "", lost: true };
}

export function isSlotTakenError(error: unknown): boolean {
  if (!(error instanceof CompassApiError)) return false;
  const code = readApiErrorCode(error.body);
  return code === "appointment_time_unavailable" || code === "appointment_time_conflict";
}

// The chosen time for one slot query, checked against each slot list the query receives.
// `dataUpdatedAt` changes with every successful response, including background rechecks.
export function useSlotSelection(items: readonly Slot[] | undefined, dataUpdatedAt: number) {
  const [selected, setSelected] = useState("");
  const [lost, setLost] = useState(false);
  const [checkedAt, setCheckedAt] = useState(dataUpdatedAt);

  if (checkedAt !== dataUpdatedAt) {
    setCheckedAt(dataUpdatedAt);
    const next = reconcileSlotSelection(selected, items);
    if (next.lost) {
      setSelected(next.selected);
      setLost(true);
    }
  }

  return {
    selected,
    // True after a recheck removed the chosen time; cleared by the next choice.
    lost,
    select(next: string) {
      setSelected(next);
      setLost(false);
    },
    clear() {
      setSelected("");
      setLost(false);
    },
    // The server or a pre-submit recheck says the chosen time is gone.
    drop() {
      setSelected("");
      setLost(true);
    },
  };
}

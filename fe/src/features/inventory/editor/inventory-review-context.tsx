"use client";

import { createContext, useContext } from "react";

import {
  emptyInventoryReviewHints,
  inventoryReviewHintId,
  type InventoryReviewHints,
} from "@/features/inventory/inventory-correction-targets";

// The answers a Counselor asked the Student to review, as the editor shows them. Outside the
// editor (and for a correction without targets) nothing is marked.
const InventoryReviewContext = createContext<InventoryReviewHints>(emptyInventoryReviewHints);

export const InventoryReviewProvider = InventoryReviewContext.Provider;

export type InventoryReviewHint = { id: string; text: string };
export type InventoryReview = { hint?: InventoryReviewHint; describedBy?: string };

function lookup(value: InventoryReviewHints, id: string | undefined): InventoryReview {
  if (!id) return {};
  const text = value.hints.get(id);
  return {
    hint: text ? { id: inventoryReviewHintId(id), text } : undefined,
    describedBy: value.describedBy.get(id),
  };
}

// For the element with this id: the hint it shows itself, and the hint ids its control adds to
// aria-describedby.
export function useInventoryReview(id: string | undefined): InventoryReview {
  return lookup(useContext(InventoryReviewContext), id);
}

// The same lookup for rows rendered in a loop.
export function useInventoryReviewLookup(): (id: string) => InventoryReview {
  const value = useContext(InventoryReviewContext);
  return (id) => lookup(value, id);
}

export function useInventoryReviewDetailsOpen(id: string): boolean {
  return useContext(InventoryReviewContext).openDetails.has(id);
}

// A review request is guidance, not a problem with the answer: no danger color, no alert role.
export function InventoryReviewHintText({ hint, className = "mt-1.5" }: { hint?: InventoryReviewHint; className?: string }) {
  if (!hint) return null;
  return (
    <p id={hint.id} className={`${className} text-xs font-medium leading-5 text-info`}>
      {hint.text}
    </p>
  );
}

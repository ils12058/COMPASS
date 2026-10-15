"use client";

import { createContext, useContext } from "react";

import {
  emptyExitInterviewReviewHints,
  exitInterviewReviewHintId,
  exitInterviewReviewHintText,
  exitInterviewSectionReviewId,
  type ExitInterviewCorrectionSectionId,
  type ExitInterviewReviewHints,
} from "@/features/exit-interviews/exit-interview-correction-targets";

// The answers an authorized reviewer asked the Student to review, as the editable form shows them.
// Outside the form (and for a correction without targets) nothing is marked.
const ExitInterviewReviewContext = createContext<ExitInterviewReviewHints>(emptyExitInterviewReviewHints);

export const ExitInterviewReviewProvider = ExitInterviewReviewContext.Provider;

export type ExitInterviewReviewHint = { id: string; text: string };
export type ExitInterviewReview = { hint?: ExitInterviewReviewHint; describedBy?: string };

function lookup(value: ExitInterviewReviewHints, id: string | undefined): ExitInterviewReview {
  if (!id) return {};
  const text = value.hints.get(id);
  return {
    hint: text ? { id: exitInterviewReviewHintId(id), text } : undefined,
    describedBy: value.describedBy.get(id),
  };
}

// For the element with this id: the hint it shows, and the hint id its control adds to
// aria-describedby.
export function useExitInterviewReview(id: string | undefined): ExitInterviewReview {
  return lookup(useContext(ExitInterviewReviewContext), id);
}

// The same lookup for rows rendered in a loop.
export function useExitInterviewReviewLookup(): (id: string) => ExitInterviewReview {
  const value = useContext(ExitInterviewReviewContext);
  return (id) => lookup(value, id);
}

// A review request is guidance, not a problem with the answer: no danger color, no alert role.
export function ExitInterviewReviewHintText({
  hint,
  className = "mt-1.5 block",
}: {
  hint?: ExitInterviewReviewHint;
  className?: string;
}) {
  if (!hint) return null;
  return (
    <span id={hint.id} className={`${className} text-xs font-medium leading-5 text-info`}>
      {hint.text}
    </span>
  );
}

// Where focus lands for a whole-section target.
export function ExitInterviewSectionReviewNote({ section }: { section: ExitInterviewCorrectionSectionId }) {
  const underReview = useContext(ExitInterviewReviewContext).sections.has(section);
  if (!underReview) return null;
  return (
    <p
      id={exitInterviewSectionReviewId(section)}
      tabIndex={-1}
      className="mt-2 rounded-sm text-sm font-medium leading-6 text-info focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
    >
      {exitInterviewReviewHintText.section}
    </p>
  );
}

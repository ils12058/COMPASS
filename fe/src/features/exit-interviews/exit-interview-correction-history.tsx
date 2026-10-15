import { useId } from "react";

import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader } from "@/components/ui/panel";
import type { ExitInterviewCorrectionTarget, PersonSummary, ReopenEventResponse } from "@/lib/api/generated/model";
import {
  exitInterviewCorrectionTargetTitle,
  readExitInterviewCorrectionTargets,
} from "@/features/exit-interviews/exit-interview-correction-targets";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";

// The reopening actor comes from the API; never assume which designation reopened it.
export function correctionReviewerName(event: ReopenEventResponse): string | null {
  const name = (event.reopened_by as Partial<PersonSummary> | null | undefined)?.display_name;
  return typeof name === "string" && name.trim() ? name.trim() : null;
}

// The answers a request named, in plain words. Only the pending request in the editable form passes
// onSelect; every other list is plain text, so a completed request never looks actionable.
function AnswersToReview({
  event,
  onSelect,
}: {
  event: ReopenEventResponse;
  onSelect?: (target: ExitInterviewCorrectionTarget) => void;
}) {
  const id = useId();
  // Events from before targets existed have none.
  const { targets, unknown } = readExitInterviewCorrectionTargets(event.targets);
  if (!targets.length && !unknown) return null;
  return (
    <div className="mt-3">
      <p id={`${id}-heading`} className="text-sm font-semibold text-ink">Answers to review</p>
      {onSelect ? (
        <p id={`${id}-help`} className="text-xs leading-5 text-muted">Select an answer to go to it in the form.</p>
      ) : null}
      <ul
        aria-labelledby={`${id}-heading`}
        className={onSelect ? "mt-1 space-y-0.5 text-sm text-ink" : "mt-1.5 list-disc space-y-1 pl-5 text-sm leading-6 text-ink"}
      >
        {targets.map((target) => (
          <li key={target}>
            {onSelect ? (
              <button
                type="button"
                aria-describedby={`${id}-help`}
                className="inline-flex min-h-9 items-center rounded-sm text-left font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                onClick={() => onSelect(target)}
              >
                {exitInterviewCorrectionTargetTitle(target)}
              </button>
            ) : (
              exitInterviewCorrectionTargetTitle(target)
            )}
          </li>
        ))}
        {unknown ? <li>{unknown === 1 ? "1 more part of the form" : `${unknown} more parts of the form`}</li> : null}
      </ul>
    </div>
  );
}

export function ExitInterviewCorrectionHistory({
  events,
  emphasizeLatest = false,
  onSelectTarget,
}: {
  events: readonly ReopenEventResponse[];
  emphasizeLatest?: boolean;
  // Only for the latest request of a draft the Student can edit.
  onSelectTarget?: (target: ExitInterviewCorrectionTarget) => void;
}) {
  const latest = events.at(-1);
  if (events.length === 0) return null;

  return (
    <>
      {emphasizeLatest && latest ? (
        <aside aria-labelledby="exit-interview-correction-heading">
          <Notice
            tone="warning"
            title={<h2 id="exit-interview-correction-heading" className="font-semibold text-ink">Correction requested</h2>}
          >
            <p className="text-muted">
              {correctionReviewerName(latest) ?? "An authorized reviewer"} reopened this Exit Interview for correction.
            </p>
            <p className="mt-2 whitespace-pre-wrap text-ink">
              <span className="font-semibold">Reason:</span> {latest.reason}
            </p>
            <AnswersToReview event={latest} onSelect={onSelectTarget} />
            <p className="mt-1 text-xs text-muted">
              Requested {formatExitInterviewDateTime(latest.reopened_at)}
            </p>
          </Notice>
        </aside>
      ) : null}

      {!emphasizeLatest || events.length > 1 ? (
        <Panel aria-labelledby="exit-interview-correction-history">
          <PanelHeader title="Correction history" titleId="exit-interview-correction-history" />
          <ol className="divide-y divide-border">
            {events.map((event) => (
              <li key={event.id} className="px-4 py-3.5 sm:px-5">
                <p className="whitespace-pre-wrap text-sm leading-6 text-ink">{event.reason}</p>
                <AnswersToReview event={event} />
                <p className="mt-1 text-xs text-muted">
                  {correctionReviewerName(event) ?? "Authorized reviewer"} · {formatExitInterviewDateTime(event.reopened_at)}
                </p>
              </li>
            ))}
          </ol>
        </Panel>
      ) : null}
    </>
  );
}

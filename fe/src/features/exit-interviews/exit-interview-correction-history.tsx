import type { ReopenEventResponse } from "@/lib/api/generated/model";
import { ExitInterviewSection } from "@/features/exit-interviews/exit-interview-shared";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";

export function ExitInterviewCorrectionHistory({
  events,
  emphasizeLatest = false,
}: {
  events: readonly ReopenEventResponse[];
  emphasizeLatest?: boolean;
}) {
  const latest = events.at(-1);
  if (events.length === 0) return null;

  return (
    <>
      {emphasizeLatest && latest ? (
        <aside className="my-5 border-l-4 border-warning bg-warning/5 px-4 py-3" aria-labelledby="exit-interview-correction-heading">
          <h2 id="exit-interview-correction-heading" className="font-semibold text-ink">
            Correction requested
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            Head Guidance reopened this Exit Interview for correction.
          </p>
          <p className="mt-2 whitespace-pre-wrap text-sm text-ink">
            <span className="font-semibold">Reason:</span> {latest.reason}
          </p>
          <p className="mt-1 text-xs text-muted">
            Requested {formatExitInterviewDateTime(latest.reopened_at)}
          </p>
        </aside>
      ) : null}

      {!emphasizeLatest || events.length > 1 ? (
        <ExitInterviewSection title="Correction history" id="exit-interview-correction-history">
          <ol className="mt-3 space-y-4 border-l border-border pl-4">
            {events.map((event) => (
              <li key={event.id}>
                <p className="whitespace-pre-wrap text-sm leading-6 text-ink">{event.reason}</p>
                <p className="mt-1 text-xs text-muted">
                  {event.reopened_by.display_name} · {formatExitInterviewDateTime(event.reopened_at)}
                </p>
              </li>
            ))}
          </ol>
        </ExitInterviewSection>
      ) : null}
    </>
  );
}

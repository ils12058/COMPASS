import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader } from "@/components/ui/panel";
import type { PersonSummary, ReopenEventResponse } from "@/lib/api/generated/model";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";

// The reopening actor comes from the API; never assume which designation reopened it.
export function correctionReviewerName(event: ReopenEventResponse): string | null {
  const name = (event.reopened_by as Partial<PersonSummary> | null | undefined)?.display_name;
  return typeof name === "string" && name.trim() ? name.trim() : null;
}

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

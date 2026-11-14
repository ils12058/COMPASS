import { Panel, PanelHeader } from "@/components/ui/panel";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { authorizationLabel } from "@/features/counseling/continuity/continuity-presentation";
import type { CounselingCaseDetailResponse } from "@/lib/api/generated/model";
import { caseEventSummary } from "./case-presentation";
import { closureReasonLabels, closureOutcomeLabels, reopenReasonLabels } from "./closure-presentation";

// Every row is an explicit backend historical fact. Sorting joins existing bounded histories;
// current status never creates a guessed opening, closure or ownership event.
export function caseHistoryRows(item: CounselingCaseDetailResponse) {
  return [
    ...item.history.map(event => ({ id: event.id, occurredAt: event.occurred_at, summary: caseEventSummary(event), actor: event.actor.display_name, detail: event.primary_counselor.id !== event.actor.id ? `Responsible counselor: ${event.primary_counselor.display_name}` : null })),
    ...(item.continuity?.history ?? []).map(event => ({ id: event.id, occurredAt: event.occurred_at, summary: `Transfer ${event.kind} · ${event.reference_code}`, actor: event.actor.display_name, detail: event.authorization_route ? authorizationLabel(event.authorization_route) : null })),
    ...(item.continuity?.coverage_history ?? []).map(event => ({ id: event.id, occurredAt: event.occurred_at, summary: `Coverage ${event.kind} · ${event.reference_code}`, actor: event.actor.display_name, detail: event.authorization_route ? authorizationLabel(event.authorization_route) : null })),
    ...(item.closures ?? []).flatMap(closure => [
      { id: `closure-${closure.id}`, occurredAt: closure.closed_at, summary: `Case closed · ${closureReasonLabels[closure.reason]} · ${closureOutcomeLabels[closure.outcome]}`, actor: closure.closed_by.display_name, detail: null },
      ...(closure.reopened_at && closure.reopened_by && closure.reopen_reason ? [{ id: `reopen-${closure.id}`, occurredAt: closure.reopened_at, summary: `Case reopened · ${reopenReasonLabels[closure.reopen_reason]}`, actor: closure.reopened_by.display_name, detail: null }] : []),
    ]),
  ].sort((first, second) => Date.parse(first.occurredAt) - Date.parse(second.occurredAt) || first.id.localeCompare(second.id));
}

export function CaseHistoryPanel({ item }: { item: CounselingCaseDetailResponse }) {
  const rows = caseHistoryRows(item);
  return <Panel className="mt-5" aria-labelledby="case-history-heading">
    <PanelHeader title="Case history" titleId="case-history-heading" />
    <ol className="divide-y divide-border">{rows.map(event => <li key={event.id} className="px-4 py-3 sm:px-5">
      <p className="text-sm text-ink">{event.summary}</p>
      <p className="mt-0.5 text-xs text-muted">{formatCounselingDateTime(event.occurredAt)} · {event.actor}</p>
      {event.detail ? <p className="mt-1 text-sm text-muted">{event.detail}</p> : null}
    </li>)}</ol>
  </Panel>;
}

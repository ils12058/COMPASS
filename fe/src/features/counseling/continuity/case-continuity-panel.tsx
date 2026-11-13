"use client";

import { ArrowRightLeft, UserRoundCheck } from "lucide-react";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { PageActionLink } from "@/components/ui/page-action";
import { Panel, PanelHeader, PanelBody, PanelSection } from "@/components/ui/panel";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import type { CounselingCaseDetailResponse } from "@/lib/api/generated/model";
import { arrangementLabel, authorizationLabel, coverageHref, coveragePrepareHref, coverageStateLabel, transferHref, transferPrepareHref } from "./continuity-presentation";

export function CaseContinuityPanel({ item, returnTo, confirmed }: { item: CounselingCaseDetailResponse; returnTo: string; confirmed: boolean }) {
  const continuity = item.continuity;
  if (!continuity) return null;
  return <Panel className="mt-5" aria-labelledby="case-continuity-heading">
    <PanelHeader title="Continuity" titleId="case-continuity-heading" actions={confirmed && item.status === "ACTIVE" && (continuity.can_transfer || continuity.can_arrange_coverage) ? <div className="flex flex-wrap gap-2">
      {continuity.can_arrange_coverage ? <PageActionLink icon={UserRoundCheck} label="Arrange coverage" variant="secondary" href={withWorkflowReturn(coveragePrepareHref(item.id), returnTo)} /> : null}
      {continuity.can_transfer ? <PageActionLink icon={ArrowRightLeft} label="Transfer case" variant="secondary" href={withWorkflowReturn(transferPrepareHref(item.id), returnTo)} /> : null}
    </div> : null} />
    <PanelBody>
      <p className="text-sm">Primary counselor: <span className="font-semibold">{item.primary_counselor.display_name}</span></p>
      {continuity.transfers.length ? <ul className="mt-3 divide-y divide-border">
        {continuity.transfers.map(transfer => <li key={transfer.id} className="py-3 text-sm">
          <Link className="font-semibold text-brand underline" href={withWorkflowReturn(transferHref(transfer.id), returnTo)}>{transfer.reference_code}</Link>
          <p className="mt-1">{arrangementLabel(transfer)}</p>
          {transfer.review_expires_at && transfer.state === "AUTHORIZED" ? <p className="mt-1 text-muted">Review until {formatCounselingDateTime(transfer.review_expires_at)}</p> : null}
          {transfer.authorization_route ? <p className="mt-1 text-muted">{authorizationLabel(transfer.authorization_route)}</p> : null}
        </li>)}
      </ul> : <p className="mt-2 text-sm text-muted">No transfer is pending.</p>}
      {continuity.coverages?.length ? <ul className="mt-3 divide-y divide-border" aria-label="Temporary coverage">
        {continuity.coverages.map(coverage => <li key={coverage.id} className="py-3 text-sm">
          <Link className="font-semibold text-brand underline" href={withWorkflowReturn(coverageHref(coverage.id), returnTo)}>{coverage.reference_code}</Link>
          <p className="mt-1">{coverageStateLabel(coverage, formatCounselingDateTime)}</p>
          {coverage.review_expires_at && coverage.state === "AUTHORIZED" ? <p className="mt-1 text-muted">Review until {formatCounselingDateTime(coverage.review_expires_at)}</p> : null}
          {coverage.authorization_route ? <p className="mt-1 text-muted">{authorizationLabel(coverage.authorization_route)}</p> : null}
          {coverage.recovery_required_count ? <p className="mt-1 text-warning">{coverage.recovery_required_count} delegated action{coverage.recovery_required_count === 1 ? "" : "s"} need authorized recovery.</p> : null}
        </li>)}
      </ul> : <p className="mt-2 text-sm text-muted">No temporary coverage is arranged.</p>}
    </PanelBody>
    {continuity.responsibility.length ? <PanelSection title="Responsibility history" titleId="case-responsibility-heading" level={3}><ul className="divide-y divide-border">{continuity.responsibility.map((period, index) => <li key={period.transfer_id ?? `opening-${index}`} className="py-2 text-sm"><p className="font-semibold">{period.counselor.display_name}</p><p className="mt-1 text-muted">From {formatCounselingDateTime(period.started_at)}{period.ended_at ? ` until ${formatCounselingDateTime(period.ended_at)}` : " · Current primary counselor"}</p></li>)}</ul></PanelSection> : null}
    {continuity.coverage_history?.length ? <PanelSection title="Coverage activity" titleId="case-coverage-activity-heading" level={3}><ul className="divide-y divide-border">{continuity.coverage_history.map(event => <li key={event.id} className="py-2 text-sm"><p>{event.reference_code} · {event.kind.charAt(0).toUpperCase() + event.kind.slice(1)} · {event.actor.display_name}</p><p className="mt-1 text-muted">{formatCounselingDateTime(event.occurred_at)}</p>{!event.independent_authorization && event.authorization_route === "OWNER_TO_HEAD" ? <p className="mt-1 text-muted">Personally requested by the primary Counselor; no independent Head authorization.</p> : null}</li>)}</ul></PanelSection> : null}
    {continuity.history.length ? <PanelSection title="Continuity activity" titleId="case-continuity-activity-heading" level={3}><ul className="divide-y divide-border">{continuity.history.map(event => <li key={event.id} className="py-2 text-sm"><p>{event.reference_code} · {event.kind.charAt(0).toUpperCase() + event.kind.slice(1)} · {event.actor.display_name}</p><p className="mt-1 text-muted">{formatCounselingDateTime(event.occurred_at)}</p>{event.authorization_route === "OWNER_TO_HEAD" ? <p className="mt-1 text-muted">Personally requested by the primary Counselor; no independent Head authorization.</p> : null}</li>)}</ul></PanelSection> : null}
  </Panel>;
}

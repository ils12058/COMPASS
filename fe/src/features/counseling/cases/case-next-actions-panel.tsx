"use client";

import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { Panel, PanelHeader, PanelMessage, PanelFooter } from "@/components/ui/panel";
import { buttonVariants } from "@/components/ui/button";
import { followupActionLabel } from "@/features/guidance-followups/followups-presentation";
import { statusLabel } from "@/features/guidance-followups/followups-shared";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import type { CounselingCaseDetailResponse } from "@/lib/api/generated/model";

export function CaseNextActionsPanel({ item, returnTo, confirmed }: { item: CounselingCaseDetailResponse; returnTo: string; confirmed: boolean }) {
  return <Panel className="mt-5" aria-labelledby="case-next-actions-heading">
    <PanelHeader title="Next actions" titleId="case-next-actions-heading" actions={confirmed && item.status === "ACTIVE" && item.can_add_next_action ? <Link className={buttonVariants({ variant: "secondary" })} href={withWorkflowReturn(`/portal/follow-ups/new?case_id=${encodeURIComponent(item.id)}`, returnTo)}>Add next action</Link> : null} />
    {!item.next_actions_available ? <PanelMessage>Next actions are unavailable to your account.</PanelMessage>
      : item.next_actions.length ? <ul className="divide-y divide-border">
        {item.next_actions.map(action => <li key={action.id} className="px-4 py-4 text-sm sm:px-5">
          <Link className="block break-words font-semibold text-brand underline underline-offset-4" href={withWorkflowReturn(`/portal/follow-ups/${action.id}`, returnTo)}>{followupActionLabel(action)}</Link>
          <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1"><span>Due {formatInstitutionalDateTime(action.due_at)}</span><span>{action.assigned_to_name}</span><span>{statusLabel(action.status)}{action.overdue ? " · Overdue" : ""}{action.post_closure_designated_at ? " · After closure" : ""}</span></div>
        </li>)}
      </ul> : <PanelMessage>No next actions are linked to this case.</PanelMessage>}
    {item.next_actions_available ? <PanelFooter>
      <Link className="text-sm font-semibold text-brand underline" href={withWorkflowReturn(`/portal/follow-ups?case_id=${encodeURIComponent(item.id)}&status=all`, returnTo)}>View all next actions</Link>
      {item.next_actions_has_more ? <p className="text-sm text-muted">More next actions are available in Follow-Ups.</p> : null}
    </PanelFooter> : null}
  </Panel>;
}

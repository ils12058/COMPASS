"use client";

import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { appointmentStatusLabel } from "@/features/appointments/appointments-shared";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import type { CounselingCaseAppointmentResponse, CounselingCaseDetailResponse } from "@/lib/api/generated/model";

export function CaseAppointmentsPanel({ item, returnTo, confirmed, onLink, onUnlink }: {
  item: CounselingCaseDetailResponse;
  returnTo: string;
  confirmed: boolean;
  onLink: () => void;
  onUnlink: (link: CounselingCaseAppointmentResponse) => void;
}) {
  return <Panel className="mt-5" aria-labelledby="case-appointments-heading">
    <PanelHeader title="Appointments" titleId="case-appointments-heading" actions={item.can_link_appointments ? <Button variant="secondary" disabled={!confirmed} onClick={onLink}>Link appointment</Button> : undefined} />
    {item.appointments.length ? <ul className="divide-y divide-border">
      {item.appointments.map(link => <li key={link.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-4 sm:px-5">
        <div className="min-w-0 flex-1 text-sm">
          {link.appointment ? <>
            {link.appointment.record_accessible ? <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`/portal/appointments/${link.appointment.id}`, returnTo)}>{link.appointment.reference_code}</Link> : <span className="font-semibold">{link.appointment.reference_code}</span>}
            <p className="mt-1">{formatCounselingDateTime(link.appointment.starts_at)} · {appointmentStatusLabel(link.appointment.status)}</p>
            {link.appointment.provider ? <p className="mt-1">{link.appointment.provider.display_name}</p> : null}
          </> : <p className="font-semibold">Appointment no longer available</p>}
          <p className="mt-1 text-muted">Linked by {link.linked_by.display_name} · {formatCounselingDateTime(link.linked_at)}</p>
          {link.removed_at ? <p className="mt-1 text-muted">Removed by {link.removed_by?.display_name} · {formatCounselingDateTime(link.removed_at)} · {link.removal_reason === "BELONGS_TO_ANOTHER_CASE" ? "Belongs to another case" : link.removal_reason === "NOT_PART_OF_THIS_CASE" ? "Not part of this case" : "Linked by mistake"}</p> : null}
        </div>
        {!link.removed_at && item.can_manage ? <Button variant="secondary" disabled={!confirmed} onClick={() => onUnlink(link)} aria-label={`Unlink appointment ${link.appointment?.reference_code ?? "from this case"}`}>Unlink</Button> : null}
      </li>)}
    </ul> : <PanelMessage>No appointments are linked to this case.</PanelMessage>}
  </Panel>;
}

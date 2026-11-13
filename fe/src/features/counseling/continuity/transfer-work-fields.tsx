"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { PanelSection } from "@/components/ui/panel";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { CaseTaskDisposition, CaseAppointmentDisposition, CaseAppointmentRetentionReason, type CaseTransferContextResponse } from "@/lib/api/generated/model";
import { appointmentDispositionLabels, enumChoice, retentionReasonLabels, taskDispositionLabels } from "./continuity-presentation";

export type TaskChoice = { disposition: CaseTaskDisposition | ""; title: string; due: string };
export type AppointmentChoice = { disposition: CaseAppointmentDisposition | ""; retention: CaseAppointmentRetentionReason | "" };

export function TransferWorkFields({ context, tasks, appointments, changeTask, changeAppointment, returnTo }: {
  context: CaseTransferContextResponse;
  tasks: Record<string, TaskChoice>;
  appointments: Record<string, AppointmentChoice>;
  changeTask: (id: string, choice: TaskChoice) => void;
  changeAppointment: (id: string, choice: AppointmentChoice) => void;
  returnTo: string;
}) {
  return <>
    <PanelSection title="2. Pending actions" titleId="transfer-tasks-heading" description="Every pending action needs a plan. Source records keep their own access permissions.">
      {context.tasks.length ? <ul className="divide-y divide-border">{context.tasks.map((task, index) => {
        const choice = tasks[task.task_id] ?? { disposition: "", title: "", due: "" };
        const title = task.title ?? `${task.category === "COUNSELING" ? "Counseling" : task.category} action ${index + 1}`;
        const valid = !choice.disposition || task.allowed_dispositions.includes(choice.disposition);
        return <li className="grid gap-3 py-3 first:pt-0" key={task.task_id}>
          <div><p className="text-sm font-semibold">{task.record_accessible ? <Link className="text-brand underline" href={withWorkflowReturn(`/portal/follow-ups/${task.task_id}`, returnTo)}>{title}</Link> : title}</p>
            <p className="mt-1 text-sm text-muted">Due {formatCounselingDateTime(task.due_at)} · {task.assignee.display_name} · {task.source_kind ? "Source-linked confidential action" : "Case action"}</p></div>
          <div className="grid gap-1"><Label htmlFor={`task-plan-${index}`}>Plan for action {index + 1}</Label><Select id={`task-plan-${index}`} value={valid ? choice.disposition : ""} required aria-invalid={!valid} onChange={event => changeTask(task.task_id, { ...choice, disposition: enumChoice(task.allowed_dispositions, event.target.value) ?? "" })}><option value="">Choose a disposition</option>{task.allowed_dispositions.map(value => <option value={value} key={value}>{taskDispositionLabels[value]}</option>)}</Select></div>
          {!valid ? <p role="alert" className="text-sm text-danger">This disposition is no longer available for the selected reason.</p> : null}
          {choice.disposition === "HAND_OVER_AS_NEW" ? <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1"><Label htmlFor={`successor-title-${index}`}>New action title</Label><Input id={`successor-title-${index}`} required maxLength={120} value={choice.title} onChange={event => changeTask(task.task_id, { ...choice, title: event.target.value })} /></div>
            <div className="grid gap-1"><Label htmlFor={`successor-due-${index}`}>New deadline (Philippine Time)</Label><Input id={`successor-due-${index}`} type="datetime-local" required value={choice.due} onChange={event => changeTask(task.task_id, { ...choice, due: event.target.value })} /></div>
            <p className="text-sm text-muted sm:col-span-2">The new case action uses this title and deadline. The original description is never copied.</p>
          </div> : null}
        </li>;
      })}</ul> : <p className="text-sm text-muted">No pending case actions.</p>}
    </PanelSection>
    <PanelSection title="3. Upcoming appointments" titleId="transfer-appointments-heading" description="Complete reassignment, rescheduling or cancellation through the existing Appointment actions before acceptance.">
      {context.appointments.length ? <ul className="divide-y divide-border">{context.appointments.map((appointment, index) => {
        const choice = appointments[appointment.link_id] ?? { disposition: "", retention: "" };
        return <li key={appointment.link_id} className="grid gap-3 py-3 first:pt-0">
          <div><p className="text-sm font-semibold">{appointment.record_accessible ? <Link className="text-brand underline" href={withWorkflowReturn(`/portal/appointments/${appointment.appointment_id}`, returnTo)}>{appointment.reference_code}</Link> : appointment.reference_code}</p><p className="mt-1 text-sm text-muted">{formatCounselingDateTime(appointment.starts_at)} · {appointment.provider.display_name}</p></div>
          <div className="grid gap-1"><Label htmlFor={`appointment-plan-${index}`}>Plan for {appointment.reference_code}</Label><Select id={`appointment-plan-${index}`} required value={choice.disposition} onChange={event => changeAppointment(appointment.link_id, { ...choice, disposition: enumChoice(Object.values(CaseAppointmentDisposition), event.target.value) ?? "" })}><option value="">Choose an appointment plan</option>{Object.values(CaseAppointmentDisposition).map(value => <option key={value} value={value}>{appointmentDispositionLabels[value]}</option>)}</Select></div>
          {choice.disposition === "RETAIN_WITH_PROVIDER" ? <div className="grid gap-1"><Label htmlFor={`retention-${index}`}>Why retain {appointment.provider.display_name}?</Label><Select id={`retention-${index}`} required value={choice.retention} onChange={event => changeAppointment(appointment.link_id, { ...choice, retention: enumChoice(Object.values(CaseAppointmentRetentionReason), event.target.value) ?? "" })}><option value="">Choose a reason</option>{Object.values(CaseAppointmentRetentionReason).map(value => <option key={value} value={value}>{retentionReasonLabels[value]}</option>)}</Select></div> : null}
        </li>;
      })}</ul> : <p className="text-sm text-muted">No upcoming linked appointments.</p>}
    </PanelSection>
  </>;
}

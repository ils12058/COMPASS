import Link from "next/link";
import { AppointmentStatusBadge, deliveryModeLabel, formatAppointmentTime } from "@/features/appointments/appointments-shared";
import type { AppointmentResponse } from "@/lib/api/generated/model";

export function HomeAgendaRow({ appointment, managed = false }: { appointment: AppointmentResponse; managed?: boolean }) {
  return <li>
    <Link href={`/portal/appointments/${appointment.id}`} aria-label={`Open ${managed ? "managed " : ""}appointment with ${appointment.student.display_name}`}
      className="grid min-h-11 min-w-0 gap-2 px-4 py-3 hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus @min-[20rem]/agenda:grid-cols-[6rem_minmax(0,1fr)] @min-[20rem]/agenda:gap-4 sm:px-5">
      <p className="text-sm font-semibold tabular-nums text-ink">
        <time dateTime={appointment.starts_at} className="block">{formatAppointmentTime(appointment.starts_at)}</time>
        <span className="block text-xs font-normal text-muted">to <time dateTime={appointment.ends_at}>{formatAppointmentTime(appointment.ends_at)}</time></span>
        <span className="sr-only"> Philippine Time</span>
      </p>
      <div className="min-w-0 [overflow-wrap:anywhere]">
        <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="text-sm font-semibold text-brand">{appointment.student.display_name}</h3><AppointmentStatusBadge status={appointment.status} /></div>
        <p className="mt-1 text-sm leading-6 text-muted">{appointment.service.name} · {deliveryModeLabel(appointment.delivery_mode)}</p>
        {managed ? <p className="text-sm leading-6 text-muted">Counselor: {appointment.provider.display_name}</p> : null}
      </div>
    </Link>
  </li>;
}

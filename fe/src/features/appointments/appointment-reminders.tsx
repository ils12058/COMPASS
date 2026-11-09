"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Button } from "@/components/ui/button";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { stepUpRequirement } from "@/features/account/security/step-up";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import {
  appointmentsPreviewReminders,
  getAppointmentsPreviewRemindersMutationKey,
  useAppointmentsSendReminders,
} from "@/lib/api/generated/appointments/appointments";

export const reminderReason = (code: string): string => ({
  ELIGIBLE: "Ready to send",
  QUEUED: "Reminder added to the notification queue",
  COOLDOWN: "A manual reminder was sent recently. Try again after three hours.",
  TOO_SOON: "This Appointment starts in less than 15 minutes.",
  NOT_SCHEDULED: "Only scheduled Appointments can receive reminders.",
  RECIPIENT_INACTIVE: "The Student account is not active.",
  NOT_AVAILABLE: "You don't have access to this Appointment.",
}[code] ?? "This appointment is not available for reminders.");

type Props = { selected: string[]; open: boolean; onClose: () => void; onComplete?: () => void };

export function ReminderSender(props: Props) {
  return props.open ? <ReminderConfirmation key={props.selected.join(",")} {...props} /> : null;
}

function ReminderConfirmation({ selected, onClose, onComplete }: Props) {
  const [requestKey] = useState(() => crypto.randomUUID());
  const [terminalFailure, setTerminalFailure] = useState(false);
  const continuation = useStepUpContinuation();
  const preview = useQuery({
    queryKey: [...getAppointmentsPreviewRemindersMutationKey(), selected],
    queryFn: ({ signal }) => appointmentsPreviewReminders({ appointment_ids: selected }, { signal }),
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
  const send = useAppointmentsSendReminders();
  const rows = send.data?.data.items ?? preview.data?.data.items ?? [];
  const available = rows.filter((item) => item.eligible).length;
  const needsStepUp = send.isError && stepUpRequirement(send.error) !== null && !terminalFailure;
  async function sendConfirmedReminders() {
    setTerminalFailure(false);
    const result = await continuation.run(
      () => send.mutateAsync({ data: { appointment_ids: selected, request_key: requestKey } }),
      { onFailure: () => setTerminalFailure(true) },
    );
    if (result) onComplete?.();
  }
  const recipients = <ul className="divide-y divide-border text-sm" aria-label="Reminder recipients">
    {rows.map((row) => <li key={row.appointment_id} className="py-2">
      <p className="font-medium text-ink">{row.student_name ?? "Appointment not accessible"}</p>
      {row.reference_code ? <p>{row.reference_code}</p> : null}
      <p>{send.isSuccess && row.accepted ? "Reminder queued." : reminderReason(row.reason)}</p>
    </li>)}
  </ul>;
  return <>
    <ConsequentialActionDialog
      open title={selected.length === 1 ? "Send Appointment reminder" : "Send Appointment reminders"}
      confirmLabel={`Send ${available} reminder${available === 1 ? "" : "s"}`}
      pendingLabel="Sending requests…" pending={send.isPending}
      confirmDisabled={!preview.isSuccess || preview.isFetching || available === 0}
      error={send.isError && !needsStepUp ? "Couldn't confirm your request. Retry with the same confirmation to avoid duplicate reminders." : null}
      onOpenChange={(next) => { if (!next) onClose(); }}
      onConfirm={() => void sendConfirmedReminders()}
      choices={!send.isSuccess ? <>
        {continuation.notice ? <p role="status" className="text-sm text-muted">{continuation.notice}</p> : null}
        {preview.isPending ? <p role="status">Checking Appointments…</p> : null}
        {preview.isError ? <p role="alert">Couldn&apos;t check the Appointments. Try again. <Button variant="secondary" onClick={() => void preview.refetch()}>Retry</Button></p> : recipients}
      </> : undefined}
      completed={send.isSuccess ? { title: "Reminder requests received", children: <>
        <p>{send.data.data.accepted} accepted, {send.data.data.skipped} skipped. Email and browser delivery may still be pending.</p>
        {recipients}
      </> } : null}
    >
      <p>Review the Students before sending. Each Student listed as ready receives a reminder in COMPASS. Email and browser notifications follow when available.</p>
    </ConsequentialActionDialog>
    <StepUpDialog open={continuation.open} requirement={continuation.requirement} onOpenChange={(next) => continuation.setOpen(next)} isContinuing={continuation.isContinuing} onVerified={continuation.continueAfterVerification} />
  </>;
}

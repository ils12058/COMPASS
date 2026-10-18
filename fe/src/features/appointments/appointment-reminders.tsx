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
  TOO_SOON: "This appointment starts in less than 15 minutes.",
  NOT_SCHEDULED: "Only scheduled appointments can receive reminders.",
  RECIPIENT_INACTIVE: "The student account is not active.",
  NOT_AVAILABLE: "This appointment is not available to you.",
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
      <p className="font-medium text-ink">{row.student_name ?? "Unavailable appointment"}</p>
      {row.reference_code ? <p>{row.reference_code}</p> : null}
      <p>{send.isSuccess && row.accepted ? "Reminder queued." : reminderReason(row.reason)}</p>
    </li>)}
  </ul>;
  return <>
    <ConsequentialActionDialog
      open title={selected.length === 1 ? "Send appointment reminder" : "Send appointment reminders"}
      confirmLabel={`Send ${available} reminder${available === 1 ? "" : "s"}`}
      pendingLabel="Sending requests…" pending={send.isPending}
      confirmDisabled={!preview.isSuccess || preview.isFetching || available === 0}
      error={send.isError && !needsStepUp ? "We couldn't confirm the request. Retry keeps the same confirmation and prevents duplicate reminders." : null}
      onOpenChange={(next) => { if (!next) onClose(); }}
      onConfirm={() => void sendConfirmedReminders()}
      choices={!send.isSuccess ? <>
        {continuation.notice ? <p role="status" className="text-sm text-muted">{continuation.notice}</p> : null}
        {preview.isPending ? <p role="status">Checking appointments…</p> : null}
        {preview.isError ? <p role="alert">We could not check the appointments. <Button variant="secondary" onClick={() => void preview.refetch()}>Retry</Button></p> : recipients}
      </> : undefined}
      completed={send.isSuccess ? { title: "Reminder requests received", children: <>
        <p>{send.data.data.accepted} accepted, {send.data.data.skipped} skipped. Email and browser delivery may still be pending.</p>
        {recipients}
      </> } : null}
    >
      <p>Review the students before sending. Each eligible student receives a reminder in COMPASS. Email and browser notifications follow when available.</p>
    </ConsequentialActionDialog>
    <StepUpDialog open={continuation.open} requirement={continuation.requirement} onOpenChange={(next) => continuation.setOpen(next)} isContinuing={continuation.isContinuing} onVerified={continuation.continueAfterVerification} />
  </>;
}

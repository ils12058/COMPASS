"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Notice } from "@/components/ui/notice";
import { formatAppointmentDateTime } from "@/features/appointments/appointments-shared";
import {
  ActualTimeFields,
  actualTimeInputId,
  actualTimeIssues,
  firstActualTimeIssue,
  type ActualTimeField,
} from "@/features/counseling/actual-time-fields";
import { unconfirmedFinishMessage } from "@/features/counseling/finish-counseling-availability";
import { counselingDeliveryModeLabel, counselingErrorMessage } from "@/features/counseling/counseling-shared";
import { encounterProvenanceNote } from "@/features/counseling/record-encounter-form";
import { AppointmentStatus, type AppointmentDetailResponse, type CounselingFinishResponse } from "@/lib/api/generated/model";
import { useCounselingFinishAppointment } from "@/lib/api/generated/counseling/counseling";
import { CompassApiError } from "@/lib/api/errors";
import { institutionalDateTimeInputToISO } from "@/lib/institutional-time";

const TIME_ID_PREFIX = "finish-counseling";
const OCCURRED_INPUT_ID = "finish-counseling-occurred";

export type FinishCounselingDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  appointment: AppointmentDetailResponse;
  onFinished: (
    result: CounselingFinishResponse,
    wasCompleted: boolean,
  ) => void | Promise<void>;
  onStale: (message: string) => void | Promise<void>;
  onCheckAgain: () => Promise<boolean>;
  onUncertainClose: () => void;
  // Where focus goes when Finish is replaced by another action after a confirmed finish.
  onCloseAutoFocus?: (event: Event) => void;
};

// One action records the Encounter and completes the Appointment, so the actual times are entered
// here rather than in a separate recording flow.
export function FinishCounselingDialog({
  open,
  onOpenChange,
  appointment,
  onFinished,
  onStale,
  onCheckAgain,
  onUncertainClose,
  onCloseAutoFocus,
}: FinishCounselingDialogProps) {
  const [startedAt, setStartedAt] = useState("");
  const [endedAt, setEndedAt] = useState("");
  const [occurred, setOccurred] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [checking, setChecking] = useState(false);
  const [stillUnconfirmed, setStillUnconfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const finish = useCounselingFinishAppointment({ mutation: { retry: false } });

  // The dialog stays mounted so Cancel keeps the entered times, but a reopened dialog never shows
  // the previous attempt's result.
  function changeOpen(next: boolean) {
    if (!next) {
      setUncertain(false);
      setChecking(false);
      setStillUnconfirmed(false);
      setAttempted(false);
      setError(null);
    }
    onOpenChange(next);
  }

  const wasCompleted = appointment.status === AppointmentStatus.COMPLETED;
  const timeIssues = actualTimeIssues(startedAt, endedAt, null);

  function changeTime(field: ActualTimeField, value: string) {
    if (field === "start") setStartedAt(value);
    else setEndedAt(value);
    setError(null);
  }

  async function checkAgain() {
    setChecking(true);
    try {
      const confirmed = await onCheckAgain();
      setStillUnconfirmed(!confirmed);
      // A confirmed finish closes the dialog through the caller, so clear this result here.
      if (confirmed) setUncertain(false);
    } finally {
      setChecking(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || uncertain) return;
    setError(null);
    const now = Date.now();
    const invalid = firstActualTimeIssue(actualTimeIssues(startedAt, endedAt, now));
    if (!occurred || invalid) {
      setAttempted(true);
      if (invalid) document.getElementById(actualTimeInputId(TIME_ID_PREFIX, invalid))?.focus();
      return;
    }
    const started = institutionalDateTimeInputToISO(startedAt);
    const ended = institutionalDateTimeInputToISO(endedAt);
    if (!started || !ended) return;

    setSubmitting(true);
    try {
      const response = await finish.mutateAsync({
        appointmentId: appointment.id,
        data: { actual_started_at: started, actual_ended_at: ended, counseling_occurred: true },
      });
      setStartedAt("");
      setEndedAt("");
      setOccurred(false);
      setAttempted(false);
      await onFinished(response.data, wasCompleted);
    } catch (caught) {
      if (!(caught instanceof CompassApiError) || caught.status >= 500) {
        setUncertain(true);
        setStillUnconfirmed(false);
        setError(null);
        return;
      }
      if (caught.status === 409) {
        await onStale(counselingErrorMessage(caught, "Couldn't finish the Appointment."));
        return;
      }
      setError(counselingErrorMessage(caught, "Couldn't finish the Appointment."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="max-w-3xl" dismissible={!submitting && !uncertain} onCloseAutoFocus={onCloseAutoFocus}>
        <DialogTitle>Finish counseling</DialogTitle>
        <DialogDescription>
          {wasCompleted
            ? "This records the Counseling Encounter for this completed Appointment."
            : "This records the Counseling Encounter and marks the Appointment completed."}
        </DialogDescription>
        <form noValidate onSubmit={submit} className="mt-5">
          <dl className="grid gap-x-8 gap-y-3 rounded-sm bg-surface-subtle px-4 py-3.5 sm:grid-cols-2">
            <div className="min-w-0">
              <dt className="text-xs font-semibold text-muted">Student</dt>
              <dd className="mt-1 break-words text-sm font-semibold text-ink">{appointment.student.display_name}</dd>
              <dd className="mt-1 break-words text-xs text-muted">Institutional ID: {appointment.student.institutional_id || "Not provided"}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs font-semibold text-muted">Delivery</dt>
              <dd className="mt-1 text-sm text-ink">{counselingDeliveryModeLabel(appointment.delivery_mode)}</dd>
            </div>
            <div className="min-w-0 sm:col-span-2">
              <dt className="text-xs font-semibold text-muted">Scheduled</dt>
              <dd className="mt-1 text-sm text-ink">{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</dd>
            </div>
            <div className="min-w-0 sm:col-span-2">
              <dt className="text-xs font-semibold text-muted">Appointment</dt>
              <dd className="mt-1 break-words text-sm text-ink">{appointment.reference_code}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-muted">{encounterProvenanceNote("APPOINTMENT")}</p>
          <div className="mt-5">
            <ActualTimeFields
              idPrefix={TIME_ID_PREFIX}
              startedAt={startedAt}
              endedAt={endedAt}
              onChange={changeTime}
              issues={timeIssues}
              attempted={attempted}
              disabled={submitting || uncertain}
              scheduled
            />
          </div>
          <div className="mt-5">
            <label className="flex items-start gap-3 text-sm leading-6 text-ink" htmlFor={OCCURRED_INPUT_ID}>
              <input
                id={OCCURRED_INPUT_ID}
                type="checkbox"
                className="mt-1 h-4 w-4 shrink-0 accent-brand"
                checked={occurred}
                disabled={submitting || uncertain}
                aria-invalid={attempted && !occurred ? true : undefined}
                onChange={(event) => { setOccurred(event.target.checked); setError(null); }}
              />
              <span>
                <span className="font-semibold">Counseling took place.</span>
                <span className="mt-1 block text-xs text-muted">Confirm that you met with this Student for Counseling.</span>
              </span>
            </label>
            {attempted && !occurred ? (
              <p role="alert" className="mt-2 text-sm text-danger">Confirm that Counseling took place before finishing.</p>
            ) : null}
          </div>
          {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
          {uncertain ? (
            // Escape cannot hide this result; checking is a deliberate choice and never replays the
            // request (ADR-091).
            <Notice
              role="alert"
              tone="warning"
              className="mt-4"
              action={(
                <>
                  <Button variant="secondary" disabled={checking} onClick={() => void checkAgain()}>
                    {checking ? "Checking…" : "Check again"}
                  </Button>
                  <Button variant="secondary" onClick={() => { onUncertainClose(); changeOpen(false); }}>Close</Button>
                </>
              )}
            >
              <p className="text-ink">{unconfirmedFinishMessage}</p>
              {stillUnconfirmed ? <p className="mt-1">The result is still not confirmed. Wait a moment and check again.</p> : null}
            </Notice>
          ) : (
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <Button type="submit" disabled={submitting} aria-busy={submitting}>{submitting ? "Finishing…" : "Finish counseling"}</Button>
              <Button variant="secondary" disabled={submitting} onClick={() => changeOpen(false)}>Cancel</Button>
            </div>
          )}
        </form>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { appointmentStatusLabel, formatAppointmentDateTime } from "@/features/appointments/appointments-shared";
import { ActualTimeFields, actualTimeInputId, actualTimeIssues, firstActualTimeIssue, type ActualTimeField } from "@/features/counseling/actual-time-fields";
import { counselingDeliveryModeLabel, counselingErrorMessage, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import type { CounselingEncounterResponse, CounselingUpdateRequest } from "@/lib/api/generated/model";
import { CounselingEntryMode, DeliveryMode } from "@/lib/api/generated/model";
import {
  getCounselingGetEncounterQueryKey,
  getCounselingListEncounterAppointmentCandidatesQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingListEncounterAppointmentCandidates,
  useCounselingUpdateEncounter,
} from "@/lib/api/generated/counseling/counseling";
import {
  institutionalDateTimeInputToISO,
  isoToInstitutionalDateTimeInput,
} from "@/lib/institutional-time";

// Saved times open with their seconds, so an untouched time is never truncated.
export function savedEncounterTimeInput(value: string): string {
  return isoToInstitutionalDateTimeInput(value, { includeSeconds: true });
}

export type EncounterCorrectionValues = {
  appointmentId: string;
  entryMode: CounselingEntryMode;
  deliveryMode: DeliveryMode;
  startedAt: string;
  endedAt: string;
};

// Only the facts the Counselor changed. A time is compared with the saved value as it opened in the
// form, so an untouched time keeps its stored precision; a changed time is read in the institutional
// zone. Null when a changed time cannot be read.
export function encounterCorrectionPayload(
  encounter: CounselingEncounterResponse,
  values: EncounterCorrectionValues,
): CounselingUpdateRequest | null {
  const startChanged = values.startedAt !== savedEncounterTimeInput(encounter.started_at);
  const endChanged = values.endedAt !== savedEncounterTimeInput(encounter.ended_at);
  const startedAt = startChanged ? institutionalDateTimeInputToISO(values.startedAt) : null;
  const endedAt = endChanged ? institutionalDateTimeInputToISO(values.endedAt) : null;
  if ((startChanged && !startedAt) || (endChanged && !endedAt)) return null;
  return {
    ...(values.appointmentId !== (encounter.appointment?.id ?? "") ? { appointment_id: values.appointmentId || null } : {}),
    ...(values.entryMode !== encounter.entry_mode ? { entry_mode: values.entryMode } : {}),
    ...(values.deliveryMode !== encounter.delivery_mode ? { delivery_mode: values.deliveryMode } : {}),
    ...(startedAt ? { started_at: startedAt } : {}),
    ...(endedAt ? { ended_at: endedAt } : {}),
  };
}

export function EncounterCorrectionForm({
  encounter,
  onClose,
}: {
  encounter: CounselingEncounterResponse;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [appointmentId, setAppointmentId] = useState(encounter.appointment?.id ?? "");
  const [entryMode, setEntryMode] = useState<CounselingEntryMode>(encounter.entry_mode);
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>(encounter.delivery_mode);
  const [startedAt, setStartedAt] = useState(savedEncounterTimeInput(encounter.started_at));
  const [endedAt, setEndedAt] = useState(savedEncounterTimeInput(encounter.ended_at));
  const [observedNow, setObservedNow] = useState<number | null>(null);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const update = useCounselingUpdateEncounter({ mutation: { retry: false } });
  const candidates = useCounselingListEncounterAppointmentCandidates(
    encounter.id,
    { page, page_size: 20 },
    { query: { retry: false } },
  );
  const items = candidates.data?.data.items ?? [];
  const selectedCandidate = items.find((item) => item.id === appointmentId);
  const currentAppointmentAvailable = encounter.appointment && !items.some((item) => item.id === encounter.appointment?.id);
  const selectedLabel = appointmentId
    ? selectedCandidate?.reference_code ?? (appointmentId === encounter.appointment?.id ? encounter.appointment.reference_code : "Selected Appointment")
    : "No Appointment link";
  const values = { appointmentId, entryMode, deliveryMode, startedAt, endedAt };
  const draft = encounterCorrectionPayload(encounter, values);
  const unchanged = draft !== null && Object.keys(draft).length === 0;
  const timeIssues = actualTimeIssues(startedAt, endedAt, observedNow);
  const missingAppointment = entryMode === "APPOINTMENT" && !appointmentId;

  function changeTime(field: ActualTimeField, value: string) {
    if (field === "start") setStartedAt(value);
    else setEndedAt(value);
    setObservedNow(Date.now());
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (update.isPending || unchanged) return;
    setError(null);
    const now = Date.now();
    const invalid = firstActualTimeIssue(actualTimeIssues(startedAt, endedAt, now));
    if (invalid || missingAppointment) {
      setAttempted(true);
      setObservedNow(now);
      document.getElementById(invalid ? actualTimeInputId("correction", invalid) : "correction-appointment")?.focus();
      return;
    }
    const data = encounterCorrectionPayload(encounter, values);
    if (!data) return;

    try {
      const response = await update.mutateAsync({ encounterId: encounter.id, data });
      queryClient.setQueryData(getCounselingGetEncounterQueryKey(encounter.id), response);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getCounselingGetEncounterQueryKey(encounter.id) }),
        queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getCounselingListEncounterAppointmentCandidatesQueryKey(encounter.id) }),
      ]);
      onClose();
    } catch (caught) {
      setError(counselingErrorMessage(caught, "The encounter couldn’t be corrected. Review the details and try again."));
    }
  }

  return (
    // Validation is COMPASS's own, per field; the backend still checks every save.
    <form noValidate onSubmit={submit} className="border-t border-brand-line px-4 py-5 sm:px-5" aria-labelledby="correct-encounter-heading">
      <h3 id="correct-encounter-heading" className="font-heading text-sm font-semibold uppercase tracking-[0.08em] text-brand">Correct encounter details</h3>
      <p className="mt-1 text-sm text-muted">Student, Counselor, Service, creator, and creation time cannot be changed.</p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2"><Label htmlFor="correction-entry-mode">Interaction origin</Label><Select id="correction-entry-mode" value={entryMode} disabled={update.isPending} onChange={(event) => { setEntryMode(event.target.value as CounselingEntryMode); setError(null); }}><option value="APPOINTMENT">Appointment</option><option value="WALK_IN">Walk-in</option><option value="CALLED_IN">Called-in</option><option value="REFERRED">Referred</option></Select></div>
        <div className="grid gap-2"><Label htmlFor="correction-delivery-mode">Delivery mode</Label><Select id="correction-delivery-mode" value={deliveryMode} disabled={update.isPending} onChange={(event) => { setDeliveryMode(event.target.value as DeliveryMode); setError(null); }}>{Object.values(DeliveryMode).map((mode) => <option key={mode} value={mode}>{counselingDeliveryModeLabel(mode)}</option>)}</Select></div>
      </div>

      <div className="mt-5 max-w-3xl">
        <Label htmlFor="correction-appointment">Appointment link</Label>
        {candidates.isPending ? <LoadingRegion label="Loading historical Appointment candidates…" className="mt-2"><Skeleton className="h-10 w-full" /></LoadingRegion> : candidates.isError ? <p role="alert" className="mt-2 text-sm text-danger">{counselingErrorMessage(candidates.error, "Historical Appointment candidates could not be loaded. Other factual details may still be corrected.")}</p> : null}
        <Select
          id="correction-appointment"
          value={appointmentId}
          disabled={update.isPending || candidates.isPending || candidates.isError}
          aria-invalid={missingAppointment ? true : undefined}
          aria-describedby={missingAppointment ? "correction-appointment-error" : "correction-appointment-selected"}
          onChange={(event) => {
            const nextId = event.target.value;
            setAppointmentId(nextId);
            if (!nextId) {
              if (entryMode === "APPOINTMENT") setEntryMode("WALK_IN");
            } else {
              setEntryMode("APPOINTMENT");
              const selected = items.find((item) => item.id === nextId);
              if (selected) setDeliveryMode(selected.delivery_mode);
            }
            setError(null);
          }}
          className="mt-2"
        >
          <option value="">No Appointment link</option>
          {currentAppointmentAvailable ? <option value={encounter.appointment?.id}>{encounter.appointment?.reference_code} · current link</option> : null}
          {items.map((item) => <option key={item.id} value={item.id}>{item.reference_code} · {formatCounselingDateTime(item.starts_at)} · {counselingDeliveryModeLabel(item.delivery_mode)} · {appointmentStatusLabel(item.status)}</option>)}
        </Select>
        {!candidates.isPending && !candidates.isError && items.length === 0 && !encounter.appointment ? <p className="mt-2 text-sm text-muted">No appointment candidates are available for this encounter.</p> : null}
        {!candidates.isPending && !candidates.isError ? <CanonicalPagination className="border-t-0 pb-0" label="Appointment candidate pages" page={candidates.data?.data.page ?? page} hasNext={candidates.data?.data.has_next ?? false} onPageChange={setPage} /> : null}
        {missingAppointment ? (
          <p id="correction-appointment-error" className="mt-2 text-sm text-danger">Select an Appointment, or choose a direct origin.</p>
        ) : (
          <p id="correction-appointment-selected" className="mt-2 text-xs text-muted">
            Selected: {selectedLabel}
            {selectedCandidate ? <> · Scheduled {formatAppointmentDateTime(selectedCandidate.starts_at, selectedCandidate.ends_at)}</> : null}
          </p>
        )}
      </div>

      <div className="mt-5">
        <ActualTimeFields
          idPrefix="correction"
          startedAt={startedAt}
          endedAt={endedAt}
          onChange={changeTime}
          issues={timeIssues}
          attempted={attempted}
          disabled={update.isPending}
          withSeconds
          scheduled={Boolean(appointmentId)}
        />
      </div>
      {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={unchanged || update.isPending} aria-busy={update.isPending}>{update.isPending ? "Saving corrections…" : "Save corrections"}</Button>
        <Button variant="secondary" disabled={update.isPending} onClick={onClose}>Cancel</Button>
      </div>
    </form>
  );
}

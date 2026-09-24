"use client";

import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { counselingDeliveryModeLabel, counselingErrorMessage, CounselingPagination } from "@/features/counseling/counseling-shared";
import type { CounselingEncounterResponse } from "@/lib/api/generated/model";
import { CounselingEntryMode, DeliveryMode } from "@/lib/api/generated/model";
import {
  getCounselingGetEncounterQueryKey,
  getCounselingListEncounterAppointmentCandidatesQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingListEncounterAppointmentCandidates,
  useCounselingUpdateEncounter,
} from "@/lib/api/generated/counseling/counseling";

function localDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "";
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function isoDateTime(value: string): string | null {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : date.toISOString();
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
  const [startedAt, setStartedAt] = useState(localDateTime(encounter.started_at));
  const [endedAt, setEndedAt] = useState(localDateTime(encounter.ended_at));
  const [observedNow, setObservedNow] = useState<number | null>(null);
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
  const unchanged = appointmentId === (encounter.appointment?.id ?? "") &&
    entryMode === encounter.entry_mode &&
    deliveryMode === encounter.delivery_mode &&
    startedAt === localDateTime(encounter.started_at) &&
    endedAt === localDateTime(encounter.ended_at);
  const startMillis = startedAt ? new Date(startedAt).getTime() : Number.NaN;
  const endMillis = endedAt ? new Date(endedAt).getTime() : Number.NaN;
  const timeInvalid = !Number.isFinite(startMillis) || !Number.isFinite(endMillis) || startMillis >= endMillis || (observedNow !== null && endMillis > observedNow);
  const missingAppointment = entryMode === "APPOINTMENT" && !appointmentId;
  const timeMessage = !startedAt || !endedAt
    ? "Enter the actual start and end times."
    : startMillis >= endMillis
      ? "The actual start must be before the end."
      : observedNow !== null && endMillis > observedNow
        ? "The actual end cannot be in the future."
        : null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (update.isPending || unchanged) return;
    setError(null);
    if (timeInvalid || endMillis > Date.now()) {
      setError("The actual start must be before the end, and the end cannot be in the future.");
      return;
    }
    if (missingAppointment) {
      setError("Select an Appointment or choose a direct origin before saving.");
      return;
    }
    const started = isoDateTime(startedAt);
    const ended = isoDateTime(endedAt);
    if (!started || !ended) {
      setError("Enter valid actual start and end times.");
      return;
    }

    const data = {
      ...(appointmentId !== (encounter.appointment?.id ?? "") ? { appointment_id: appointmentId || null } : {}),
      ...(entryMode !== encounter.entry_mode ? { entry_mode: entryMode } : {}),
      ...(deliveryMode !== encounter.delivery_mode ? { delivery_mode: deliveryMode } : {}),
      ...(startedAt !== localDateTime(encounter.started_at) ? { started_at: started } : {}),
      ...(endedAt !== localDateTime(encounter.ended_at) ? { ended_at: ended } : {}),
    };

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
      setError(counselingErrorMessage(caught, "Encounter details could not be corrected. Review the values and try again."));
    }
  }

  return (
    <form onSubmit={submit} className="mt-5 border-y border-border py-5" aria-labelledby="correct-encounter-heading">
      <h3 id="correct-encounter-heading" className="font-heading text-lg font-semibold text-ink">Correct encounter details</h3>
      <p className="mt-1 text-sm text-muted">Use this to correct how the completed interaction was recorded. Student, Counselor, Service, creator, and creation time cannot be changed.</p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2"><Label htmlFor="correction-entry-mode">Interaction origin</Label><select id="correction-entry-mode" value={entryMode} disabled={update.isPending} onChange={(event) => { setEntryMode(event.target.value as CounselingEntryMode); setError(null); }} className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"><option value="APPOINTMENT">Appointment</option><option value="WALK_IN">Walk-in</option><option value="CALLED_IN">Called-in</option><option value="REFERRED">Referred</option></select></div>
        <div className="grid gap-2"><Label htmlFor="correction-delivery-mode">Delivery mode</Label><select id="correction-delivery-mode" value={deliveryMode} disabled={update.isPending} onChange={(event) => { setDeliveryMode(event.target.value as DeliveryMode); setError(null); }} className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{Object.values(DeliveryMode).map((mode) => <option key={mode} value={mode}>{counselingDeliveryModeLabel(mode)}</option>)}</select></div>
      </div>

      <div className="mt-5 max-w-3xl">
        <Label htmlFor="correction-appointment">Appointment link</Label>
        {candidates.isPending ? <div aria-busy="true" className="mt-2"><Skeleton className="h-10 w-full" /></div> : candidates.isError ? <p role="alert" className="mt-2 text-sm text-danger">{counselingErrorMessage(candidates.error, "Historical Appointment candidates could not be loaded. Other factual details may still be corrected.")}</p> : null}
        <select id="correction-appointment" value={appointmentId} disabled={update.isPending || candidates.isPending || candidates.isError} onChange={(event) => {
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
        }} className="mt-2 min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          <option value="">No Appointment link</option>
          {currentAppointmentAvailable ? <option value={encounter.appointment?.id}>{encounter.appointment?.reference_code} · current link</option> : null}
          {items.map((item) => <option key={item.id} value={item.id}>{item.reference_code} · {new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.starts_at))} · {counselingDeliveryModeLabel(item.delivery_mode)} · {item.status.toLowerCase().replaceAll("_", " ")}</option>)}
        </select>
        {!candidates.isPending && !candidates.isError && items.length === 0 && !encounter.appointment ? <p className="mt-2 text-sm text-muted">No Appointment candidates are available for this Encounter.</p> : null}
        {!candidates.isPending && !candidates.isError ? <CounselingPagination page={candidates.data?.data.page ?? page} hasNext={candidates.data?.data.has_next ?? false} onPageChange={setPage} /> : null}
        <p className="mt-2 text-xs text-muted">Selected: {selectedLabel}</p>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2"><Label htmlFor="correction-started-at">Actual start</Label><Input id="correction-started-at" type="datetime-local" step="1" value={startedAt} disabled={update.isPending} aria-invalid={timeInvalid} aria-describedby={timeInvalid ? "correction-time-error" : undefined} onChange={(event) => { setStartedAt(event.target.value); setObservedNow(Date.now()); setError(null); }} /></div>
        <div className="grid gap-2"><Label htmlFor="correction-ended-at">Actual end</Label><Input id="correction-ended-at" type="datetime-local" step="1" value={endedAt} disabled={update.isPending} aria-invalid={timeInvalid} aria-describedby={timeInvalid ? "correction-time-error" : undefined} onChange={(event) => { setEndedAt(event.target.value); setObservedNow(Date.now()); setError(null); }} /></div>
      </div>
      {timeInvalid ? <p id="correction-time-error" className="mt-4 text-sm text-danger">{timeMessage ?? "Enter valid actual start and end times."}</p> : null}
      {error && !timeInvalid ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
      <div className="mt-5 flex flex-wrap gap-2"><Button type="submit" disabled={unchanged || update.isPending || timeInvalid || missingAppointment} aria-busy={update.isPending}>{update.isPending ? "Saving correction…" : "Save correction"}</Button><Button type="button" variant="secondary" disabled={update.isPending} onClick={onClose}>Cancel</Button></div>
    </form>
  );
}

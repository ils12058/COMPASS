"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorCode,
  counselingErrorMessage,
  CounselingPagination,
} from "@/features/counseling/counseling-shared";
import type {
  CounselingAppointmentCandidate,
  CounselingCreateRequest,
  CounselingEntryMode,
  CounselingStudentResponse,
  DeliveryMode,
} from "@/lib/api/generated/model";
import {
  getCounselingListAppointmentCandidatesQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingCreateEncounter,
  useCounselingGetEncounterCreationOptions,
  useCounselingListAppointmentCandidates,
  useCounselingListStudents,
} from "@/lib/api/generated/counseling/counseling";
import { CompassApiError } from "@/lib/api/errors";

type Source = "appointment" | "direct";

export type EncounterOriginPreset = {
  entryMode: CounselingEntryMode;
  studentId?: string;
  studentName: string;
  institutionalId?: string | null;
  appointmentId?: string;
  appointmentReference?: string;
  deliveryMode: DeliveryMode;
};

type RecordEncounterFormProps = {
  preset?: EncounterOriginPreset;
  onCancel?: () => void;
  onCreated?: (encounterId: string) => void;
  onUncertain?: () => void;
};

function statusLabel(value: string): string {
  return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isoFromLocalDateTime(value: string): string | null {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : date.toISOString();
}

export function RecordEncounterForm({ preset, onCancel, onCreated, onUncertain }: RecordEncounterFormProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [source, setSource] = useState<Source | null>(null);
  const [candidateSearch, setCandidateSearch] = useState("");
  const [studentSearch, setStudentSearch] = useState("");
  const [candidateQuery, setCandidateQuery] = useState("");
  const [studentQuery, setStudentQuery] = useState("");
  const [page, setPage] = useState(1);
  const [selectedAppointmentId, setSelectedAppointmentId] = useState("");
  const [selectedAppointmentRecord, setSelectedAppointmentRecord] = useState<CounselingAppointmentCandidate | null>(null);
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [selectedStudentRecord, setSelectedStudentRecord] = useState<CounselingStudentResponse | null>(null);
  const [entryMode, setEntryMode] = useState<CounselingEntryMode>("WALK_IN");
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode | "">("");
  const [startedAt, setStartedAt] = useState("");
  const [endedAt, setEndedAt] = useState("");
  const [observedNow, setObservedNow] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const create = useCounselingCreateEncounter({ mutation: { retry: false } });

  const appointmentCandidates = useCounselingListAppointmentCandidates(
    { ...(candidateQuery ? { search: candidateQuery } : {}), page, page_size: 20 },
    { query: { enabled: !preset && source === "appointment", retry: false } },
  );
  const creationOptions = useCounselingGetEncounterCreationOptions({
    query: { enabled: !preset && source === "direct", retry: false },
  });
  const students = useCounselingListStudents(
    { ...(studentQuery ? { search: studentQuery } : {}), page, page_size: 20 },
    { query: { enabled: !preset && source === "direct", retry: false } },
  );

  const appointments = appointmentCandidates.data?.data.items ?? [];
  const studentItems = students.data?.data.items ?? [];
  const options = creationOptions.data?.data;
  const selectedAppointment = appointments.find((item) => item.id === selectedAppointmentId) ??
    (selectedAppointmentRecord?.id === selectedAppointmentId ? selectedAppointmentRecord : undefined);
  const selectedStudent = studentItems.find((item) => item.id === selectedStudentId) ??
    (selectedStudentRecord?.id === selectedStudentId ? selectedStudentRecord : undefined);
  const selectedContextStudent = preset?.studentId ? preset : undefined;
  const selectedDeliveryMode = preset?.deliveryMode ?? (
    source === "appointment" && selectedAppointment
      ? selectedAppointment.delivery_mode
      : deliveryMode || (options?.delivery_modes.length === 1 ? options.delivery_modes[0] : "")
  );
  const selectedOrigin = preset ?? (
    source === "appointment" && selectedAppointment
      ? {
          entryMode: "APPOINTMENT" as const,
          appointmentId: selectedAppointment.id,
          appointmentReference: selectedAppointment.reference_code,
          studentName: selectedAppointment.student.display_name,
          institutionalId: selectedAppointment.student.institutional_id,
          deliveryMode: selectedAppointment.delivery_mode,
        }
      : source === "direct" && selectedStudent && selectedDeliveryMode
        ? {
            entryMode,
            studentId: selectedStudent.id,
            studentName: selectedStudent.display_name,
            institutionalId: selectedStudent.institutional_id,
            deliveryMode: selectedDeliveryMode,
          }
        : undefined
  );
  const hasSelectedRecord = Boolean(preset || (source === "appointment" ? selectedAppointment : selectedStudent));
  const endTimestamp = endedAt ? new Date(endedAt).getTime() : Number.NaN;
  const startTimestamp = startedAt ? new Date(startedAt).getTime() : Number.NaN;
  const timeError = startedAt && endedAt && (
    Number.isNaN(startTimestamp) ||
    Number.isNaN(endTimestamp) ||
    startTimestamp >= endTimestamp ||
    (observedNow !== null && endTimestamp > observedNow)
  );

  function changeSource(next: Source) {
    setSource(next);
    setError(null);
    setPage(1);
    setSelectedAppointmentId("");
    setSelectedAppointmentRecord(null);
    setSelectedStudentId("");
    setSelectedStudentRecord(null);
    setStartedAt("");
    setEndedAt("");
    setObservedNow(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrigin || create.isPending || uncertain) return;
    setError(null);
    if (!startedAt || !endedAt) {
      setError("Enter the actual start and end times of the completed interaction.");
      return;
    }
    if (timeError || endTimestamp > Date.now()) {
      setError("The actual start must be before the end, and the end cannot be in the future.");
      return;
    }
    const started = isoFromLocalDateTime(startedAt);
    const ended = isoFromLocalDateTime(endedAt);
    if (!started || !ended) {
      setError("Enter valid actual start and end times.");
      return;
    }

    const payload: CounselingCreateRequest = selectedOrigin.entryMode === "APPOINTMENT"
      ? {
          appointment_id: selectedOrigin.appointmentId,
          entry_mode: "APPOINTMENT",
          started_at: started,
          ended_at: ended,
        }
      : {
          student_id: selectedOrigin.studentId,
          entry_mode: selectedOrigin.entryMode,
          delivery_mode: selectedOrigin.deliveryMode,
          started_at: started,
          ended_at: ended,
        };

    try {
      const response = await create.mutateAsync({ data: payload });
      const encounterId = response.data.id;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
        ...(selectedOrigin.entryMode === "APPOINTMENT"
          ? [queryClient.invalidateQueries({ queryKey: getCounselingListAppointmentCandidatesQueryKey() })]
          : []),
      ]);
      if (onCreated) onCreated(encounterId);
      else router.push(`/portal/counseling/encounters/${encounterId}`);
    } catch (caught) {
      const isUncertain = !(caught instanceof CompassApiError) || caught.status >= 500;
      if (isUncertain) {
        setUncertain(true);
        onUncertain?.();
        setError(null);
      } else {
        setError(counselingErrorMessage(caught, "The Counseling Encounter could not be recorded. Review the values and try again."));
        if (counselingErrorCode(caught) === "counseling_appointment_already_used") {
          setSelectedAppointmentId("");
          setSelectedAppointmentRecord(null);
          void Promise.all([
            queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
            queryClient.invalidateQueries({ queryKey: getCounselingListAppointmentCandidatesQueryKey() }),
          ]);
        }
      }
    }
  }

  if (!preset && !source) {
    return (
      <section className="border-y border-border py-5" aria-labelledby="record-encounter-source-heading">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="record-encounter-source-heading" className="font-heading text-xl font-semibold text-ink">Record counseling encounter</h2>
            <p className="mt-1 text-sm text-muted">Choose how the completed interaction originated.</p>
          </div>
          {onCancel && !uncertain ? <Button variant="quiet" onClick={onCancel}>Close</Button> : null}
        </div>
        <div role="group" aria-label="Counseling interaction source" className="mt-5 flex flex-wrap gap-3">
          <Button variant="secondary" onClick={() => changeSource("appointment")}>From Counseling appointment</Button>
          <Button variant="secondary" onClick={() => changeSource("direct")}>Walk-in / called-in / referred</Button>
        </div>
      </section>
    );
  }

  return (
    <section className="border-y border-border py-5" aria-labelledby="record-encounter-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="record-encounter-heading" className="font-heading text-xl font-semibold text-ink">Record counseling encounter</h2>
          <p className="mt-1 text-sm text-muted">
            {preset ? "Record the completed interaction connected to this Counseling context." : source === "appointment" ? "Select an eligible Counseling Appointment, then enter when the interaction actually occurred." : "Select a Student and record the completed direct interaction."}
          </p>
        </div>
        {!preset && !uncertain ? <Button variant="quiet" disabled={create.isPending} onClick={() => source ? changeSource(source === "appointment" ? "direct" : "appointment") : onCancel?.()}>Change source</Button> : preset && onCancel && !uncertain ? <Button variant="quiet" disabled={create.isPending} onClick={onCancel}>Close</Button> : null}
      </div>

      {!preset && source === "appointment" ? (
        <div className="mt-5 space-y-4">
          <form className="grid gap-2 sm:max-w-xl" onSubmit={(event) => { event.preventDefault(); setCandidateQuery(candidateSearch.trim()); setPage(1); setSelectedAppointmentId(""); setSelectedAppointmentRecord(null); setError(null); }}>
            <Label htmlFor="counseling-appointment-search">Search Counseling Appointments</Label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input id="counseling-appointment-search" value={candidateSearch} onChange={(event) => setCandidateSearch(event.target.value)} placeholder="Appointment reference, Student name, or Institutional ID" />
              <Button type="submit" variant="secondary">Search</Button>
            </div>
          </form>
          {appointmentCandidates.isPending ? <div aria-busy="true" className="space-y-2"><span className="sr-only">Loading Counseling Appointment candidates…</span><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div> : appointmentCandidates.isError ? <p role="alert" className="text-sm text-danger">{counselingErrorMessage(appointmentCandidates.error, "Counseling Appointments could not be loaded.")}</p> : appointments.length === 0 ? <p className="border-y border-border py-4 text-sm text-muted">No eligible Counseling Appointments match this search.</p> : (
            <>
              <ul className="divide-y divide-border border-y border-border" aria-label="Counseling Appointment candidates">
                {appointments.map((candidate) => (
                  <li key={candidate.id}>
                    <button type="button" aria-pressed={selectedAppointmentId === candidate.id} onClick={() => { setSelectedAppointmentId(candidate.id); setSelectedAppointmentRecord(candidate); setStartedAt(""); setEndedAt(""); setError(null); }} className={`flex w-full flex-wrap items-start justify-between gap-3 px-3 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${selectedAppointmentId === candidate.id ? "bg-surface-muted" : "hover:bg-surface-muted/60"}`}>
                      <span>
                        <span className="block font-semibold text-ink">{candidate.reference_code} · {candidate.student.display_name}</span>
                        <span className="mt-1 block text-sm text-muted">{candidate.student.institutional_id ? `Institutional ID ${candidate.student.institutional_id} · ` : ""}{new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" }).format(new Date(candidate.starts_at))} – {new Intl.DateTimeFormat("en-PH", { timeStyle: "short" }).format(new Date(candidate.ends_at))}</span>
                      </span>
                      <span className="text-sm text-muted">{counselingDeliveryModeLabel(candidate.delivery_mode)} · {statusLabel(candidate.status)}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <CounselingPagination page={appointmentCandidates.data?.data.page ?? page} hasNext={appointmentCandidates.data?.data.has_next ?? false} onPageChange={setPage} />
            </>
          )}
        </div>
      ) : null}

      {!preset && source === "direct" ? (
        <div className="mt-5 space-y-5">
          {creationOptions.isPending ? <div aria-busy="true"><Skeleton className="h-12 w-full" /></div> : creationOptions.isError ? <p role="alert" className="text-sm text-danger">{counselingErrorMessage(creationOptions.error, "Counseling recording options could not be loaded.")}</p> : options ? (
            <div><p className="text-sm text-muted">Service: <span className="font-medium text-ink">{options.service.name} · {options.service.code}</span></p>{options.delivery_modes.length === 0 ? <p role="status" className="mt-2 text-sm text-warning">No delivery mode is currently configured for this Counseling Service.</p> : null}</div>
          ) : null}
          <form className="grid gap-2 sm:max-w-xl" onSubmit={(event) => { event.preventDefault(); setStudentQuery(studentSearch.trim()); setPage(1); setSelectedStudentId(""); setSelectedStudentRecord(null); setStartedAt(""); setEndedAt(""); setError(null); }}>
            <Label htmlFor="counseling-student-search">Search for a Student</Label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input id="counseling-student-search" value={studentSearch} onChange={(event) => setStudentSearch(event.target.value)} placeholder="Student name or Institutional ID" />
              <Button type="submit" variant="secondary">Search</Button>
            </div>
          </form>
          {students.isPending ? <div aria-busy="true" className="space-y-2"><span className="sr-only">Loading Student candidates…</span><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div> : students.isError ? <p role="alert" className="text-sm text-danger">{counselingErrorMessage(students.error, "Student candidates could not be loaded.")}</p> : studentItems.length === 0 ? <p className="border-y border-border py-4 text-sm text-muted">No Students match this search.</p> : (
            <>
              <ul className="divide-y divide-border border-y border-border" aria-label="Student candidates">
                {studentItems.map((student) => (
                  <li key={student.id}>
                    <button type="button" aria-pressed={selectedStudentId === student.id} onClick={() => { if (selectedStudentId !== student.id) { setStartedAt(""); setEndedAt(""); } setSelectedStudentId(student.id); setSelectedStudentRecord(student); setError(null); }} className={`w-full px-3 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${selectedStudentId === student.id ? "bg-surface-muted" : "hover:bg-surface-muted/60"}`}>
                      <span className="block font-semibold text-ink">{student.display_name}</span>
                      <span className="mt-1 block text-sm text-muted">Institutional ID: {student.institutional_id ?? "Not provided"}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <CounselingPagination page={students.data?.data.page ?? page} hasNext={students.data?.data.has_next ?? false} onPageChange={setPage} />
            </>
          )}
          {selectedStudent && options ? (
            <div className="grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="counseling-entry-mode">Interaction origin</Label>
                <select id="counseling-entry-mode" value={entryMode} onChange={(event) => setEntryMode(event.target.value as CounselingEntryMode)} disabled={create.isPending} className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                  <option value="WALK_IN">Walk-in</option><option value="CALLED_IN">Called-in</option><option value="REFERRED">Referred</option>
                </select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="counseling-delivery-mode">Delivery mode</Label>
                <select id="counseling-delivery-mode" value={selectedDeliveryMode} onChange={(event) => setDeliveryMode(event.target.value as DeliveryMode)} disabled={create.isPending || options.delivery_modes.length === 1} className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                  {options.delivery_modes.length === 0 ? <option value="">No delivery mode configured</option> : null}
                  {options.delivery_modes.map((mode) => <option key={mode} value={mode}>{counselingDeliveryModeLabel(mode)}</option>)}
                </select>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {hasSelectedRecord && selectedOrigin ? (
        <form onSubmit={submit} className="mt-6 border-t border-border pt-5">
          <div className="grid gap-x-8 gap-y-4 border-b border-border pb-5 sm:grid-cols-2">
            <div><p className="text-xs font-semibold text-muted">Student</p><p className="mt-1 text-sm font-semibold text-ink">{selectedOrigin.studentName}</p><p className="mt-1 text-xs text-muted">Institutional ID: {selectedOrigin.institutionalId ?? "Not provided"}</p></div>
            <div><p className="text-xs font-semibold text-muted">Origin and delivery</p><p className="mt-1 text-sm text-ink">{counselingEntryModeLabel(selectedOrigin.entryMode)} · {counselingDeliveryModeLabel(selectedOrigin.deliveryMode)}</p>{selectedOrigin.appointmentReference ? <p className="mt-1 text-xs text-muted">Appointment {selectedOrigin.appointmentReference}</p> : null}</div>
          </div>
          {selectedOrigin.entryMode === "APPOINTMENT" ? <p className="mt-3 text-xs text-muted">Student, Counselor, Counseling Service, and delivery mode are fixed by this Appointment and the signed-in Counselor.</p> : <p className="mt-3 text-xs text-muted">You are recorded as the Counselor, and the Counseling Service is assigned automatically.</p>}
          <p className="mt-4 text-sm text-muted">Enter the actual times of the completed interaction. Appointment schedule boundaries and default duration do not constrain these times.</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2"><Label htmlFor="counseling-started-at">Actual start</Label><Input id="counseling-started-at" type="datetime-local" required value={startedAt} disabled={create.isPending || uncertain} aria-invalid={Boolean(error && !startedAt) || Boolean(startedAt && endedAt && timeError)} aria-describedby={error && (!startedAt || !endedAt) ? "counseling-time-required" : startedAt && endedAt && timeError ? "counseling-time-error" : undefined} onChange={(event) => { setStartedAt(event.target.value); setObservedNow(Date.now()); setError(null); }} /></div>
            <div className="grid gap-2"><Label htmlFor="counseling-ended-at">Actual end</Label><Input id="counseling-ended-at" type="datetime-local" required value={endedAt} disabled={create.isPending || uncertain} aria-invalid={Boolean(error && (!endedAt || timeError))} aria-describedby={error && (!startedAt || !endedAt) ? "counseling-time-required" : startedAt && endedAt && timeError ? "counseling-time-error" : undefined} onChange={(event) => { setEndedAt(event.target.value); setObservedNow(Date.now()); setError(null); }} /></div>
          </div>
          {error && (!startedAt || !endedAt) ? <p id="counseling-time-required" className="mt-2 text-sm text-danger">{error}</p> : null}
          {startedAt && endedAt && timeError ? <p id="counseling-time-error" className="mt-2 text-sm text-danger">The actual start must be before the end, and the end cannot be in the future.</p> : null}
          {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
          {uncertain ? (
            <div role="alert" className="mt-4 border-y border-warning/40 py-4">
              <p className="text-sm leading-6 text-ink">The result of this recording request could not be confirmed. Refresh My Counseling Encounters before recording the interaction again to avoid a duplicate record.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" variant="secondary" onClick={() => void Promise.all([
                  queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
                  ...(selectedOrigin.entryMode === "APPOINTMENT" ? [queryClient.invalidateQueries({ queryKey: getCounselingListAppointmentCandidatesQueryKey() })] : []),
                ])}>Refresh My Counseling Encounters</Button>
                <Link href="/portal/counseling#encounters" className="inline-flex min-h-10 items-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">View My Counseling Encounters</Link>
              </div>
            </div>
          ) : null}
          {!uncertain ? (
            <div className="mt-5 flex flex-wrap gap-2">
              <Button type="submit" disabled={create.isPending || !selectedDeliveryMode || Boolean(timeError)} aria-busy={create.isPending}>{create.isPending ? "Recording…" : "Record counseling encounter"}</Button>
              {!preset && source === "appointment" && selectedAppointment?.status === "SCHEDULED" ? <p className="basis-full text-xs text-muted">Recording this Encounter will not complete the Appointment.</p> : null}
              {!preset && onCancel ? <Button type="button" variant="secondary" disabled={create.isPending} onClick={onCancel}>Cancel</Button> : null}
            </div>
          ) : null}
        </form>
      ) : null}

      {preset && selectedContextStudent ? (
        <p className="sr-only">Recording is bound to {selectedContextStudent.studentName} and the current Counseling context.</p>
      ) : null}
    </section>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { formatAppointmentDateTime } from "@/features/appointments/appointments-shared";
import { ActualTimeFields, actualTimeInputId, actualTimeIssues, firstActualTimeIssue, type ActualTimeField } from "@/features/counseling/actual-time-fields";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorCode,
  counselingErrorMessage,
  formatCounselingDateTime,
  unconfirmedEncounterMessage,
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
import { institutionalDateTimeInputToISO } from "@/lib/institutional-time";

type Source = "appointment" | "direct";

export type EncounterOriginPreset = {
  entryMode: CounselingEntryMode;
  studentId?: string;
  studentName: string;
  institutionalId?: string | null;
  appointmentId?: string;
  appointmentReference?: string;
  // Recording from this Routine Interview's workspace links the Encounter to it.
  routineInterviewId?: string;
  deliveryMode: DeliveryMode;
  // The Appointment's scheduled times, shown for reference only. They never fill the actual times
  // and are not sent.
  scheduledStartsAt?: string;
  scheduledEndsAt?: string;
};

export type EncounterTimes = { startedAt: string; endedAt: string };

type RecordEncounterFormProps = {
  initialTimes?: EncounterTimes;
  onTimesChange?: (times: EncounterTimes) => void;
  onBusyChange?: (busy: boolean) => void;
  preset?: EncounterOriginPreset;
  // False inside a dialog, which supplies the title and the provenance note itself.
  framed?: boolean;
  onCancel?: () => void;
  onCreated?: (encounterId: string) => void | Promise<void>;
  onUncertain?: () => void;
  // The preset's Appointment or Routine Interview already has its Encounter; the caller reloads
  // what it shows.
  onAlreadyRecorded?: () => void | Promise<void>;
};

// Who and what an Encounter recorded from this origin is fixed to.
export function encounterProvenanceNote(entryMode: CounselingEntryMode): string {
  return entryMode === "APPOINTMENT"
    ? "The Appointment sets the student, Service, and delivery mode. You are recorded as the counselor."
    : "You are recorded as the counselor for this encounter.";
}

export function encounterCreatePayload(
  origin: EncounterOriginPreset,
  startedAt: string,
  endedAt: string,
): CounselingCreateRequest {
  const routine = origin.routineInterviewId ? { routine_interview_id: origin.routineInterviewId } : {};
  return origin.entryMode === "APPOINTMENT"
    ? {
        appointment_id: origin.appointmentId,
        entry_mode: "APPOINTMENT",
        ...routine,
        started_at: startedAt,
        ended_at: endedAt,
      }
    : {
        student_id: origin.studentId,
        entry_mode: origin.entryMode,
        delivery_mode: origin.deliveryMode,
        ...routine,
        started_at: startedAt,
        ended_at: endedAt,
      };
}

function statusLabel(value: string): string {
  return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function RecordEncounterForm({ preset, framed = true, onCancel, onCreated, onUncertain, onAlreadyRecorded, initialTimes, onTimesChange, onBusyChange }: RecordEncounterFormProps) {
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
  const [startedAt, setStartedAt] = useState(initialTimes?.startedAt ?? "");
  const [endedAt, setEndedAt] = useState(initialTimes?.endedAt ?? "");
  const [observedNow, setObservedNow] = useState<number | null>(null);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const create = useCounselingCreateEncounter({ mutation: { retry: false } });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { onTimesChange?.({ startedAt, endedAt }); }, [startedAt, endedAt, onTimesChange]);
  useEffect(() => { onBusyChange?.(submitting || uncertain); }, [submitting, uncertain, onBusyChange]);

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
  const selectedDeliveryMode = preset?.deliveryMode ?? (
    source === "appointment" && selectedAppointment
      ? selectedAppointment.delivery_mode
      : deliveryMode || (options?.delivery_modes.length === 1 ? options.delivery_modes[0] : "")
  );
  const selectedOrigin: EncounterOriginPreset | undefined = preset ?? (
    source === "appointment" && selectedAppointment
      ? {
          entryMode: "APPOINTMENT" as const,
          appointmentId: selectedAppointment.id,
          appointmentReference: selectedAppointment.reference_code,
          studentName: selectedAppointment.student.display_name,
          institutionalId: selectedAppointment.student.institutional_id,
          deliveryMode: selectedAppointment.delivery_mode,
          scheduledStartsAt: selectedAppointment.starts_at,
          scheduledEndsAt: selectedAppointment.ends_at,
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
  const timeIssues = actualTimeIssues(startedAt, endedAt, observedNow);

  // A different record starts with blank actual times and no reported issues.
  function clearTimes() {
    setStartedAt("");
    setEndedAt("");
    setObservedNow(null);
    setAttempted(false);
  }

  function changeSource(next: Source) {
    setSource(next);
    setError(null);
    setPage(1);
    setSelectedAppointmentId("");
    setSelectedAppointmentRecord(null);
    setSelectedStudentId("");
    setSelectedStudentRecord(null);
    clearTimes();
  }

  function changeTime(field: ActualTimeField, value: string) {
    if (field === "start") setStartedAt(value);
    else setEndedAt(value);
    setObservedNow(Date.now());
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrigin || submitting || uncertain) return;
    setError(null);
    const now = Date.now();
    const invalid = firstActualTimeIssue(actualTimeIssues(startedAt, endedAt, now));
    if (invalid) {
      setAttempted(true);
      setObservedNow(now);
      document.getElementById(actualTimeInputId("counseling", invalid))?.focus();
      return;
    }
    const started = institutionalDateTimeInputToISO(startedAt);
    const ended = institutionalDateTimeInputToISO(endedAt);
    if (!started || !ended) return;

    const payload = encounterCreatePayload(selectedOrigin, started, ended);

    setSubmitting(true);
    // Lock the containing dialog in the submission event, before Escape can dismiss it.
    onBusyChange?.(true);
    try {
      const response = await create.mutateAsync({ data: payload });
      const encounterId = response.data.id;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
        ...(selectedOrigin.entryMode === "APPOINTMENT"
          ? [queryClient.invalidateQueries({ queryKey: getCounselingListAppointmentCandidatesQueryKey() })]
          : []),
      ]);
      if (onCreated) await onCreated(encounterId);
      else router.push(`/portal/counseling/encounters/${encounterId}`);
    } catch (caught) {
      const isUncertain = !(caught instanceof CompassApiError) || caught.status >= 500;
      if (isUncertain) {
        setUncertain(true);
        onUncertain?.();
        setError(null);
      } else {
        const code = counselingErrorCode(caught);
        // A preset's own record already has its Encounter: the caller reloads it and says so.
        if (preset && onAlreadyRecorded && (code === "counseling_routine_interview_already_linked" || code === "counseling_appointment_already_used")) {
          await onAlreadyRecorded();
          return;
        }
        setError(counselingErrorMessage(caught, "The encounter couldn’t be recorded. Review the details and try again."));
        if (code === "counseling_appointment_already_used") {
          setSelectedAppointmentId("");
          setSelectedAppointmentRecord(null);
          void Promise.all([
            queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
            queryClient.invalidateQueries({ queryKey: getCounselingListAppointmentCandidatesQueryKey() }),
          ]);
        }
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!preset && !source) {
    return (
      <Panel aria-labelledby="record-encounter-source-heading">
        <PanelHeader
          title="Record counseling encounter"
          titleId="record-encounter-source-heading"
          actions={onCancel && !uncertain ? <Button variant="quiet" onClick={onCancel}>Close</Button> : undefined}
        />
        <PanelBody>
          <div role="group" aria-label="Counseling interaction source" className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => changeSource("appointment")}>From Counseling appointment</Button>
            <Button variant="secondary" onClick={() => changeSource("direct")}>Walk-in / called-in / referred</Button>
          </div>
        </PanelBody>
      </Panel>
    );
  }

  const scheduled = selectedOrigin?.scheduledStartsAt && selectedOrigin.scheduledEndsAt
    ? formatAppointmentDateTime(selectedOrigin.scheduledStartsAt, selectedOrigin.scheduledEndsAt)
    : null;
  const recordForm = hasSelectedRecord && selectedOrigin ? (
    // Validation is COMPASS's own, per field; the backend still checks every save.
    <form noValidate onSubmit={submit} className={framed ? "border-t border-brand-line px-4 py-5 sm:px-5" : undefined}>
      <dl className="grid gap-x-8 gap-y-3 rounded-sm bg-surface-subtle px-4 py-3.5 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="text-xs font-semibold text-muted">Student</dt>
          <dd className="mt-1 break-words text-sm font-semibold text-ink">{selectedOrigin.studentName}</dd>
          <dd className="mt-1 break-words text-xs text-muted">Institutional ID: {selectedOrigin.institutionalId || "Not provided"}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs font-semibold text-muted">Origin and delivery</dt>
          <dd className="mt-1 text-sm text-ink">{counselingEntryModeLabel(selectedOrigin.entryMode)} · {counselingDeliveryModeLabel(selectedOrigin.deliveryMode)}</dd>
          {selectedOrigin.appointmentReference ? <dd className="mt-1 break-words text-xs text-muted">Appointment {selectedOrigin.appointmentReference}</dd> : null}
        </div>
        {scheduled ? (
          <div className="min-w-0 sm:col-span-2">
            <dt className="text-xs font-semibold text-muted">Scheduled appointment</dt>
            <dd className="mt-1 text-sm text-ink">{scheduled}</dd>
          </div>
        ) : null}
      </dl>
      {framed ? <p className="mt-3 text-xs text-muted">{encounterProvenanceNote(selectedOrigin.entryMode)}</p> : null}
      <div className="mt-5">
        <ActualTimeFields
          idPrefix="counseling"
          startedAt={startedAt}
          endedAt={endedAt}
          onChange={changeTime}
          issues={timeIssues}
          attempted={attempted}
          disabled={submitting || uncertain}
          scheduled={selectedOrigin.entryMode === "APPOINTMENT"}
        />
      </div>
      {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
      {uncertain ? (
        // Escape cannot hide this result inside a dialog; its Close is a deliberate choice (ADR-091).
        <Notice
          role="alert"
          tone="warning"
          className="mt-4"
          action={(
            <>
              {framed ? (
                <Button variant="secondary" onClick={() => void Promise.all([
                  queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
                  ...(selectedOrigin.entryMode === "APPOINTMENT" ? [queryClient.invalidateQueries({ queryKey: getCounselingListAppointmentCandidatesQueryKey() })] : []),
                ])}>Refresh encounters</Button>
              ) : null}
              <Link href="/portal/counseling#encounters" className={buttonVariants({ variant: "secondary" })}>View encounters</Link>
              {!framed && onCancel ? <Button variant="secondary" onClick={onCancel}>Close</Button> : null}
            </>
          )}
        >
          <p className="text-ink">{unconfirmedEncounterMessage} Check your encounters before trying again to avoid a duplicate.</p>
        </Notice>
      ) : (
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <Button type="submit" disabled={submitting || !selectedDeliveryMode} aria-busy={submitting}>{submitting ? "Recording encounter…" : "Record encounter"}</Button>
          {onCancel ? <Button variant="secondary" disabled={submitting} onClick={onCancel}>Cancel</Button> : null}
          {!preset && source === "appointment" && selectedAppointment?.status === "SCHEDULED" ? <p className="basis-full text-xs text-muted">Recording this encounter does not complete the Appointment.</p> : null}
        </div>
      )}
    </form>
  ) : null;

  if (!framed) return recordForm;

  return (
    <Panel aria-labelledby="record-encounter-heading">
      <PanelHeader
        title="Record counseling encounter"
        titleId="record-encounter-heading"
        description={preset ? undefined : source === "appointment" ? "Choose an Appointment." : "Choose a Student."}
        actions={!preset && !uncertain ? <Button variant="quiet" disabled={submitting} onClick={() => changeSource(source === "appointment" ? "direct" : "appointment")}>Change source</Button> : undefined}
      />

      {!preset && source === "appointment" ? (
        <div className="space-y-4 px-4 py-4 sm:px-5">
          <form className="grid gap-2 sm:max-w-xl" onSubmit={(event) => { event.preventDefault(); setCandidateQuery(candidateSearch.trim()); setPage(1); setSelectedAppointmentId(""); setSelectedAppointmentRecord(null); setError(null); }}>
            <Label htmlFor="counseling-appointment-search">Search Counseling Appointments</Label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input id="counseling-appointment-search" value={candidateSearch} onChange={(event) => setCandidateSearch(event.target.value)} placeholder="Appointment reference, Student name, or Institutional ID" />
              <Button type="submit" variant="secondary">Search</Button>
            </div>
          </form>
          {appointmentCandidates.isPending ? <div aria-busy="true" className="space-y-2"><span className="sr-only">Loading counseling appointments…</span><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div> : appointmentCandidates.isError ? <p role="alert" className="text-sm text-danger">{counselingErrorMessage(appointmentCandidates.error, "Counseling Appointments could not be loaded.")}</p> : appointments.length === 0 ? <p className="text-sm text-muted">No eligible counseling appointments match this search.</p> : (
            <>
              <ul className="divide-y divide-border rounded-sm border border-border" aria-label="Counseling Appointment candidates">
                {appointments.map((candidate) => (
                  <li key={candidate.id}>
                    <button type="button" aria-pressed={selectedAppointmentId === candidate.id} onClick={() => { setSelectedAppointmentId(candidate.id); setSelectedAppointmentRecord(candidate); clearTimes(); setError(null); }} className={`flex w-full flex-wrap items-start justify-between gap-3 px-4 py-3.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus ${selectedAppointmentId === candidate.id ? "bg-brand-wash" : "hover:bg-surface-subtle"}`}>
                      <span>
                        <span className="flex items-center gap-2 font-semibold text-ink"><PersonAvatar displayName={candidate.student.display_name} photoUrl={candidate.student.profile_photo_url} photoUpdatedAt={candidate.student.profile_photo_updated_at} size="compact" />{candidate.reference_code} · {candidate.student.display_name}</span>
                        <span className="mt-1 block text-sm text-muted">{candidate.student.institutional_id ? `Institutional ID ${candidate.student.institutional_id} · ` : ""}{formatCounselingDateTime(candidate.starts_at)} – {formatCounselingDateTime(candidate.ends_at)}</span>
                      </span>
                      <span className="text-sm text-muted">{counselingDeliveryModeLabel(candidate.delivery_mode)} · {statusLabel(candidate.status)}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <CanonicalPagination className="border-t-0 pb-0" label="Appointment candidate pages" page={appointmentCandidates.data?.data.page ?? page} hasNext={appointmentCandidates.data?.data.has_next ?? false} onPageChange={setPage} />
            </>
          )}
        </div>
      ) : null}

      {!preset && source === "direct" ? (
        <div className="space-y-5 px-4 py-4 sm:px-5">
          {creationOptions.isPending ? <div aria-busy="true"><Skeleton className="h-12 w-full" /></div> : creationOptions.isError ? <p role="alert" className="text-sm text-danger">{counselingErrorMessage(creationOptions.error, "Counseling recording options could not be loaded.")}</p> : options ? (
            <div><p className="text-sm text-muted">Service: <span className="font-medium text-ink">{options.service.name}</span></p>{options.delivery_modes.length === 0 ? <p role="status" className="mt-2 text-sm text-warning">No delivery mode is available for this counseling service.</p> : null}</div>
          ) : null}
          <form className="grid gap-2 sm:max-w-xl" onSubmit={(event) => { event.preventDefault(); setStudentQuery(studentSearch.trim()); setPage(1); setSelectedStudentId(""); setSelectedStudentRecord(null); clearTimes(); setError(null); }}>
            <Label htmlFor="counseling-student-search">Search for a Student</Label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input id="counseling-student-search" value={studentSearch} onChange={(event) => setStudentSearch(event.target.value)} placeholder="Student name or Institutional ID" />
              <Button type="submit" variant="secondary">Search</Button>
            </div>
          </form>
          {students.isPending ? <div aria-busy="true" className="space-y-2"><span className="sr-only">Loading students…</span><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div> : students.isError ? <p role="alert" className="text-sm text-danger">{counselingErrorMessage(students.error, "Student candidates could not be loaded.")}</p> : studentItems.length === 0 ? <p className="text-sm text-muted">No students match this search.</p> : (
            <>
              <ul className="divide-y divide-border rounded-sm border border-border" aria-label="Student candidates">
                {studentItems.map((student) => (
                  <li key={student.id}>
                    <button type="button" aria-pressed={selectedStudentId === student.id} onClick={() => { if (selectedStudentId !== student.id) clearTimes(); setSelectedStudentId(student.id); setSelectedStudentRecord(student); setError(null); }} className={`w-full px-4 py-3.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus ${selectedStudentId === student.id ? "bg-brand-wash" : "hover:bg-surface-subtle"}`}>
                      <span className="flex items-center gap-2 font-semibold text-ink"><PersonAvatar displayName={student.display_name} photoUrl={student.profile_photo_url} photoUpdatedAt={student.profile_photo_updated_at} size="compact" />{student.display_name}</span>
                      <span className="mt-1 block text-sm text-muted">Institutional ID: {student.institutional_id ?? "Not provided"}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <CanonicalPagination className="border-t-0 pb-0" label="Student pages" page={students.data?.data.page ?? page} hasNext={students.data?.data.has_next ?? false} onPageChange={setPage} />
            </>
          )}
          {selectedStudent && options ? (
            <div className="grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="counseling-entry-mode">Interaction origin</Label>
                <Select id="counseling-entry-mode" value={entryMode} onChange={(event) => setEntryMode(event.target.value as CounselingEntryMode)} disabled={submitting}>
                  <option value="WALK_IN">Walk-in</option><option value="CALLED_IN">Called-in</option><option value="REFERRED">Referred</option>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="counseling-delivery-mode">Delivery mode</Label>
                <Select id="counseling-delivery-mode" value={selectedDeliveryMode} onChange={(event) => setDeliveryMode(event.target.value as DeliveryMode)} disabled={submitting || options.delivery_modes.length === 1}>
                  {options.delivery_modes.length === 0 ? <option value="">No delivery mode available</option> : null}
                  {options.delivery_modes.map((mode) => <option key={mode} value={mode}>{counselingDeliveryModeLabel(mode)}</option>)}
                </Select>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {recordForm}
    </Panel>
  );
}

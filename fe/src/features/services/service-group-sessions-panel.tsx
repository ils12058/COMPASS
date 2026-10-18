"use client";

import { useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import {
  Calendar,
  Plus,
  Users,
  CheckCircle,
  XCircle,
  Download,
  Ban,
  UserCheck,
  MapPin,
  Video,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/ui/notice";
import { useServicesGet, useServicesList } from "@/lib/api/generated/services/services";
import { FloatingListTools, ListToolField } from "@/components/ui/floating-list-tools";
import { FilterField } from "@/components/ui/filter-toolbar";
import { groupSessionsError } from "@/features/group-sessions/group-sessions-shared";
import { Select } from "@/components/ui/select";
import { PanelSection } from "@/components/ui/panel";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  formatInstitutionalDateTime,
  institutionalDateTimeInputToISO,
  isoToInstitutionalDateTimeInput,
} from "@/lib/institutional-time";
import {
  useGroupSessionsListStaff,
  useGroupSessionsDiscover,
  useGroupSessionsGetMetrics,
  useGroupSessionsListRegistrations,
  useGroupSessionsCreate,
  useGroupSessionsPublish,
  useGroupSessionsCancel,
  useGroupSessionsComplete,
  useGroupSessionsWithdraw,
  useGroupSessionsRegister,
  useGroupSessionsCancelRegistration,
  useGroupSessionsRecordAttendance,
  useGroupSessionsUpdate,
  useGroupSessionsListFacilitatorCandidates,
  getGroupSessionsListStaffQueryKey,
  getGroupSessionsDiscoverQueryKey,
  getGroupSessionsGetMetricsQueryKey,
  getGroupSessionsListRegistrationsQueryKey,
  getGroupSessionsGetMyRegistrationsQueryKey,
} from "@/lib/api/generated/group-sessions/group-sessions";
import {
  DeliveryMode,
  type ServiceResponse,
  type GroupSessionResponse,
  type StudentGroupSessionResponse,
} from "@/lib/api/generated/model";

type ExternalFacilitatorDraft = { key: string; name: string };

function dateTimeInput(value: string): string {
  return isoToInstitutionalDateTimeInput(value);
}

// --- STAFF PANEL ---

export function ServiceGroupSessionsStaffPanel({ service, attendanceOnly = false }: { service?: ServiceResponse; attendanceOnly?: boolean }) {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const continuation = useStepUpContinuation();
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedService, setSelectedService] = useState<ServiceResponse | null>(null);
  const formService = service ?? selectedService;
  const [statusFilter, setStatusFilter] = useState("");
  const [serviceFilter, setServiceFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const scopeParams = service ? { service_id: service.id } : undefined;
  const listParams = statusFilter ? { ...scopeParams, status: statusFilter } : scopeParams;
  const [editingSession, setEditingSession] = useState<GroupSessionResponse | null>(null);
  const editingService = useServicesGet(editingSession?.service_id ?? "", { query: { retry: false, enabled: !service && Boolean(editingSession) && createOpen && user.capabilities.includes("services.catalog.view") } });
  const deliveryModes = (editingSession ? service?.delivery_modes ?? editingService.data?.data.delivery_modes : formService?.delivery_modes) ?? [editingSession?.delivery_mode ?? DeliveryMode.IN_PERSON];
  const [scheduleReviewOpen, setScheduleReviewOpen] = useState(false);
  const [cancelModalSession, setCancelModalSession] = useState<GroupSessionResponse | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [withdrawSession, setWithdrawSession] = useState<GroupSessionResponse | null>(null);
  const [rosterSession, setRosterSession] = useState<GroupSessionResponse | null>(null);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Create Form State
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>(
    formService?.delivery_modes[0] ?? DeliveryMode.IN_PERSON
  );
  const [venueOrUrl, setVenueOrUrl] = useState("");
  const [startDateTime, setStartDateTime] = useState("");
  const [endDateTime, setEndDateTime] = useState("");
  const [capacity, setCapacity] = useState(20);
  const [regOpensAt, setRegOpensAt] = useState("");
  const [regClosesAt, setRegClosesAt] = useState("");
  const [facilitatorSearch, setFacilitatorSearch] = useState("");
  const [internalFacilitatorIds, setInternalFacilitatorIds] = useState<string[]>(
    user.role === "COUNSELOR" ? [user.id] : [],
  );
  const [externalFacilitators, setExternalFacilitators] = useState<ExternalFacilitatorDraft[]>([]);
  const [externalNameDraft, setExternalNameDraft] = useState("");
  const [leadFacilitatorKey, setLeadFacilitatorKey] = useState(
    user.role === "COUNSELOR" ? `internal:${user.id}` : "",
  );
  const [facilitatorsTouched, setFacilitatorsTouched] = useState(false);

  const sessionsQuery = useGroupSessionsListStaff(
    listParams,
    { query: { retry: false } }
  );
  const metricsQuery = useGroupSessionsGetMetrics(
    scopeParams,
    { query: { retry: false, enabled: !attendanceOnly } }
  );
  const facilitatorCandidatesQuery = useGroupSessionsListFacilitatorCandidates(
    undefined,
    { query: { retry: false, enabled: createOpen } },
  );

  const createMutation = useGroupSessionsCreate();
  const updateMutation = useGroupSessionsUpdate();
  const publishMutation = useGroupSessionsPublish();
  const cancelMutation = useGroupSessionsCancel();
  const completeMutation = useGroupSessionsComplete();
  const withdrawMutation = useGroupSessionsWithdraw();

  const allSessions = sessionsQuery.data?.data ?? [];
  const serviceChoices = Array.from(new Map(allSessions.map((item) => [item.service_id, item.service_name])));
  const sessions = allSessions.filter((item) =>
    (!attendanceOnly || item.can_access_participants) &&
    (!serviceFilter || item.service_id === serviceFilter) &&
    (!fromDate || isoToInstitutionalDateTimeInput(item.starts_at).slice(0, 10) >= fromDate) &&
    (!toDate || isoToInstitutionalDateTimeInput(item.starts_at).slice(0, 10) <= toDate)
  );
  const metrics = metricsQuery.data?.data;
  const facilitatorCandidates = facilitatorCandidatesQuery.data?.data ?? [];
  const visibleFacilitatorCandidates = facilitatorCandidates.filter((candidate) =>
    candidate.display_name.toLocaleLowerCase().includes(facilitatorSearch.trim().toLocaleLowerCase()),
  );

  const invalidateAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getGroupSessionsListStaffQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getGroupSessionsGetMetricsQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getGroupSessionsDiscoverQueryKey(),
      }),
    ]);
  };

  const runStaffAction = async <T,>(operation: () => Promise<T>, fallback: string) =>
    continuation.run(operation, {
      onFailure: (caught) => {
        setErrorMessage(groupSessionsError(caught, fallback));
      },
    });

  const resetForm = () => {
    setEditingSession(null);
    setSelectedService(null);
    setTitle("");
    setDescription("");
    setDeliveryMode(formService?.delivery_modes[0] ?? DeliveryMode.IN_PERSON);
    setVenueOrUrl("");
    setStartDateTime("");
    setEndDateTime("");
    setCapacity(20);
    setRegOpensAt("");
    setRegClosesAt("");
    setInternalFacilitatorIds(user.role === "COUNSELOR" ? [user.id] : []);
    setExternalFacilitators([]);
    setExternalNameDraft("");
    setLeadFacilitatorKey(user.role === "COUNSELOR" ? `internal:${user.id}` : "");
    setFacilitatorsTouched(false);
    setFacilitatorSearch("");
    setErrorMessage(null);
  };

  const openCreate = () => {
    resetForm();
    setCreateOpen(true);
  };

  const openEdit = (session: GroupSessionResponse) => {
    setEditingSession(session);
    setSelectedService(null);
    setTitle(session.title);
    setDescription(session.description);
    setDeliveryMode(session.delivery_mode as DeliveryMode);
    setVenueOrUrl(session.venue_or_meeting_url);
    setStartDateTime(dateTimeInput(session.starts_at));
    setEndDateTime(dateTimeInput(session.ends_at));
    setCapacity(session.capacity);
    setRegOpensAt(session.reg_opens_at ? dateTimeInput(session.reg_opens_at) : "");
    setRegClosesAt(session.reg_closes_at ? dateTimeInput(session.reg_closes_at) : "");
    const activeFacilitators = session.facilitators.filter((facilitator) => facilitator.is_current);
    const internalIds = activeFacilitators.flatMap((facilitator) =>
      facilitator.kind === "INTERNAL" && facilitator.internal_user_id
        ? [facilitator.internal_user_id]
        : [],
    );
    const guests = activeFacilitators.flatMap((facilitator) =>
      facilitator.kind === "EXTERNAL"
        ? [{ key: facilitator.id, name: facilitator.external_display_name }]
        : [],
    );
    setInternalFacilitatorIds(internalIds);
    setExternalFacilitators(guests);
    const lead = activeFacilitators.find((facilitator) => facilitator.is_lead);
    setLeadFacilitatorKey(
      lead?.kind === "INTERNAL" && lead.internal_user_id
        ? `internal:${lead.internal_user_id}`
        : lead?.kind === "EXTERNAL"
          ? `external:${lead.id}`
          : "",
    );
    setFacilitatorsTouched(false);
    setFacilitatorSearch("");
    setErrorMessage(null);
    setCreateOpen(true);
  };

  const scheduleWillChange = () => {
    if (editingSession?.status !== "PUBLISHED") return false;
    const nextStartsAt = institutionalDateTimeInputToISO(startDateTime);
    const nextEndsAt = institutionalDateTimeInputToISO(endDateTime);
    if (!nextStartsAt || !nextEndsAt) return false;
    return (
      new Date(nextStartsAt).getTime() !== new Date(editingSession.starts_at).getTime() ||
      new Date(nextEndsAt).getTime() !== new Date(editingSession.ends_at).getTime() ||
      deliveryMode !== editingSession.delivery_mode ||
      venueOrUrl.trim() !== editingSession.venue_or_meeting_url
    );
  };

  const handleSaveForm = async (e?: React.FormEvent, scheduleReviewed = false) => {
    e?.preventDefault();
    if (scheduleReviewed) setScheduleReviewOpen(false);
    setErrorMessage(null);
    setSuccessMessage(null);

    if (!title.trim()) {
      setErrorMessage("Please enter a session title.");
      return;
    }
    if (!startDateTime || !endDateTime) {
      setErrorMessage("Please specify both start and end dates/times.");
      return;
    }
    const startsAtIso = institutionalDateTimeInputToISO(startDateTime);
    const endsAtIso = institutionalDateTimeInputToISO(endDateTime);
    if (!startsAtIso || !endsAtIso) {
      setErrorMessage("Enter valid dates and times in Philippine Time.");
      return;
    }
    const regOpensAtIso = regOpensAt ? institutionalDateTimeInputToISO(regOpensAt) : null;
    const regClosesAtIso = regClosesAt ? institutionalDateTimeInputToISO(regClosesAt) : null;
    if ((regOpensAt && !regOpensAtIso) || (regClosesAt && !regClosesAtIso)) {
      setErrorMessage("Enter valid registration dates and times in Philippine Time.");
      return;
    }
    const startsAt = new Date(startsAtIso);
    const endsAt = new Date(endsAtIso);
    if (startsAt >= endsAt) {
      setErrorMessage("Session start time must be before end time.");
      return;
    }
    if (capacity < 1) {
      setErrorMessage("Capacity must be at least 1.");
      return;
    }
    if (facilitatorsTouched || !editingSession) {
      const hasLead = leadFacilitatorKey && (
        internalFacilitatorIds.some((id) => `internal:${id}` === leadFacilitatorKey) ||
        externalFacilitators.some((item) => `external:${item.key}` === leadFacilitatorKey)
      );
      if (!hasLead) {
        setErrorMessage("Assign at least one facilitator and choose the lead facilitator.");
        return;
      }
    }
    if (editingSession && scheduleWillChange() && !scheduleReviewed) {
      setScheduleReviewOpen(true);
      return;
    }

    if (!editingSession && (!formService?.is_active || !formService.booking_pathways.includes("GROUP_SESSION"))) {
      setErrorMessage("Choose an active Service that offers Group Sessions.");
      return;
    }

    let saved: boolean;
    try {
      const facilitatorAssignments = [
        ...internalFacilitatorIds.map((id) => ({
          kind: "INTERNAL" as const,
          internal_user_id: id,
          external_display_name: "",
          is_lead: leadFacilitatorKey === `internal:${id}`,
        })),
        ...externalFacilitators.map((item) => ({
          kind: "EXTERNAL" as const,
          internal_user_id: null,
          external_display_name: item.name,
          is_lead: leadFacilitatorKey === `external:${item.key}`,
        })),
      ];
      const common = {
        title: title.trim(),
        description: description.trim(),
        delivery_mode: deliveryMode,
        venue_or_meeting_url: venueOrUrl.trim(),
        starts_at: startsAtIso,
        ends_at: endsAtIso,
        capacity,
        reg_opens_at: regOpensAtIso,
        reg_closes_at: regClosesAtIso,
      };
      if (editingSession) {
        saved = (await runStaffAction(
          () => updateMutation.mutateAsync({
            sessionId: editingSession.id,
            data: {
              ...common,
              ...(facilitatorsTouched ? { facilitators: facilitatorAssignments } : {}),
            },
          }),
          "Could not save the Group Session.",
        )) !== undefined;
      } else {
        saved = (await runStaffAction(
          () => createMutation.mutateAsync({
            serviceId: formService!.id,
            data: { ...common, facilitators: facilitatorAssignments },
          }),
          "Could not save the Group Session.",
        )) !== undefined;
      }
      if (!saved) return;

      await invalidateAll();
      setSuccessMessage(
        editingSession
          ? `Group Session "${editingSession.title}" updated.`
          : "Group Session created in Draft status.",
      );
      setCreateOpen(false);
      setScheduleReviewOpen(false);
      resetForm();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not save the Group Session.";
      setErrorMessage(msg);
    }
  };

  const handlePublish = async (session: GroupSessionResponse) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    const result = await runStaffAction(
      () => publishMutation.mutateAsync({ sessionId: session.id }),
      "Failed to publish session.",
    );
    if (!result) return;
    await invalidateAll();
    setSuccessMessage(`Session "${session.title}" published for student registration.`);
  };

  const handleComplete = async (session: GroupSessionResponse) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    const result = await runStaffAction(
      () => completeMutation.mutateAsync({ sessionId: session.id }),
      "Failed to complete session.",
    );
    if (!result) return;
    await invalidateAll();
    setSuccessMessage(`Session "${session.title}" marked as completed.`);
  };

  const handleCancel = async () => {
    if (!cancelModalSession) return;
    if (!cancelReason.trim()) {
      setErrorMessage("A cancellation reason is required.");
      return;
    }
    const target = cancelModalSession;
    const reason = cancelReason.trim();
    const result = await runStaffAction(
      () => cancelMutation.mutateAsync({ sessionId: target.id, data: { reason } }),
      "Failed to cancel session.",
    );
    if (!result) return;
    await invalidateAll();
    setSuccessMessage(`Session "${target.title}" cancelled.`);
    setCancelModalSession(null);
    setCancelReason("");
  };

  const handleWithdraw = async () => {
    if (!withdrawSession) return;
    const target = withdrawSession;
    const result = await runStaffAction(
      () => withdrawMutation.mutateAsync({ sessionId: target.id, data: { reason: "Draft withdrawn by staff." } }),
      "Failed to withdraw session.",
    );
    if (!result) return;
    await invalidateAll();
    setSuccessMessage(`Draft session "${target.title}" withdrawn. Its record is preserved.`);
    setWithdrawSession(null);
  };

  return (
    <PanelSection
      title={attendanceOnly ? "Registrations & Attendance" : "Group Sessions & Events"}
      titleId="service-group-sessions-heading"
    >
      <div className="flex flex-col gap-4">
        {errorMessage && (
          <Notice role="alert" tone="danger" className="mb-2">
            {errorMessage}
          </Notice>
        )}
        {successMessage && (
          <Notice role="status" tone="success" className="mb-2">
            {successMessage}
          </Notice>
        )}
        {continuation.notice ? (
          <Notice role="status" tone="info" className="mb-2">
            {continuation.notice}
          </Notice>
        ) : null}

        {/* Operational Metrics Cards */}
        {!attendanceOnly && metricsQuery.isError ? <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void metricsQuery.refetch()}>Retry summary</Button>}>{groupSessionsError(metricsQuery.error, "The session summary could not be loaded.")}</Notice> : null}
        {!attendanceOnly && metrics && !metricsQuery.isError && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 rounded-sm border border-border bg-subtle p-3">
            <div>
              <p className="text-xs font-semibold uppercase text-muted">Total Sessions</p>
              <p className="mt-1 text-xl font-bold text-ink">{metrics.total_sessions}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-muted">Published</p>
              <p className="mt-1 text-xl font-bold text-accent">{metrics.published_sessions}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-muted">Completed</p>
              <p className="mt-1 text-xl font-bold text-success">{metrics.completed_sessions}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-muted">Registrations</p>
              <p className="mt-1 text-xl font-bold text-ink">{metrics.total_registrations}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-muted">Capacity Used</p>
              <p className="mt-1 text-xl font-bold text-ink">
                {metrics.capacity_utilization_percent}%
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-muted">Attendance Rate</p>
              <p className="mt-1 text-xl font-bold text-ink">
                {metrics.attendance_rate_percent}%
              </p>
            </div>
          </div>
        )}

        {!service ? <FloatingListTools compact label="Group Session filters" filterCount={Number(Boolean(serviceFilter)) + Number(Boolean(fromDate)) + Number(Boolean(toDate))} clear={serviceFilter || fromDate || toDate ? <Button variant="quiet" onClick={() => { setServiceFilter(""); setFromDate(""); setToDate(""); }}>Clear filters</Button> : undefined} filters={<>
          <FilterField label="Service" htmlFor="group-session-service-filter"><Select id="group-session-service-filter" value={serviceFilter} onChange={(event) => setServiceFilter(event.target.value)}>
            <option value="">All Services</option>{serviceChoices.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </Select></FilterField>
          <FilterField label="From date" htmlFor="group-session-from"><Input id="group-session-from" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></FilterField>
          <FilterField label="To date" htmlFor="group-session-to"><Input id="group-session-to" type="date" value={toDate} min={fromDate || undefined} onChange={(event) => setToDate(event.target.value)} /></FilterField>
        </>}>
          <ListToolField label="Status" htmlFor="group-session-status"><Select id="group-session-status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All statuses</option>{["DRAFT", "PUBLISHED", "CANCELLED", "COMPLETED"].map((status) => <option key={status} value={status}>{status.charAt(0) + status.slice(1).toLowerCase()}</option>)}
          </Select></ListToolField>
        </FloatingListTools> : null}
        {!attendanceOnly ? <div className="flex flex-wrap justify-end gap-3">
          <Button onClick={openCreate} disabled={sessionsQuery.isPending || sessionsQuery.isError || (service ? !service.is_active : !user.capabilities.includes("services.catalog.view"))}
            title={service && !service.is_active ? "Enable the Service before creating events." : undefined}>
            <Plus className="mr-1.5 h-4 w-4" />Schedule Group Session
          </Button>
          {!service && !user.capabilities.includes("services.catalog.view") ? <p className="text-sm text-muted">Service catalog access is needed to choose a Service for a new session.</p> : null}
        </div> : null}

        {sessionsQuery.isPending ? (
          <p className="text-sm text-muted">Loading group sessions…</p>
        ) : sessionsQuery.isError ? (
          <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void sessionsQuery.refetch()}>Retry</Button>}>
            {groupSessionsError(sessionsQuery.error, "Group sessions could not be loaded. Try again.")}
          </Notice>
        ) : sessions.length === 0 ? (
          <div className="rounded-sm border border-dashed border-border p-6 text-center text-sm text-muted">
            No group sessions match this view.
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {sessions.map((sess) => {
              const statusColors: Record<string, string> = {
                DRAFT: "bg-surface-elevated text-muted border-border",
                PUBLISHED: "bg-accent/10 text-accent border-accent/20",
                CANCELLED: "bg-critical/10 text-critical border-critical/20",
                COMPLETED: "bg-success/10 text-success border-success/20",
              };
              const badgeClass = statusColors[sess.status] || "bg-subtle text-muted";

              return (
                <div
                  key={sess.id}
                  className="flex flex-col gap-3 rounded-sm border border-border bg-surface p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="font-semibold text-ink text-base"><Link href={`/portal/group-sessions/${sess.id}`} className="underline underline-offset-4">{sess.title}</Link></h4>
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium border ${badgeClass}`}
                        >
                          {sess.status}
                        </span>
                      </div>
                      {!service ? <p className="mt-1 text-sm text-muted">{sess.service_name} · {sess.active_registrations_count}/{sess.capacity} registered</p> : null}
                      {sess.description && (
                        <p className="mt-1 text-sm text-muted line-clamp-2">{sess.description}</p>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {!attendanceOnly && (sess.status === "DRAFT" || sess.status === "PUBLISHED") &&
                      sess.can_manage ? (
                        <Button
                          className="min-h-8 px-2.5 py-1 text-xs"
                          variant="secondary"
                          onClick={() => openEdit(sess)}
                        >
                          Edit
                        </Button>
                      ) : null}
                      {!attendanceOnly && sess.status === "DRAFT" && sess.can_manage && (
                        <>
                          <Button
                            className="min-h-8 px-2.5 py-1 text-xs"
                            variant="secondary"
                            onClick={() => handlePublish(sess)}
                            disabled={publishMutation.isPending}
                          >
                            <CheckCircle className="mr-1.5 h-3.5 w-3.5 text-accent" />
                            Publish
                          </Button>
                          <Button
                            className="min-h-8 px-2 py-1 text-xs"
                            variant="secondary"
                            onClick={() => setWithdrawSession(sess)}
                          >
                            <Ban className="mr-1 h-3.5 w-3.5 text-critical" />
                            Withdraw
                          </Button>
                        </>
                      )}

                      {!attendanceOnly && sess.status === "PUBLISHED" && sess.can_manage && (
                        <>
                          <Button
                            className="min-h-8 px-2.5 py-1 text-xs"
                            variant="secondary"
                            onClick={() => handleComplete(sess)}
                          disabled={completeMutation.isPending || !sess.can_complete}
                          title={!sess.can_complete ? "Available after the event ends." : undefined}
                          >
                            <UserCheck className="mr-1.5 h-3.5 w-3.5 text-success" />
                            Complete
                          </Button>
                          <Button
                            className="min-h-8 px-2.5 py-1 text-xs"
                            variant="secondary"
                            onClick={() => {
                              setCancelModalSession(sess);
                              setCancelReason("");
                            }}
                          >
                            <XCircle className="mr-1.5 h-3.5 w-3.5 text-critical" />
                            Cancel
                          </Button>
                        </>
                      )}

                      {sess.can_access_participants ? (
                        <Button
                          className="min-h-8 px-2.5 py-1 text-xs"
                          variant="secondary"
                          onClick={() => setRosterSession(sess)}
                        >
                          <Users className="mr-1.5 h-3.5 w-3.5" />
                          Roster & Attendance ({sess.active_registrations_count}/{sess.capacity})
                        </Button>
                      ) : null}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-2 pt-2 border-t border-border/50 text-xs sm:grid-cols-3 text-muted">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="h-3.5 w-3.5 text-muted" />
                      <span>
                        {formatInstitutionalDateTime(sess.starts_at)} – {formatInstitutionalDateTime(sess.ends_at)}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {sess.delivery_mode === "ONLINE" ? (
                        <Video className="h-3.5 w-3.5 text-accent" />
                      ) : (
                        <MapPin className="h-3.5 w-3.5 text-muted" />
                      )}
                      <span>
                        {sess.delivery_mode === "ONLINE" ? "Online" : "In-Person"}
                        {sess.venue_or_meeting_url && ` · ${sess.venue_or_meeting_url}`}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Users className="h-3.5 w-3.5 text-muted" />
                      <span>
                        Facilitators:{" "}
                        {sess.facilitators
                          .filter((facilitator) => facilitator.is_current)
                          .map((facilitator) =>
                            `${facilitator.display_name}${facilitator.is_lead ? " (Lead)" : ""}${facilitator.kind === "EXTERNAL" ? " · Guest" : ""}`,
                          )
                          .join(", ") || "None"}
                        {sess.facilitators.some((facilitator) => !facilitator.is_current) ? (
                          <span className="block">
                            Former facilitators:{" "}
                            {sess.facilitators
                              .filter((facilitator) => !facilitator.is_current)
                              .map((facilitator) => facilitator.display_name)
                              .join(", ")}
                          </span>
                        ) : null}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* CREATE SESSION MODAL */}
      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) setScheduleReviewOpen(false);
        }}
      >
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogTitle>{editingSession ? "Edit Group Session" : "Schedule Group Session"}</DialogTitle>
          <form onSubmit={(event) => void handleSaveForm(event)} className="mt-4 flex flex-col gap-4">
            {!service && !editingSession ? <GroupSessionServicePicker selected={selectedService} onSelect={(chosen) => { setSelectedService(chosen); setDeliveryMode(chosen.delivery_modes[0] ?? DeliveryMode.IN_PERSON); }} /> : null}
            {editingSession ? <p className="text-sm text-muted">{editingSession.service_name}</p> : null}
            <div>
              <Label htmlFor="session-title">Title *</Label>
              <Input
                id="session-title"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Career Planning Workshop"
              />
            </div>

            <div>
              <Label htmlFor="session-desc">Description</Label>
              <Textarea
                id="session-desc"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Session objectives, requirements, target attendees..."
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="session-delivery">Delivery Mode</Label>
                <Select
                  id="session-delivery"
                  value={deliveryMode}
                  onChange={(e) => setDeliveryMode(e.target.value as DeliveryMode)}
                >
                  {deliveryModes.map((mode) => (
                    <option key={mode} value={mode}>
                      {mode === "ONLINE" ? "Online" : "In-Person"}
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <Label htmlFor="session-capacity">Capacity *</Label>
                <Input
                  id="session-capacity"
                  type="number"
                  min={1}
                  required
                  value={capacity}
                  onChange={(e) => setCapacity(parseInt(e.target.value, 10) || 1)}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="session-venue">
                {deliveryMode === "ONLINE" ? "Meeting URL / Link" : "Venue / Room"}
              </Label>
              <Input
                id="session-venue"
                value={venueOrUrl}
                onChange={(e) => setVenueOrUrl(e.target.value)}
                placeholder={
                  deliveryMode === "ONLINE"
                    ? "https://meet.example.edu/session"
                    : "Guidance Conference Room A"
                }
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="session-start">Start Time *</Label>
                <Input
                  id="session-start"
                  type="datetime-local"
                  required
                  value={startDateTime}
                  onChange={(e) => setStartDateTime(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="session-end">End Time *</Label>
                <Input
                  id="session-end"
                  type="datetime-local"
                  required
                  value={endDateTime}
                  onChange={(e) => setEndDateTime(e.target.value)}
                />
              </div>
            </div>

            <fieldset className="rounded-md border border-border p-3">
              <legend className="px-1 text-sm font-semibold text-ink">Facilitators</legend>
              <p className="mb-3 text-xs leading-5 text-muted">
                Internal assignments grant event access only. They do not qualify someone to provide individual Appointments. External guests do not need COMPASS accounts.
              </p>
              {facilitatorCandidatesQuery.isPending ? (
                <p className="text-sm text-muted">Loading eligible internal facilitators…</p>
              ) : facilitatorCandidatesQuery.isError ? (
                <Notice role="alert" tone="danger">
                  Facilitators could not be loaded. {" "}
                  <Button
                    type="button"
                    variant="quiet"
                    onClick={() => void facilitatorCandidatesQuery.refetch()}
                  >
                    Retry
                  </Button>
                </Notice>
              ) : (
                <>
                  <Label htmlFor="facilitator-search">Search internal facilitators</Label>
                  <Input
                    id="facilitator-search"
                    value={facilitatorSearch}
                    onChange={(event) => setFacilitatorSearch(event.target.value)}
                    placeholder="Search name"
                    className="mt-1"
                  />
                  <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto rounded-sm border border-border p-2">
                    {visibleFacilitatorCandidates.map((candidate) => (
                      <li key={candidate.id}>
                        <label className="flex items-center gap-2 py-1 text-sm text-ink">
                          <input
                            type="checkbox"
                            checked={internalFacilitatorIds.includes(candidate.id)}
                            onChange={(event) => {
                              const checked = event.target.checked;
                              const key = `internal:${candidate.id}`;
                              setFacilitatorsTouched(true);
                              setInternalFacilitatorIds((current) => checked
                                ? [...current, candidate.id]
                                : current.filter((id) => id !== candidate.id));
                              if (!checked && leadFacilitatorKey === key) setLeadFacilitatorKey("");
                              else if (checked && !leadFacilitatorKey) setLeadFacilitatorKey(key);
                            }}
                          />
                          <span>
                            {candidate.display_name} <span className="text-xs text-muted">· {candidate.role === "COUNSELOR" ? "Counselor" : "Guidance Services Staff"}</span>
                          </span>
                        </label>
                      </li>
                    ))}
                    {visibleFacilitatorCandidates.length === 0 ? (
                      <li className="py-1 text-sm text-muted">No matching internal facilitators.</li>
                    ) : null}
                  </ul>
                </>
              )}
              <div className="mt-3">
                <Label htmlFor="external-facilitator">External guest or speaker</Label>
                <div className="mt-1 flex gap-2">
                  <Input
                    id="external-facilitator"
                    value={externalNameDraft}
                    maxLength={255}
                    onChange={(event) => setExternalNameDraft(event.target.value)}
                    placeholder="Name to display for this event"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!externalNameDraft.trim()}
                    onClick={() => {
                      const name = externalNameDraft.trim();
                      if (externalFacilitators.some((item) => item.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
                        setErrorMessage("This external facilitator is already listed.");
                        return;
                      }
                      const key = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
                      setExternalFacilitators((current) => [...current, { key, name }]);
                      if (!leadFacilitatorKey) setLeadFacilitatorKey(`external:${key}`);
                      setFacilitatorsTouched(true);
                      setExternalNameDraft("");
                    }}
                  >
                    Add
                  </Button>
                </div>
                {externalFacilitators.length ? (
                  <ul className="mt-2 space-y-1">
                    {externalFacilitators.map((facilitator) => (
                      <li key={facilitator.key} className="flex items-center justify-between gap-2 text-sm">
                        <span>{facilitator.name} <span className="text-xs text-muted">· Guest</span></span>
                        <Button
                          type="button"
                          variant="quiet"
                          onClick={() => {
                            setExternalFacilitators((current) => current.filter((item) => item.key !== facilitator.key));
                            if (leadFacilitatorKey === `external:${facilitator.key}`) setLeadFacilitatorKey("");
                            setFacilitatorsTouched(true);
                          }}
                        >
                          Remove
                        </Button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <div className="mt-3">
                <Label htmlFor="session-facilitator">Lead facilitator *</Label>
                <Select
                  id="session-facilitator"
                  required
                  value={leadFacilitatorKey}
                  onChange={(event) => {
                    setLeadFacilitatorKey(event.target.value);
                    setFacilitatorsTouched(true);
                  }}
                >
                  <option value="">Choose a lead facilitator…</option>
                  {internalFacilitatorIds.map((id) => {
                    const candidate = facilitatorCandidates.find((item) => item.id === id);
                    return candidate ? (
                      <option key={id} value={`internal:${id}`}>
                        {candidate.display_name} · {candidate.role === "COUNSELOR" ? "Counselor" : "Guidance Services Staff"}
                      </option>
                    ) : null;
                  })}
                  {externalFacilitators.map((item) => (
                    <option key={item.key} value={`external:${item.key}`}>
                      {item.name} · Guest
                    </option>
                  ))}
                </Select>
              </div>
            </fieldset>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="reg-opens">Reg. Opens (Optional)</Label>
                <Input
                  id="reg-opens"
                  type="datetime-local"
                  value={regOpensAt}
                  onChange={(e) => setRegOpensAt(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="reg-closes">Reg. Closes (Optional)</Label>
                <Input
                  id="reg-closes"
                  type="datetime-local"
                  value={regClosesAt}
                  onChange={(e) => setRegClosesAt(e.target.value)}
                />
              </div>
            </div>

            <div className="mt-2 flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending || (!editingSession && !formService)}>
                {createMutation.isPending || updateMutation.isPending
                  ? "Saving…"
                  : editingSession
                    ? "Save changes"
                    : "Create Session (Draft)"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <ConsequentialActionDialog
        open={scheduleReviewOpen}
        title="Notify registered students about this change?"
        confirmLabel="Save and notify"
        pendingLabel="Saving…"
        pending={updateMutation.isPending}
        error={errorMessage}
        onOpenChange={setScheduleReviewOpen}
        onConfirm={() => void handleSaveForm(undefined, true)}
      >
        <p className="text-sm text-muted">
          Registered students will receive an in-app notice to review the current event details. The schedule change will be rejected if it conflicts with a facilitator or a student’s existing booking.
        </p>
      </ConsequentialActionDialog>

      {/* CANCEL SESSION DIALOG */}
      <ConsequentialActionDialog
        open={cancelModalSession !== null}
        title="Cancel Group Session"
        confirmLabel="Yes, Cancel Session"
        pendingLabel="Cancelling session..."
        error={errorMessage}
        variant="danger"
        pending={cancelMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setCancelModalSession(null);
        }}
        onConfirm={handleCancel}
      >
        <div>
          <p className="text-sm text-muted">
            Are you sure you want to cancel &quot;{cancelModalSession?.title}&quot;? All registered participants
            will have their registrations cancelled and will receive operational notifications.
          </p>
          <div className="mt-3">
            <Label htmlFor="cancel-reason">Cancellation Reason *</Label>
            <Input
              id="cancel-reason"
              required
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="e.g. Facilitator emergency, university closure..."
            />
          </div>
        </div>
      </ConsequentialActionDialog>

      {/* WITHDRAW DRAFT SESSION DIALOG */}
      <ConsequentialActionDialog
        open={withdrawSession !== null}
        title="Withdraw Draft Session"
        confirmLabel="Withdraw Draft"
        pendingLabel="Withdrawing..."
        error={errorMessage}
        variant="danger"
        pending={withdrawMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setWithdrawSession(null);
        }}
        onConfirm={handleWithdraw}
      >
        <p className="text-sm text-muted">
          Withdraw draft session &quot;{withdrawSession?.title}&quot; from the active workflow? Its identifier,
          facilitator assignments, and audit history will be retained.
        </p>
      </ConsequentialActionDialog>

      {/* ROSTER & ATTENDANCE MODAL */}
      {rosterSession && (
        <GroupSessionRosterModal
          session={rosterSession}
          onClose={() => {
            setRosterSession(null);
            invalidateAll();
          }}
        />
      )}
      <StepUpDialog
        open={continuation.open}
        requirement={continuation.requirement}
        onOpenChange={continuation.setOpen}
        isContinuing={continuation.isContinuing}
        onVerified={continuation.continueAfterVerification}
      />
    </PanelSection>
  );
}

// --- ROSTER & ATTENDANCE MODAL ---

function GroupSessionRosterModal({
  session,
  onClose,
}: {
  session: GroupSessionResponse;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const continuation = useStepUpContinuation();
  const regsQuery = useGroupSessionsListRegistrations(session.id, {
    query: { retry: false },
  });
  const attendanceMutation = useGroupSessionsRecordAttendance();

  const regs = regsQuery.data?.data ?? [];
  const [attendanceState, setAttendanceState] = useState<
    Record<string, { attended: boolean; notes: string }>
  >({});
  const [initialized, setInitialized] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  // Sync initial attendance state when data arrives
  if (!initialized && regs.length > 0) {
    const initial: Record<string, { attended: boolean; notes: string }> = {};
    for (const r of regs) {
      initial[r.id] = {
        attended: r.attended ?? false,
        notes: r.attendance_notes ?? "",
      };
    }
    setAttendanceState(initial);
    setInitialized(true);
  }

  const handleSaveAttendance = async () => {
    setSaveStatus(null);
    const activeIds = new Set(regs.filter((registration) => registration.status === "REGISTERED").map((registration) => registration.id));
    const records = Object.entries(attendanceState).filter(([regId]) => activeIds.has(regId)).map(([regId, state]) => ({
      registration_id: regId,
      attended: state.attended,
      ...(session.can_manage ? { notes: state.notes } : {}),
    }));

    const result = await continuation.run(
      () => attendanceMutation.mutateAsync({ sessionId: session.id, data: { records } }),
      { onFailure: () => setSaveStatus("Failed to save attendance.") },
    );
    if (!result) return;
    await queryClient.invalidateQueries({
      queryKey: getGroupSessionsListRegistrationsQueryKey(session.id),
    });
    setSaveStatus("Attendance saved successfully.");
  };

  const handleExportCsv = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      const res = await fetch(`/api/v1/group-sessions/${session.id}/roster/export`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("CSV export failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const sanitizedTitle = session.title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      a.download = `roster-${sanitizedTitle}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setExportError("The participant roster could not be exported. Try again.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <>
    <Dialog open={true} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogTitle className="flex items-center justify-between">
          <span>Participant Roster & Attendance</span>
          {session.can_export_roster ? (
            <Button
              className="min-h-8 px-2.5 py-1 text-xs"
              variant="secondary"
              onClick={handleExportCsv}
              disabled={isExporting}
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              {isExporting ? "Exporting..." : "Export CSV Roster"}
            </Button>
          ) : null}
        </DialogTitle>

        <div className="text-xs text-muted">
          Session: <strong className="text-ink">{session.title}</strong> · Capacity:{" "}
          <strong className="text-ink">{session.capacity}</strong> · Registered:{" "}
          <strong className="text-ink">{regs.filter((r) => r.status === "REGISTERED").length}</strong>
        </div>

        {exportError ? (
          <Notice role="alert" tone="danger" className="my-2">
            {exportError}
          </Notice>
        ) : null}

        {saveStatus && (
          <Notice
            role="status"
            tone={saveStatus.includes("success") ? "success" : "danger"}
            className="my-2"
          >
            {saveStatus}
          </Notice>
        )}

        {continuation.notice ? (
          <Notice role="status" tone="info" className="my-2">
            {continuation.notice}
          </Notice>
        ) : null}

        <div className="mt-3 overflow-y-auto flex-1 pr-1">
          {regsQuery.isPending ? (
            <p className="text-sm text-muted">Loading roster…</p>
          ) : regsQuery.isError ? (
            <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void regsQuery.refetch()}>Retry roster</Button>}>
              {groupSessionsError(regsQuery.error, "The participant roster could not be loaded.")}
            </Notice>
          ) : regs.length === 0 ? (
            <div className="rounded-sm border border-dashed border-border p-6 text-center text-sm text-muted">
              No students have registered for this session yet.
            </div>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-subtle text-muted uppercase font-semibold">
                  <th className="py-2 px-3">Student</th>
                  <th className="py-2 px-3">Status</th>
                  {session.can_manage ? <th className="py-2 px-3">Registered At</th> : null}
                  <th className="py-2 px-3 text-center">Attended</th>
                  {session.can_manage ? <th className="py-2 px-3">Notes</th> : null}
                </tr>
              </thead>
              <tbody>
                {regs.map((r) => {
                  const state = attendanceState[r.id] ?? {
                    attended: r.attended ?? false,
                    notes: r.attendance_notes ?? "",
                  };
                  const isRegistered = r.status === "REGISTERED";

                  return (
                    <tr key={r.id} className="border-b border-border/50 hover:bg-subtle/50">
                      <td className="py-2 px-3">
                        <div className="font-semibold text-ink">{r.student_name}</div>
                        {session.can_manage && r.student_email ? (
                          <div className="text-muted text-[11px]">{r.student_email}</div>
                        ) : null}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                            isRegistered
                              ? "bg-accent/10 text-accent"
                              : "bg-critical/10 text-critical"
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      {session.can_manage ? (
                        <td className="py-2 px-3 text-muted">
                          {r.registered_at ? formatInstitutionalDateTime(r.registered_at) : "—"}
                        </td>
                      ) : null}
                      <td className="py-2 px-3 text-center">
                        <input
                          type="checkbox"
                          aria-label={`Attended: ${r.student_name}`}
                          disabled={!isRegistered || !session.can_record_attendance}
                          checked={state.attended}
                          onChange={(e) =>
                            setAttendanceState((prev) => ({
                              ...prev,
                              [r.id]: { ...state, attended: e.target.checked },
                            }))
                          }
                          className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                        />
                      </td>
                      {session.can_manage ? (
                        <td className="py-2 px-3">
                          <Input
                            aria-label={`Attendance notes: ${r.student_name}`}
                            disabled={!isRegistered || !session.can_record_attendance}
                            value={state.notes}
                            onChange={(e) =>
                              setAttendanceState((prev) => ({
                                ...prev,
                                [r.id]: { ...state, notes: e.target.value },
                              }))
                            }
                            placeholder="Optional notes..."
                            className="h-7 text-xs"
                          />
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="mt-4 flex justify-end gap-2 pt-3 border-t border-border">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button
            onClick={handleSaveAttendance}
            disabled={
              !session.can_record_attendance || !["PUBLISHED", "COMPLETED"].includes(session.status) || regsQuery.isError || attendanceMutation.isPending || !regs.some((registration) => registration.status === "REGISTERED")
            }
          >
            {attendanceMutation.isPending ? "Saving..." : "Save Attendance"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
    <StepUpDialog
      open={continuation.open}
      requirement={continuation.requirement}
      onOpenChange={continuation.setOpen}
      isContinuing={continuation.isContinuing}
      onVerified={continuation.continueAfterVerification}
    />
    </>
  );
}

// --- STUDENT PANEL ---

export function ServiceGroupSessionsStudentPanel({
  service,
}: {
  service?: ServiceResponse;
}) {
  const queryClient = useQueryClient();
  const [registeringId, setRegisteringId] = useState<string | null>(null);
  const [cancellingSession, setCancellingSession] = useState<StudentGroupSessionResponse | null>(
    null
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const discoveryParams = service ? { service_id: service.id } : undefined;
  const discoverQuery = useGroupSessionsDiscover(discoveryParams, {
    query: { retry: false },
  });

  const registerMutation = useGroupSessionsRegister();
  const cancelRegMutation = useGroupSessionsCancelRegistration();

  const sessions = discoverQuery.data?.data ?? [];

  const handleRegister = async (session: StudentGroupSessionResponse) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    setRegisteringId(session.id);
    try {
      await registerMutation.mutateAsync({ sessionId: session.id });
      await queryClient.invalidateQueries({
        queryKey: getGroupSessionsDiscoverQueryKey(discoveryParams),
      });
      await queryClient.invalidateQueries({
        queryKey: getGroupSessionsGetMyRegistrationsQueryKey(),
      });
      setSuccessMessage(`Successfully registered for "${session.title}"!`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to register for session.";
      setErrorMessage(msg);
    } finally {
      setRegisteringId(null);
    }
  };

  const handleCancelRegistration = async () => {
    if (!cancellingSession) return;
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await cancelRegMutation.mutateAsync({ sessionId: cancellingSession.id });
      await queryClient.invalidateQueries({
        queryKey: getGroupSessionsDiscoverQueryKey(discoveryParams),
      });
      await queryClient.invalidateQueries({
        queryKey: getGroupSessionsGetMyRegistrationsQueryKey(),
      });
      setSuccessMessage(`Your registration for "${cancellingSession.title}" has been cancelled.`);
      setCancellingSession(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel registration.";
      setErrorMessage(msg);
    }
  };

  return (
    <PanelSection
      title="Upcoming Group Sessions & Workshops"
      titleId="group-sessions-student-heading"
    >
      <div className="flex flex-col gap-4">
        {errorMessage && (
          <Notice role="alert" tone="danger" className="mb-2">
            {errorMessage}
          </Notice>
        )}
        {successMessage && (
          <Notice role="status" tone="success" className="mb-2">
            {successMessage}
          </Notice>
        )}

        {service ? <Link href="/portal/group-sessions/my" className="inline-flex min-h-11 items-center text-sm font-semibold text-brand underline underline-offset-4">My Registrations</Link> : null}

        {discoverQuery.isPending ? (
          <p className="text-sm text-muted">Loading upcoming group sessions…</p>
        ) : discoverQuery.isError ? (
          <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void discoverQuery.refetch()}>Retry</Button>}>
            {groupSessionsError(discoverQuery.error, "Upcoming group sessions could not be loaded. Try again.")}
          </Notice>
        ) : sessions.length === 0 ? (
          <div className="rounded-sm border border-dashed border-border p-6 text-center text-sm text-muted">
            {service
              ? "No upcoming group sessions are currently scheduled for this Service."
              : "No upcoming group sessions are currently scheduled."}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {sessions.map((sess) => (
              <div
                key={sess.id}
                className="flex flex-col gap-3 rounded-sm border border-border bg-surface p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h4 className="font-semibold text-ink text-base">
                      <Link
                        href={`/portal/group-sessions/${sess.id}`}
                        className="underline decoration-brand-line underline-offset-4 hover:decoration-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                      >
                        {sess.title}
                      </Link>
                    </h4>
                    {sess.description && (
                      <p className="mt-1 text-sm text-muted line-clamp-2">{sess.description}</p>
                    )}
                  </div>

                  <div>
                    {sess.is_registered_by_me ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-semibold text-success border border-success/20">
                          <CheckCircle className="h-3.5 w-3.5" />
                          You are registered
                        </span>
                        <Button
                          className="min-h-8 px-2.5 py-1 text-xs"
                          variant="secondary"
                          onClick={() => setCancellingSession(sess)}
                        >
                          Cancel Registration
                        </Button>
                      </div>
                    ) : sess.can_register ? (
                      <Button
                        className="min-h-8 px-3 py-1 text-xs"
                        onClick={() => handleRegister(sess)}
                        disabled={registeringId === sess.id}
                      >
                        {registeringId === sess.id ? "Registering..." : "Register"}
                      </Button>
                    ) : (
                      <div className="text-right">
                        <span className="inline-flex items-center rounded-full border border-border bg-surface-muted px-2.5 py-0.5 text-xs font-semibold text-muted">
                          {sess.is_full ? "Session Full" : "Registration unavailable"}
                        </span>
                        {sess.registration_block_reason ? (
                          <p className="mt-1 max-w-56 text-xs text-muted">
                            {sess.registration_block_reason}
                          </p>
                        ) : null}
                      </div>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-2 pt-2 border-t border-border/50 text-xs sm:grid-cols-3 text-muted">
                  <div className="flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5 text-muted" />
                    <span>{formatInstitutionalDateTime(sess.starts_at)}</span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {sess.delivery_mode === "ONLINE" ? (
                      <Video className="h-3.5 w-3.5 text-accent" />
                    ) : (
                      <MapPin className="h-3.5 w-3.5 text-muted" />
                    )}
                    <span>
                      {sess.delivery_mode === "ONLINE" ? "Online" : "In-Person"}
                      {sess.venue_or_meeting_url && ` · ${sess.venue_or_meeting_url}`}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Users className="h-3.5 w-3.5 text-muted" />
                    <span>
                      {sess.is_full
                        ? "0 seats left"
                        : `${sess.seats_remaining} of ${sess.capacity} seats remaining`}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* CONFIRM REGISTRATION CANCELLATION */}
      <ConsequentialActionDialog
        open={cancellingSession !== null}
        title="Cancel Registration"
        confirmLabel="Yes, Cancel My Registration"
        pendingLabel="Cancelling..."
        error={errorMessage}
        variant="danger"
        pending={cancelRegMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setCancellingSession(null);
        }}
        onConfirm={handleCancelRegistration}
      >
        <p className="text-sm text-muted">
          Are you sure you want to cancel your registration for &quot;{cancellingSession?.title}&quot;? Your seat will be released to other students.
        </p>
      </ConsequentialActionDialog>
    </PanelSection>
  );
}


function GroupSessionServicePicker({ selected, onSelect }: { selected: ServiceResponse | null; onSelect: (service: ServiceResponse) => void }) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const catalog = useServicesList({ page, page_size: 50, search: search || undefined }, { query: { retry: false } });
  const choices = (catalog.data?.data.items ?? []).filter((item) => item.is_active && item.booking_pathways.includes("GROUP_SESSION"));
  return <div className="space-y-2">
    <Label htmlFor="group-session-service-search">Find a Service</Label>
    <Input id="group-session-service-search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search Services" />
    <Label htmlFor="group-session-service">Service *</Label>
    <Select id="group-session-service" required value={selected?.id ?? ""} disabled={catalog.isPending || catalog.isError} onChange={(event) => {
      const choice = choices.find((item) => item.id === event.target.value);
      if (choice) onSelect(choice);
    }}>
      <option value="">Choose a Service…</option>
      {selected && !choices.some((item) => item.id === selected.id) ? <option value={selected.id}>{selected.name}</option> : null}
      {choices.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </Select>
    {catalog.isPending ? <p role="status" className="text-sm text-muted">Loading Services…</p> : catalog.isError ? <Notice role="alert" tone="danger" action={<Button type="button" variant="secondary" onClick={() => void catalog.refetch()}>Retry Services</Button>}>{groupSessionsError(catalog.error, "Services could not be loaded.")}</Notice> : choices.length === 0 ? <p className="text-sm text-muted">No Services offering Group Sessions on this page. Try another search or page.</p> : null}
    <div className="flex gap-3"><Button type="button" variant="quiet" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>Previous Services</Button><Button type="button" variant="quiet" disabled={!catalog.data?.data.has_next} onClick={() => setPage((value) => value + 1)}>More Services</Button></div>
  </div>;
}

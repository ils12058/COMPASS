"use client";

import { useState } from "react";
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
import { Select } from "@/components/ui/select";
import { PanelSection } from "@/components/ui/panel";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
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
  getGroupSessionsListStaffQueryKey,
  getGroupSessionsDiscoverQueryKey,
  getGroupSessionsGetMetricsQueryKey,
  getGroupSessionsListRegistrationsQueryKey,
} from "@/lib/api/generated/group-sessions/group-sessions";
import { useServicesGetProviders } from "@/lib/api/generated/services/services";
import {
  DeliveryMode,
  type ServiceResponse,
  type GroupSessionResponse,
  type StudentGroupSessionResponse,
} from "@/lib/api/generated/model";

// --- STAFF PANEL ---

export function ServiceGroupSessionsStaffPanel({ service }: { service: ServiceResponse }) {
  const { user } = usePortalSession();
  const canManageServices = user.capabilities.includes("services.manage");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
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
    service.delivery_modes[0] ?? DeliveryMode.IN_PERSON
  );
  const [venueOrUrl, setVenueOrUrl] = useState("");
  const [startDateTime, setStartDateTime] = useState("");
  const [endDateTime, setEndDateTime] = useState("");
  const [capacity, setCapacity] = useState(20);
  const [regOpensAt, setRegOpensAt] = useState("");
  const [regClosesAt, setRegClosesAt] = useState("");
  const [leadCounselorId, setLeadCounselorId] = useState(
    user.role === "COUNSELOR" ? user.id : ""
  );

  const sessionsQuery = useGroupSessionsListStaff(
    { service_id: service.id },
    { query: { retry: false } }
  );
  const metricsQuery = useGroupSessionsGetMetrics(
    { service_id: service.id },
    { query: { retry: false } }
  );
  const providersQuery = useServicesGetProviders(service.id, {
    query: { retry: false, enabled: canManageServices },
  });

  const createMutation = useGroupSessionsCreate();
  const publishMutation = useGroupSessionsPublish();
  const cancelMutation = useGroupSessionsCancel();
  const completeMutation = useGroupSessionsComplete();
  const withdrawMutation = useGroupSessionsWithdraw();

  const sessions = sessionsQuery.data?.data ?? [];
  const metrics = metricsQuery.data?.data;
  const fetchedProviders = providersQuery.data?.data.counselors ?? [];
  const providers =
    fetchedProviders.length > 0
      ? fetchedProviders
      : user.role === "COUNSELOR"
        ? [
            {
              id: user.id,
              display_name: `${user.first_name} ${user.last_name}`.trim() || user.email,
              is_active: true,
            },
          ]
        : [];

  const invalidateAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getGroupSessionsListStaffQueryKey({ service_id: service.id }),
      }),
      queryClient.invalidateQueries({
        queryKey: getGroupSessionsGetMetricsQueryKey({ service_id: service.id }),
      }),
      queryClient.invalidateQueries({
        queryKey: getGroupSessionsDiscoverQueryKey({ service_id: service.id }),
      }),
    ]);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
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
    const startsAt = new Date(startDateTime);
    const endsAt = new Date(endDateTime);
    if (startsAt >= endsAt) {
      setErrorMessage("Session start time must be before end time.");
      return;
    }
    if (capacity < 1) {
      setErrorMessage("Capacity must be at least 1.");
      return;
    }
    if (!leadCounselorId) {
      setErrorMessage("Please select a qualified Lead Facilitator.");
      return;
    }

    try {
      await createMutation.mutateAsync({
        serviceId: service.id,
        data: {
          title: title.trim(),
          description: description.trim(),
          delivery_mode: deliveryMode,
          venue_or_meeting_url: venueOrUrl.trim(),
          starts_at: startsAt.toISOString(),
          ends_at: endsAt.toISOString(),
          capacity,
          reg_opens_at: regOpensAt ? new Date(regOpensAt).toISOString() : null,
          reg_closes_at: regClosesAt ? new Date(regClosesAt).toISOString() : null,
          facilitator_ids: [leadCounselorId],
          lead_facilitator_id: leadCounselorId,
        },
      });

      await invalidateAll();
      setSuccessMessage("Group session created in Draft status.");
      setCreateOpen(false);
      setTitle("");
      setDescription("");
      setVenueOrUrl("");
      setStartDateTime("");
      setEndDateTime("");
      setCapacity(20);
      setRegOpensAt("");
      setRegClosesAt("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create group session.";
      setErrorMessage(msg);
    }
  };

  const handlePublish = async (session: GroupSessionResponse) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await publishMutation.mutateAsync({ sessionId: session.id });
      await invalidateAll();
      setSuccessMessage(`Session "${session.title}" published for student registration.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to publish session.";
      setErrorMessage(msg);
    }
  };

  const handleComplete = async (session: GroupSessionResponse) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await completeMutation.mutateAsync({ sessionId: session.id });
      await invalidateAll();
      setSuccessMessage(`Session "${session.title}" marked as completed.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to complete session.";
      setErrorMessage(msg);
    }
  };

  const handleCancel = async () => {
    if (!cancelModalSession) return;
    if (!cancelReason.trim()) {
      setErrorMessage("A cancellation reason is required.");
      return;
    }
    try {
      await cancelMutation.mutateAsync({
        sessionId: cancelModalSession.id,
        data: { reason: cancelReason.trim() },
      });
      await invalidateAll();
      setSuccessMessage(`Session "${cancelModalSession.title}" cancelled.`);
      setCancelModalSession(null);
      setCancelReason("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel session.";
      setErrorMessage(msg);
    }
  };

  const handleWithdraw = async () => {
    if (!withdrawSession) return;
    try {
      await withdrawMutation.mutateAsync({
        sessionId: withdrawSession.id,
        data: { reason: "Draft withdrawn by staff." },
      });
      await invalidateAll();
      setSuccessMessage(`Draft session "${withdrawSession.title}" withdrawn. Its record is preserved.`);
      setWithdrawSession(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to withdraw session.";
      setErrorMessage(msg);
    }
  };

  return (
    <PanelSection
      title="Group Sessions & Events"
      titleId="service-group-sessions-heading"
      className="mt-6"
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

        {/* Operational Metrics Cards */}
        {metrics && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 rounded-lg border border-border bg-subtle p-3">
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

        <div className="flex items-center justify-between">
          <p className="text-xs text-muted">
            Manage scheduled workshops, seminars, and group counseling activities for this Service.
          </p>
          <Button
            className="min-h-8 px-3 py-1 text-xs"
            onClick={() => {
              setErrorMessage(null);
              setSuccessMessage(null);
              setCreateOpen(true);
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Schedule Group Session
          </Button>
        </div>

        {sessionsQuery.isLoading ? (
          <p className="text-sm text-muted">Loading group sessions...</p>
        ) : sessions.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">
            No group sessions scheduled for this Service yet. Click &quot;Schedule Group Session&quot; to create one.
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
                  className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-xs"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-ink text-base">{sess.title}</h4>
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium border ${badgeClass}`}
                        >
                          {sess.status}
                        </span>
                      </div>
                      {sess.description && (
                        <p className="mt-1 text-sm text-muted line-clamp-2">{sess.description}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {sess.status === "DRAFT" && sess.can_manage && (
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

                      {sess.status === "PUBLISHED" && sess.can_manage && (
                        <>
                          <Button
                            className="min-h-8 px-2.5 py-1 text-xs"
                            variant="secondary"
                            onClick={() => handleComplete(sess)}
                            disabled={completeMutation.isPending}
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
                        Facilitators:{" "}
                        {sess.facilitators.map((f) => f.counselor_name).join(", ") || "None"}
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
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogTitle>Schedule Group Session</DialogTitle>
          <form onSubmit={handleCreate} className="mt-4 flex flex-col gap-4">
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

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="session-delivery">Delivery Mode</Label>
                <Select
                  id="session-delivery"
                  value={deliveryMode}
                  onChange={(e) => setDeliveryMode(e.target.value as DeliveryMode)}
                >
                  {service.delivery_modes.map((mode) => (
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

            <div className="grid grid-cols-2 gap-3">
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

            <div>
              <Label htmlFor="session-facilitator">Lead Facilitator *</Label>
              <Select
                id="session-facilitator"
                required
                value={leadCounselorId}
                onChange={(e) => setLeadCounselorId(e.target.value)}
              >
                <option value="">Select qualified counselor...</option>
                {providers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.display_name}
                  </option>
                ))}
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
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
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create Session (Draft)"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

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
    const records = Object.entries(attendanceState).map(([regId, state]) => ({
      registration_id: regId,
      attended: state.attended,
      ...(session.can_manage ? { notes: state.notes } : {}),
    }));

    try {
      await attendanceMutation.mutateAsync({
        sessionId: session.id,
        data: { records },
      });
      await queryClient.invalidateQueries({
        queryKey: getGroupSessionsListRegistrationsQueryKey(session.id),
      });
      setSaveStatus("Attendance saved successfully.");
    } catch {
      setSaveStatus("Failed to save attendance.");
    }
  };

  const handleExportCsv = async () => {
    setIsExporting(true);
    try {
      const res = await fetch(`/api/v1/group-sessions/${session.id}/roster.csv`, {
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
      alert("Failed to export participant roster.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
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

        {saveStatus && (
          <Notice
            role="status"
            tone={saveStatus.includes("success") ? "success" : "danger"}
            className="my-2"
          >
            {saveStatus}
          </Notice>
        )}

        <div className="mt-3 overflow-y-auto flex-1 pr-1">
          {regsQuery.isLoading ? (
            <p className="text-sm text-muted">Loading roster...</p>
          ) : regs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">
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
                          disabled={!isRegistered}
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
                            disabled={!isRegistered}
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
              !session.can_record_attendance || attendanceMutation.isPending || regs.length === 0
            }
          >
            {attendanceMutation.isPending ? "Saving..." : "Save Attendance"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// --- STUDENT PANEL ---

export function ServiceGroupSessionsStudentPanel({ service }: { service: ServiceResponse }) {
  const queryClient = useQueryClient();
  const [registeringId, setRegisteringId] = useState<string | null>(null);
  const [cancellingSession, setCancellingSession] = useState<StudentGroupSessionResponse | null>(
    null
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const discoverQuery = useGroupSessionsDiscover(
    { service_id: service.id },
    { query: { retry: false } }
  );

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
        queryKey: getGroupSessionsDiscoverQueryKey({ service_id: service.id }),
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
        queryKey: getGroupSessionsDiscoverQueryKey({ service_id: service.id }),
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
      titleId="service-group-sessions-student-heading"
      className="mt-6"
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

        <p className="text-xs text-muted">
          Browse upcoming group sessions for this Service and secure your seat. Capacity is limited.
        </p>

        {discoverQuery.isLoading ? (
          <p className="text-sm text-muted">Loading upcoming group sessions...</p>
        ) : sessions.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">
            No upcoming group sessions are currently scheduled for this Service.
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {sessions.map((sess) => (
              <div
                key={sess.id}
                className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-xs"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h4 className="font-semibold text-ink text-base">{sess.title}</h4>
                    {sess.description && (
                      <p className="mt-1 text-sm text-muted line-clamp-2">{sess.description}</p>
                    )}
                  </div>

                  <div>
                    {sess.is_registered_by_me ? (
                      <div className="flex items-center gap-2">
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
                    ) : sess.is_full ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-critical/10 px-2.5 py-0.5 text-xs font-semibold text-critical border border-critical/20">
                        Session Full
                      </span>
                    ) : (
                      <Button
                        className="min-h-8 px-3 py-1 text-xs"
                        onClick={() => handleRegister(sess)}
                        disabled={registeringId === sess.id}
                      >
                        {registeringId === sess.id ? "Registering..." : "Register"}
                      </Button>
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

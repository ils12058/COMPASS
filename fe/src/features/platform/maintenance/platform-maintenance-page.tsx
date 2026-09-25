"use client";

import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  PlatformConfirmation,
  usePlatformAction,
} from "@/features/platform/platform-actions";
import {
  PlatformPageHeader,
  PlatformQueryError,
  PlatformRowsSkeleton,
  PlatformTimestamp,
} from "@/features/platform/platform-presentation";
import { hasPlatformManage } from "@/features/platform/platform-gate";
import {
  initialScheduleDraft,
  ManualMaintenanceForm,
  MaintenanceScheduleForm,
  type MaintenanceDraft,
  type ScheduleDraft,
} from "@/features/platform/maintenance/maintenance-controls";
import {
  formatLocalDateTime,
  localDateTimeToIso,
} from "@/features/platform/maintenance/maintenance-time";
import { refreshMaintenanceQueries } from "@/features/platform/maintenance/maintenance-queries";
import { usePortalSession } from "@/features/portal/components/portal-session";
import type { MaintenanceResponse } from "@/lib/api/generated/model";
import {
  usePlatformOperationsCancelMaintenanceSchedule,
  usePlatformOperationsDisableMaintenance,
  usePlatformOperationsEnableMaintenance,
  usePlatformOperationsGetMaintenance,
  usePlatformOperationsScheduleMaintenance,
} from "@/lib/api/generated/platform-operations/platform-operations";

type Confirmation = "enable" | "disable" | "schedule" | "cancel";

const emptyManualDraft: MaintenanceDraft = { message: "", expectedEnd: "" };
const emptyScheduleDraft: ScheduleDraft = {
  message: "",
  startsAt: "",
  endsAt: "",
};

function effectiveStateLabel(maintenance: MaintenanceResponse): string {
  if (maintenance.state === "NORMAL") return "Operational";
  if (maintenance.state === "SCHEDULED") return "Maintenance scheduled";
  if (maintenance.state === "MAINTENANCE") {
    return maintenance.source === "MANUAL"
      ? "Manual maintenance active"
      : maintenance.source === "SCHEDULED"
        ? "Scheduled maintenance active"
        : "Maintenance active";
  }
  return "State unavailable";
}

function stateTone(maintenance: MaintenanceResponse): string {
  if (maintenance.state === "NORMAL") {
    return "border-success/30 bg-success/10 text-success";
  }
  if (maintenance.state === "SCHEDULED") {
    return "border-info/30 bg-info/5 text-info";
  }
  if (maintenance.state === "MAINTENANCE") {
    return "border-warning/30 bg-warning/10 text-warning";
  }
  return "border-border bg-surface-muted text-muted";
}

function isKnownState(maintenance: MaintenanceResponse): boolean {
  return ["NORMAL", "SCHEDULED", "MAINTENANCE"].includes(maintenance.state);
}

export function PlatformMaintenancePage() {
  const { user } = usePortalSession();
  const canManage = hasPlatformManage(user);
  const queryClient = useQueryClient();
  const maintenanceQuery = usePlatformOperationsGetMaintenance({
    query: { retry: false, staleTime: 15_000 },
  });
  const enable = usePlatformOperationsEnableMaintenance();
  const disable = usePlatformOperationsDisableMaintenance();
  const schedule = usePlatformOperationsScheduleMaintenance();
  const cancelSchedule = usePlatformOperationsCancelMaintenanceSchedule();
  const action = usePlatformAction();
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [manualDraft, setManualDraft] = useState(emptyManualDraft);
  const [scheduleDraft, setScheduleDraft] = useState(emptyScheduleDraft);
  const [manualFormError, setManualFormError] = useState<string | null>(null);
  const [scheduleFormError, setScheduleFormError] = useState<string | null>(null);
  const [editingSchedule, setEditingSchedule] = useState(false);
  const result = maintenanceQuery.data?.data;
  const pending =
    enable.isPending ||
    disable.isPending ||
    schedule.isPending ||
    cancelSchedule.isPending;

  function submitManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setManualFormError(null);
    if (!manualDraft.message.trim()) {
      setManualFormError("Enter the message that will be shown to COMPASS users.");
      return;
    }
    if (manualDraft.expectedEnd) {
      const expectedEnd = localDateTimeToIso(manualDraft.expectedEnd);
      if (!expectedEnd || new Date(expectedEnd).getTime() <= Date.now()) {
        setManualFormError("Choose a future expected end time or clear the field.");
        return;
      }
    }
    setConfirmation("enable");
  }

  function submitSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setScheduleFormError(null);
    if (!scheduleDraft.message.trim()) {
      setScheduleFormError("Enter the message that will be shown to COMPASS users.");
      return;
    }
    const startsAt = localDateTimeToIso(scheduleDraft.startsAt);
    const endsAt = localDateTimeToIso(scheduleDraft.endsAt);
    if (!startsAt || !endsAt) {
      setScheduleFormError("Enter both the start and end times.");
      return;
    }
    if (new Date(startsAt).getTime() <= Date.now()) {
      setScheduleFormError("The maintenance schedule must start in the future.");
      return;
    }
    if (new Date(endsAt).getTime() <= new Date(startsAt).getTime()) {
      setScheduleFormError("The end time must be after the start time.");
      return;
    }
    setConfirmation("schedule");
  }

  async function confirmAction() {
    if (!confirmation || !result) return;

    if (confirmation === "enable") {
      const expectedEnd = manualDraft.expectedEnd
        ? localDateTimeToIso(manualDraft.expectedEnd)
        : undefined;
      if (
        manualDraft.expectedEnd &&
        (!expectedEnd || new Date(expectedEnd).getTime() <= Date.now())
      ) {
        setManualFormError("Choose a future expected end time or clear the field.");
        setConfirmation(null);
        return;
      }
      const success = await action.run(
        () =>
          enable.mutateAsync({
            data: {
              message: manualDraft.message,
              ...(expectedEnd ? { expected_end_at: expectedEnd } : {}),
            },
          }),
        "Maintenance Mode could not be enabled.",
        () => setConfirmation(null),
      );
      if (!success) return;
      setConfirmation(null);
      setManualDraft(emptyManualDraft);
      action.setNotice("Maintenance Mode is active.");
      refreshMaintenanceQueries(queryClient);
      return;
    }

    if (confirmation === "disable") {
      const success = await action.run(
        () => disable.mutateAsync(),
        "Manual Maintenance Mode could not be ended.",
        () => setConfirmation(null),
      );
      if (!success) return;
      setConfirmation(null);
      action.setNotice("Manual Maintenance Mode has ended.");
      refreshMaintenanceQueries(queryClient);
      return;
    }

    if (confirmation === "schedule") {
      const startsAt = localDateTimeToIso(scheduleDraft.startsAt);
      const endsAt = localDateTimeToIso(scheduleDraft.endsAt);
      if (
        !startsAt ||
        !endsAt ||
        new Date(startsAt).getTime() <= Date.now() ||
        new Date(endsAt).getTime() <= new Date(startsAt).getTime()
      ) {
        setScheduleFormError(
          "Review the schedule: start must be in the future and end must be after start.",
        );
        setConfirmation(null);
        return;
      }
      const success = await action.run(
        () =>
          schedule.mutateAsync({
            data: {
              message: scheduleDraft.message,
              starts_at: startsAt,
              ends_at: endsAt,
            },
          }),
        "The maintenance schedule could not be saved.",
        () => setConfirmation(null),
      );
      if (!success) return;
      setConfirmation(null);
      setEditingSchedule(false);
      setScheduleDraft(emptyScheduleDraft);
      action.setNotice("The maintenance schedule has been saved.");
      refreshMaintenanceQueries(queryClient);
      return;
    }

    const success = await action.run(
      () => cancelSchedule.mutateAsync(),
      "The maintenance schedule could not be cancelled.",
      () => setConfirmation(null),
    );
    if (!success) return;
    setConfirmation(null);
    setEditingSchedule(false);
    action.setNotice("The maintenance schedule has been cancelled.");
    refreshMaintenanceQueries(queryClient);
  }

  function confirmationCopy() {
    if (confirmation === "enable") {
      return (
        <>
          <p>
            Enable Maintenance Mode? Normal application APIs may become
            unavailable. Manual Maintenance Mode remains active until explicitly
            disabled; the expected end does not turn it off automatically.
          </p>
          <p className="font-medium text-ink">Public message</p>
          <p className="whitespace-pre-wrap break-words">{manualDraft.message}</p>
          {manualDraft.expectedEnd ? (
            <p>
              Expected end: {formatLocalDateTime(manualDraft.expectedEnd)}
              {" "}(informational only)
            </p>
          ) : null}
        </>
      );
    }
    if (confirmation === "disable") {
      return (
        <p>
          End manual Maintenance Mode? Normal API access will resume after the
          server confirms this operation.
        </p>
      );
    }
    if (confirmation === "schedule") {
      return (
        <>
          <p>
            {result?.schedule_upcoming
              ? "Replace the upcoming maintenance schedule?"
              : "Schedule Maintenance Mode for this future window?"}{" "}
            The server will apply the configured time window.
          </p>
          <p className="font-medium text-ink">Public message</p>
          <p className="whitespace-pre-wrap break-words">{scheduleDraft.message}</p>
          <p>
            Starts: {formatLocalDateTime(scheduleDraft.startsAt)}
            <br />
            Ends: {formatLocalDateTime(scheduleDraft.endsAt)}
          </p>
        </>
      );
    }
    if (result?.schedule_active) {
      return (
        <p>
          Cancel the active scheduled window? Maintenance Mode will end
          immediately after the server confirms the cancellation.
        </p>
      );
    }
    return (
      <p>
        Cancel the upcoming scheduled window? Maintenance Mode will not start
        during that window.
      </p>
    );
  }

  const isUpcomingSchedule =
    Boolean(result?.schedule_upcoming) && !result?.schedule_active;
  const canCancelSchedule =
    Boolean(result?.schedule_upcoming) || Boolean(result?.schedule_active);

  return (
    <section>
      <PlatformPageHeader
        title="Maintenance"
        description="Review public status and administer manual or scheduled Maintenance Mode."
      />

      {maintenanceQuery.isPending ? <PlatformRowsSkeleton rows={3} /> : null}
      {maintenanceQuery.isError && !result ? (
        <PlatformQueryError
          message="Maintenance status could not be loaded."
          onRetry={() => void maintenanceQuery.refetch()}
        />
      ) : null}

      {result ? (
        <>
          <section aria-labelledby="maintenance-current-heading">
            <h2 id="maintenance-current-heading" className="sr-only">
              Current Maintenance Mode status
            </h2>
            <dl className="grid gap-4 border-y border-border py-5 sm:grid-cols-[minmax(9rem,0.35fr)_minmax(0,1fr)]">
              <dt className="text-sm font-semibold text-muted">Effective state</dt>
              <dd>
                <span
                  className={`inline-flex min-h-8 items-center rounded-md border px-3 text-sm font-semibold ${stateTone(result)}`}
                >
                  {effectiveStateLabel(result)}
                </span>
                {result.source === "MANUAL" || result.source === "SCHEDULED" ? (
                  <p className="mt-1 text-xs text-muted">
                    Source: {result.source === "MANUAL" ? "Manual" : "Scheduled"}
                  </p>
                ) : null}
              </dd>
              {result.state !== "NORMAL" ? (
                <>
                  <dt className="text-sm font-semibold text-muted">
                    Public message
                  </dt>
                  <dd className="whitespace-pre-wrap break-words text-sm leading-6 text-ink">
                    {result.message}
                  </dd>
                </>
              ) : null}
              {result.state === "SCHEDULED" || result.schedule_active ? (
                <>
                  <dt className="text-sm font-semibold text-muted">Starts</dt>
                  <dd className="text-sm text-ink">
                    <PlatformTimestamp value={result.scheduled_start_at} />
                  </dd>
                  <dt className="text-sm font-semibold text-muted">
                    {result.schedule_active ? "Scheduled end" : "Ends"}
                  </dt>
                  <dd className="text-sm text-ink">
                    <PlatformTimestamp value={result.scheduled_end_at} />
                  </dd>
                </>
              ) : null}
              {result.state === "MAINTENANCE" &&
              result.source === "MANUAL" &&
              result.manual_expected_end_at ? (
                <>
                  <dt className="text-sm font-semibold text-muted">Expected end</dt>
                  <dd className="text-sm text-ink">
                    <PlatformTimestamp value={result.manual_expected_end_at} />
                    <p className="mt-1 text-xs text-muted">
                      Informational only; Maintenance Mode remains active until
                      explicitly disabled.
                    </p>
                  </dd>
                </>
              ) : null}
            </dl>
          </section>

          {action.notice ? (
            <p role="status" className="mt-5 text-sm text-success">
              {action.notice}
            </p>
          ) : null}

          {canManage ? (
            <section className="mt-8" aria-labelledby="maintenance-controls-heading">
              <h2
                id="maintenance-controls-heading"
                className="font-heading text-xl font-semibold text-ink"
              >
                Maintenance controls
              </h2>

              {result.state === "NORMAL" ? (
                <>
                  <ManualMaintenanceForm
                    draft={manualDraft}
                    error={manualFormError}
                    pending={pending}
                    onChange={(draft) => {
                      setManualDraft(draft);
                      setManualFormError(null);
                    }}
                    onSubmit={submitManual}
                  />
                  <MaintenanceScheduleForm
                    existing={null}
                    open
                    draft={scheduleDraft}
                    error={scheduleFormError}
                    pending={pending}
                    onOpen={() => setEditingSchedule(true)}
                    onClose={() => setEditingSchedule(false)}
                    onChange={(draft) => {
                      setScheduleDraft(draft);
                      setScheduleFormError(null);
                    }}
                    onSubmit={submitSchedule}
                  />
                </>
              ) : null}

              {isUpcomingSchedule ? (
                <MaintenanceScheduleForm
                  existing={result}
                  open={editingSchedule}
                  draft={scheduleDraft}
                  error={scheduleFormError}
                  pending={pending}
                  onOpen={() => {
                    setScheduleDraft(initialScheduleDraft(result));
                    setScheduleFormError(null);
                    setEditingSchedule(true);
                  }}
                  onClose={() => {
                    setEditingSchedule(false);
                    setScheduleFormError(null);
                  }}
                  onChange={(draft) => {
                    setScheduleDraft(draft);
                    setScheduleFormError(null);
                  }}
                  onSubmit={submitSchedule}
                />
              ) : null}

              {result.state === "MAINTENANCE" && result.source === "MANUAL" ? (
                <section className="border-t border-border py-6">
                  <h3 className="font-heading text-lg font-semibold text-ink">
                    Manual Maintenance Mode is active
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    It remains active until an operator explicitly ends it.
                  </p>
                  <Button
                    className="mt-4"
                    variant="danger"
                    disabled={pending}
                    onClick={() => {
                      action.setError(null);
                      setConfirmation("disable");
                    }}
                  >
                    End Maintenance Mode
                  </Button>
                </section>
              ) : null}

              {canCancelSchedule ? (
                <section className="border-t border-border py-6">
                  <h3 className="font-heading text-lg font-semibold text-ink">
                    {result.schedule_active
                      ? "Scheduled Maintenance Mode is active"
                      : "Upcoming maintenance is scheduled"}
                  </h3>
                  <Button
                    className="mt-4"
                    variant="danger"
                    disabled={pending}
                    onClick={() => {
                      action.setError(null);
                      setConfirmation("cancel");
                    }}
                  >
                    Cancel scheduled maintenance
                  </Button>
                </section>
              ) : null}

              {!isKnownState(result) ? (
                <p className="mt-5 border-t border-border pt-5 text-sm text-muted">
                  No management actions are available for the current state.
                </p>
              ) : null}
            </section>
          ) : null}

          {action.stepUpDialog}
          <PlatformConfirmation
            open={confirmation !== null}
            title={
              confirmation === "enable"
                ? "Enable Maintenance Mode?"
                : confirmation === "disable"
                  ? "End Maintenance Mode?"
                  : confirmation === "schedule"
                    ? "Confirm maintenance schedule"
                    : result.schedule_active
                      ? "Cancel the active scheduled window?"
                      : "Cancel scheduled maintenance?"
            }
            confirmLabel={
              confirmation === "enable"
                ? "Enable Maintenance Mode"
                : confirmation === "disable"
                  ? "End Maintenance Mode"
                  : confirmation === "schedule"
                    ? result.schedule_upcoming
                      ? "Change schedule"
                      : "Schedule maintenance"
                    : "Cancel schedule"
            }
            cancelLabel={confirmation === "cancel" ? "Keep schedule" : "Cancel"}
            pendingLabel={
              confirmation === "enable"
                ? "Enabling…"
                : confirmation === "disable"
                  ? "Ending…"
                  : confirmation === "schedule"
                    ? "Saving schedule…"
                    : "Cancelling…"
            }
            pending={pending}
            error={action.error}
            variant={
              confirmation === "disable" || confirmation === "cancel"
                ? "danger"
                : "primary"
            }
            onOpenChange={(open) => {
              if (!open && !pending) {
                setConfirmation(null);
                action.setError(null);
              }
            }}
            onConfirm={() => void confirmAction()}
          >
            {confirmationCopy()}
          </PlatformConfirmation>
        </>
      ) : null}
    </section>
  );
}

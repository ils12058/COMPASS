"use client";

import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { MaintenanceResponse } from "@/lib/api/generated/model";
import {
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateTimeInputValue,
  isoToInstitutionalDateTimeInput,
} from "@/lib/institutional-time";

export type MaintenanceDraft = {
  message: string;
  expectedEnd: string;
};

export type ScheduleDraft = {
  message: string;
  startsAt: string;
  endsAt: string;
};

export function ManualMaintenanceForm({
  draft,
  error,
  pending,
  onChange,
  onSubmit,
}: {
  draft: MaintenanceDraft;
  error: string | null;
  pending: boolean;
  onChange: (draft: MaintenanceDraft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="border-t border-border py-6">
      <h2 className="font-heading text-xl font-semibold text-ink">
        Enable Maintenance Mode
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
        The public message may be shown to COMPASS users. Do not include internal
        or sensitive information. Manual Maintenance Mode remains active until
        explicitly disabled.
      </p>
      <form className="mt-5 max-w-2xl space-y-5" onSubmit={onSubmit}>
        <div className="grid gap-2">
          <Label htmlFor="manual-maintenance-message">Public message</Label>
          <Textarea
            id="manual-maintenance-message"
            required
            value={draft.message}
            onChange={(event) =>
              onChange({ ...draft, message: event.target.value })
            }
            aria-describedby="manual-maintenance-message-help"
          />
          <p id="manual-maintenance-message-help" className="text-xs leading-5 text-muted">
            This text is public and will be displayed as plain text.
          </p>
        </div>
        <div className="grid max-w-sm gap-2">
          <Label htmlFor="manual-maintenance-expected-end">Expected end (optional)</Label>
          <Input
            id="manual-maintenance-expected-end"
            type="datetime-local"
            min={institutionalDateTimeInputValue()}
            value={draft.expectedEnd}
            aria-describedby="manual-maintenance-timezone-help"
            onChange={(event) =>
              onChange({ ...draft, expectedEnd: event.target.value })
            }
          />
          <p
            id="manual-maintenance-timezone-help"
            className="text-xs leading-5 text-muted"
          >
            Times use {INSTITUTION_TIME_ZONE_LABEL}. Expected end is
            informational; it does not automatically disable Maintenance Mode.
          </p>
        </div>
        {error ? (
          <p role="alert" className="text-sm text-danger">{error}</p>
        ) : null}
        <Button type="submit" disabled={pending}>
          Enable Maintenance Mode
        </Button>
      </form>
    </section>
  );
}

export function MaintenanceScheduleForm({
  existing,
  open,
  draft,
  error,
  pending,
  onOpen,
  onClose,
  onChange,
  onSubmit,
}: {
  existing: MaintenanceResponse | null;
  open: boolean;
  draft: ScheduleDraft;
  error: string | null;
  pending: boolean;
  onOpen: () => void;
  onClose: () => void;
  onChange: (draft: ScheduleDraft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  if (existing && !open) {
    return (
      <section className="border-t border-border py-6">
        <h2 className="font-heading text-xl font-semibold text-ink">
          Upcoming maintenance
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Change the configured window or cancel it. The schedule uses
          {INSTITUTION_TIME_ZONE_LABEL}.
        </p>
        <Button className="mt-4" variant="secondary" onClick={onOpen}>
          Change schedule
        </Button>
      </section>
    );
  }

  return (
    <section className="border-t border-border py-6">
      <h2 className="font-heading text-xl font-semibold text-ink">
        {existing ? "Change maintenance schedule" : "Schedule maintenance"}
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
        The message may be shown publicly. Maintenance becomes effective during
        the configured window in {INSTITUTION_TIME_ZONE_LABEL}; no browser action
        is required.
        {existing ? " Saving replaces the upcoming schedule." : ""}
      </p>
      <form className="mt-5 max-w-2xl space-y-5" onSubmit={onSubmit}>
        <div className="grid gap-2">
          <Label htmlFor="scheduled-maintenance-message">Public message</Label>
          <Textarea
            id="scheduled-maintenance-message"
            required
            value={draft.message}
            onChange={(event) =>
              onChange({ ...draft, message: event.target.value })
            }
            aria-describedby="scheduled-maintenance-message-help"
          />
          <p id="scheduled-maintenance-message-help" className="text-xs leading-5 text-muted">
            Do not include internal or sensitive information. The message is
            rendered as plain text.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="scheduled-maintenance-start">Starts at</Label>
            <Input
              id="scheduled-maintenance-start"
              type="datetime-local"
              min={institutionalDateTimeInputValue()}
              required
              value={draft.startsAt}
              aria-describedby="scheduled-maintenance-timezone-help"
              onChange={(event) =>
                onChange({ ...draft, startsAt: event.target.value })
              }
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="scheduled-maintenance-end">Ends at</Label>
            <Input
              id="scheduled-maintenance-end"
              type="datetime-local"
              min={draft.startsAt || institutionalDateTimeInputValue()}
              required
              value={draft.endsAt}
              aria-describedby="scheduled-maintenance-timezone-help"
              onChange={(event) =>
                onChange({ ...draft, endsAt: event.target.value })
              }
            />
          </div>
        </div>
        <p
          id="scheduled-maintenance-timezone-help"
          className="text-xs leading-5 text-muted"
        >
          Times use {INSTITUTION_TIME_ZONE_LABEL}.
        </p>
        {error ? (
          <p role="alert" className="text-sm text-danger">{error}</p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={pending}>
            {existing ? "Change schedule" : "Schedule maintenance"}
          </Button>
          {existing ? (
            <Button
              type="button"
              variant="secondary"
              disabled={pending}
              onClick={onClose}
            >
              Stop editing
            </Button>
          ) : null}
        </div>
      </form>
    </section>
  );
}

export function initialScheduleDraft(
  maintenance: MaintenanceResponse,
): ScheduleDraft {
  return {
    message: maintenance.message,
    startsAt: isoToInstitutionalDateTimeInput(maintenance.scheduled_start_at),
    endsAt: isoToInstitutionalDateTimeInput(maintenance.scheduled_end_at),
  };
}

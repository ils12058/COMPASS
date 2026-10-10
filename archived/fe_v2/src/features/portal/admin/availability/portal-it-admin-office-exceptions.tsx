"use client";

import { FormEvent, useState } from "react";
import { CalendarDays, LoaderCircle, Plus, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  AvailabilityModeScope,
  ExceptionCreateRequest,
} from "@/lib/api/generated/model";
import { AvailabilityModeScope as AvailabilityModeScopeValues } from "@/lib/api/generated/model";
import {
  getAvailabilityListOfficeExceptionsQueryKey,
  useAvailabilityCreateOfficeException,
  useAvailabilityListOfficeExceptions,
  useAvailabilityRemoveOfficeException,
} from "@/lib/api/generated/availability/availability";
import {
  AvailabilityActionMessage,
  AvailabilityEmptyState,
  AvailabilityListSkeleton,
  AvailabilityManagementRequired,
  AvailabilityQueryError,
  AvailabilitySection,
  availabilityAdminError,
  availabilitySelectClassName,
  formatAvailabilityDateTime,
  formatAvailabilityValue,
  toDateTimeIso,
} from "@/features/portal/admin/availability/portal-it-admin-availability-shared";

const EMPTY_FORM = {
  endsAt: "",
  modeScope: AvailabilityModeScopeValues.ALL as AvailabilityModeScope,
  reason: "",
  startsAt: "",
};

export function PortalItAdminOfficeExceptions({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const exceptionsQuery = useAvailabilityListOfficeExceptions({
    query: {
      enabled: canManage,
      retry: false,
      staleTime: 30_000,
    },
  });
  const createException = useAvailabilityCreateOfficeException();
  const removeException = useAvailabilityRemoveOfficeException();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const startsAt = new Date(form.startsAt);
    const endsAt = new Date(form.endsAt);
    if (
      Number.isNaN(startsAt.getTime()) ||
      Number.isNaN(endsAt.getTime()) ||
      startsAt >= endsAt
    ) {
      setError("Choose an end time after the start time.");
      return;
    }

    const data: ExceptionCreateRequest = {
      ends_at: toDateTimeIso(form.endsAt),
      mode_scope: form.modeScope,
      reason: form.reason.trim(),
      starts_at: toDateTimeIso(form.startsAt),
    };

    try {
      await createException.mutateAsync({ data });
      setForm(EMPTY_FORM);
      setMessage("Office exception added.");
      await queryClient.invalidateQueries({
        queryKey: getAvailabilityListOfficeExceptionsQueryKey(),
      });
    } catch (caught) {
      setError(availabilityAdminError(caught, "We couldn’t add this office exception."));
    }
  }

  async function remove(exceptionId: string) {
    if (!window.confirm("Remove this office exception?")) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      await removeException.mutateAsync({ exceptionId });
      setMessage("Office exception removed.");
      await queryClient.invalidateQueries({
        queryKey: getAvailabilityListOfficeExceptionsQueryKey(),
      });
    } catch (caught) {
      setError(availabilityAdminError(caught, "We couldn’t remove this office exception."));
    }
  }

  const exceptions = exceptionsQuery.data?.data.items ?? [];

  return (
    <AvailabilitySection
      icon={CalendarDays}
      title="Office exceptions"
      description="Record closures or temporary changes that override the recurring office schedule."
    >
      {!canManage ? (
        <AvailabilityManagementRequired />
      ) : exceptionsQuery.isPending ? (
        <AvailabilityListSkeleton label="Loading office exceptions" />
      ) : exceptionsQuery.isError ? (
        <AvailabilityQueryError onRetry={() => void exceptionsQuery.refetch()} />
      ) : (
        <div className="space-y-6">
          <AvailabilityActionMessage error={error} message={message} />
          <form
            className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:p-5"
            onSubmit={submit}
          >
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-card text-[var(--compass-brand-maroon)]">
                <Plus aria-hidden="true" className="size-4" />
              </span>
              <div>
                <h3 className="font-semibold">Add an exception</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Use local date and time for a closure or temporary unavailability.
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="office-exception-start">Starts</Label>
                <Input
                  id="office-exception-start"
                  className="mt-2 h-10"
                  required
                  type="datetime-local"
                  value={form.startsAt}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, startsAt: event.target.value }))
                  }
                />
              </div>
              <div>
                <Label htmlFor="office-exception-end">Ends</Label>
                <Input
                  id="office-exception-end"
                  className="mt-2 h-10"
                  required
                  type="datetime-local"
                  value={form.endsAt}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, endsAt: event.target.value }))
                  }
                />
              </div>
              <div>
                <Label htmlFor="office-exception-scope">Applies to</Label>
                <select
                  id="office-exception-scope"
                  className={`${availabilitySelectClassName} mt-2`}
                  value={form.modeScope}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      modeScope: event.target.value as AvailabilityModeScope,
                    }))
                  }
                >
                  {Object.values(AvailabilityModeScopeValues).map((scope) => (
                    <option key={scope} value={scope}>
                      {formatAvailabilityValue(scope)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="office-exception-reason">Reason</Label>
                <Input
                  id="office-exception-reason"
                  className="mt-2 h-10"
                  maxLength={255}
                  placeholder="Optional note"
                  value={form.reason}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, reason: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button disabled={createException.isPending} type="submit">
                {createException.isPending ? (
                  <LoaderCircle aria-hidden="true" className="animate-spin" />
                ) : null}
                {createException.isPending ? "Adding…" : "Add exception"}
              </Button>
            </div>
          </form>

          {exceptions.length ? (
            <div className="space-y-3">
              {exceptions.map((exception) => (
                <div
                  key={exception.id}
                  className="flex flex-col gap-4 rounded-2xl border border-[var(--compass-border)] p-4 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold">
                        {formatAvailabilityDateTime(exception.starts_at)} – {formatAvailabilityDateTime(exception.ends_at)}
                      </p>
                      <span className="rounded-full bg-[var(--compass-brand-maroon)]/10 px-2.5 py-1 text-xs font-bold text-[var(--compass-brand-maroon)]">
                        {formatAvailabilityValue(exception.mode_scope)}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {exception.reason || "No reason was added."}
                    </p>
                  </div>
                  <Button
                    className="shrink-0 self-start"
                    disabled={removeException.isPending}
                    type="button"
                    variant="ghost"
                    onClick={() => void remove(exception.id)}
                  >
                    <Trash2 aria-hidden="true" />
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <AvailabilityEmptyState
              description="There are no office closures or temporary changes recorded."
              title="No office exceptions"
            />
          )}
        </div>
      )}
    </AvailabilitySection>
  );
}

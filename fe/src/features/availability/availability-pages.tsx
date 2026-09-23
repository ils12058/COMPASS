"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AvailabilityPageHeading,
  AvailabilityQueryError,
  AvailabilityRouteUnavailable,
  AvailabilitySectionSkeleton,
  AvailabilityStatusBadge,
  canManageAvailability,
  canUseSelfAvailability,
  useAvailabilityAction,
  type StepUpHooks,
} from "@/features/availability/availability-shared";
import { EffectiveAvailabilityPreview } from "@/features/availability/effective-availability-preview";
import { UnavailabilitySection } from "@/features/availability/unavailability-section";
import { WeeklyScheduleEditor } from "@/features/availability/weekly-schedule-editor";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  type AvailabilityProviderSummary,
  type ExceptionCreateRequest,
  type WeeklyWindowRequest,
} from "@/lib/api/generated/model";
import {
  useAvailabilityCreateMyException,
  useAvailabilityCreateOfficeException,
  useAvailabilityCreateProviderException,
  useAvailabilityGetMyWeekly,
  useAvailabilityGetOfficeWeekly,
  useAvailabilityGetProviderWeekly,
  useAvailabilityListMyExceptions,
  useAvailabilityListOfficeExceptions,
  useAvailabilityListProviderExceptions,
  useAvailabilityListProviders,
  useAvailabilityRemoveMyException,
  useAvailabilityRemoveOfficeException,
  useAvailabilityRemoveProviderException,
  useAvailabilityReplaceMyWeekly,
  useAvailabilityReplaceOfficeWeekly,
  useAvailabilityReplaceProviderWeekly,
} from "@/lib/api/generated/availability/availability";

export function MyAvailabilityPage() {
  const { user } = usePortalSession();
  const allowed = canUseSelfAvailability(user);
  const canMutate =
    user.capabilities.includes("availability.manage_self") ||
    user.capabilities.includes("availability.manage");

  const weekly = useAvailabilityGetMyWeekly({
    query: { enabled: allowed, retry: false },
  });
  const exceptions = useAvailabilityListMyExceptions({
    query: { enabled: allowed, retry: false },
  });
  const replaceWeekly = useAvailabilityReplaceMyWeekly();
  const createException = useAvailabilityCreateMyException();
  const removeException = useAvailabilityRemoveMyException();
  const weeklyAction = useAvailabilityAction();
  const exceptionAction = useAvailabilityAction();
  const [previewRefresh, setPreviewRefresh] = useState(0);

  if (!allowed) return <AvailabilityRouteUnavailable />;

  async function saveWeekly(
    windows: WeeklyWindowRequest[],
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await weeklyAction.run(
      () => replaceWeekly.mutateAsync({ data: { windows } }),
      "Your weekly Availability could not be saved.",
      hooks,
    );
    if (!response) return false;
    weeklyAction.setNotice("Weekly Availability saved.");
    await weekly.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  async function addException(
    payload: ExceptionCreateRequest,
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await exceptionAction.run(
      () => createException.mutateAsync({ data: payload }),
      "Your unavailability could not be added.",
      hooks,
    );
    if (!response) return false;
    exceptionAction.setNotice("Unavailability added.");
    await exceptions.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  async function removeExceptionById(
    exceptionId: string,
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await exceptionAction.run(
      () => removeException.mutateAsync({ exceptionId }),
      "Your unavailability could not be removed.",
      hooks,
    );
    if (!response) return false;
    exceptionAction.setNotice("Unavailability removed.");
    await exceptions.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  return (
    <section>
      <AvailabilityPageHeading title="My availability" />

      <div className="mt-9">
        {weekly.isPending ? (
          <AvailabilitySectionSkeleton label="Loading weekly Availability…" />
        ) : weekly.isError ? (
          <AvailabilityQueryError
            error={weekly.error}
            fallback="Your weekly Availability could not be loaded."
            onRetry={() => void weekly.refetch()}
          />
        ) : (
          <WeeklyScheduleEditor
            key={weekly.data.data.windows.map((window) => window.id).join("|")}
            windows={weekly.data.data.windows}
            canMutate={canMutate}
            pending={replaceWeekly.isPending}
            error={weeklyAction.error}
            notice={weeklyAction.notice}
            onSave={saveWeekly}
          />
        )}
      </div>

      <div className="mt-12 border-t border-border pt-10">
        {exceptions.isPending ? (
          <AvailabilitySectionSkeleton label="Loading unavailability…" />
        ) : exceptions.isError ? (
          <AvailabilityQueryError
            error={exceptions.error}
            fallback="Your unavailability could not be loaded."
            onRetry={() => void exceptions.refetch()}
          />
        ) : (
          <UnavailabilitySection
            items={exceptions.data.data.items}
            canCreate={canMutate}
            canRemove={canMutate}
            administrative={false}
            createPending={createException.isPending}
            removePending={removeException.isPending}
            error={exceptionAction.error}
            notice={exceptionAction.notice}
            onCreate={addException}
            onRemove={removeExceptionById}
          />
        )}
      </div>

      <div className="mt-12 border-t border-border pt-10">
        <EffectiveAvailabilityPreview
          providerId={user.id}
          refreshToken={previewRefresh}
        />
      </div>

      {weeklyAction.stepUpDialog}
      {exceptionAction.stepUpDialog}
    </section>
  );
}

export function OfficeAvailabilityPage() {
  const { user } = usePortalSession();
  const allowed = canManageAvailability(user);

  const weekly = useAvailabilityGetOfficeWeekly({
    query: { enabled: allowed, retry: false },
  });
  const exceptions = useAvailabilityListOfficeExceptions({
    query: { enabled: allowed, retry: false },
  });
  const replaceWeekly = useAvailabilityReplaceOfficeWeekly();
  const createException = useAvailabilityCreateOfficeException();
  const removeException = useAvailabilityRemoveOfficeException();
  const weeklyAction = useAvailabilityAction();
  const exceptionAction = useAvailabilityAction();

  if (!allowed) return <AvailabilityRouteUnavailable management />;

  async function saveWeekly(
    windows: WeeklyWindowRequest[],
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await weeklyAction.run(
      () => replaceWeekly.mutateAsync({ data: { windows } }),
      "Office weekly Availability could not be saved.",
      { administrative: true, ...hooks },
    );
    if (!response) return false;
    weeklyAction.setNotice("Office weekly Availability saved.");
    await weekly.refetch();
    return true;
  }

  async function addException(
    payload: ExceptionCreateRequest,
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await exceptionAction.run(
      () => createException.mutateAsync({ data: payload }),
      "Office unavailability could not be added.",
      { administrative: true, ...hooks },
    );
    if (!response) return false;
    exceptionAction.setNotice("Office unavailability added.");
    await exceptions.refetch();
    return true;
  }

  async function removeExceptionById(
    exceptionId: string,
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await exceptionAction.run(
      () => removeException.mutateAsync({ exceptionId }),
      "Office unavailability could not be removed.",
      { administrative: true, ...hooks },
    );
    if (!response) return false;
    exceptionAction.setNotice("Office unavailability removed.");
    await exceptions.refetch();
    return true;
  }

  return (
    <section>
      <AvailabilityPageHeading
        title="Office availability"
        description="Office availability defines the operating windows within which provider availability can become effective."
      />

      <div className="mt-9">
        {weekly.isPending ? (
          <AvailabilitySectionSkeleton label="Loading Office weekly Availability…" />
        ) : weekly.isError ? (
          <AvailabilityQueryError
            error={weekly.error}
            fallback="Office weekly Availability could not be loaded."
            onRetry={() => void weekly.refetch()}
          />
        ) : (
          <WeeklyScheduleEditor
            key={weekly.data.data.windows.map((window) => window.id).join("|")}
            windows={weekly.data.data.windows}
            canMutate
            pending={replaceWeekly.isPending}
            error={weeklyAction.error}
            notice={weeklyAction.notice}
            onSave={saveWeekly}
          />
        )}
      </div>

      <div className="mt-12 border-t border-border pt-10">
        {exceptions.isPending ? (
          <AvailabilitySectionSkeleton label="Loading Office unavailability…" />
        ) : exceptions.isError ? (
          <AvailabilityQueryError
            error={exceptions.error}
            fallback="Office unavailability could not be loaded."
            onRetry={() => void exceptions.refetch()}
          />
        ) : (
          <UnavailabilitySection
            items={exceptions.data.data.items}
            canCreate
            canRemove
            administrative
            createPending={createException.isPending}
            removePending={removeException.isPending}
            error={exceptionAction.error}
            notice={exceptionAction.notice}
            onCreate={addException}
            onRemove={removeExceptionById}
          />
        )}
      </div>

      {weeklyAction.stepUpDialog}
      {exceptionAction.stepUpDialog}
    </section>
  );
}

function ProviderWorkspace({
  provider,
  onBack,
}: {
  provider: AvailabilityProviderSummary;
  onBack: () => void;
}) {
  const { user } = usePortalSession();
  const operational =
    provider.role === "COUNSELOR" && provider.is_active;
  const legacy = provider.role === "GUIDANCE_SERVICES_STAFF";
  const canPreview =
    operational && user.capabilities.includes("availability.view");

  const weekly = useAvailabilityGetProviderWeekly(provider.id, {
    query: { retry: false },
  });
  const exceptions = useAvailabilityListProviderExceptions(provider.id, {
    query: { retry: false },
  });
  const replaceWeekly = useAvailabilityReplaceProviderWeekly();
  const createException = useAvailabilityCreateProviderException();
  const removeException = useAvailabilityRemoveProviderException();
  const weeklyAction = useAvailabilityAction();
  const exceptionAction = useAvailabilityAction();
  const [previewRefresh, setPreviewRefresh] = useState(0);

  async function saveWeekly(
    windows: WeeklyWindowRequest[],
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await weeklyAction.run(
      () =>
        replaceWeekly.mutateAsync({
          providerId: provider.id,
          data: { windows },
        }),
      "The provider weekly Availability could not be saved.",
      { administrative: true, ...hooks },
    );
    if (!response) return false;
    weeklyAction.setNotice(
      windows.length === 0
        ? "Recurring Availability cleared."
        : "Provider weekly Availability saved.",
    );
    await weekly.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  async function addException(
    payload: ExceptionCreateRequest,
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await exceptionAction.run(
      () =>
        createException.mutateAsync({
          providerId: provider.id,
          data: payload,
        }),
      "The provider unavailability could not be added.",
      { administrative: true, ...hooks },
    );
    if (!response) return false;
    exceptionAction.setNotice("Provider unavailability added.");
    await exceptions.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  async function removeExceptionById(
    exceptionId: string,
    hooks?: StepUpHooks,
  ): Promise<boolean> {
    const response = await exceptionAction.run(
      () =>
        removeException.mutateAsync({
          providerId: provider.id,
          exceptionId,
        }),
      "The provider unavailability could not be removed.",
      { administrative: true, ...hooks },
    );
    if (!response) return false;
    exceptionAction.setNotice("Provider unavailability removed.");
    await exceptions.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  return (
    <section>
      <Button variant="quiet" onClick={onBack}>
        ← Counselors
      </Button>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
            {provider.full_name || provider.email}
          </h1>
          <p className="mt-2 break-all text-sm text-muted">{provider.email}</p>
        </div>
        <AvailabilityStatusBadge
          active={provider.is_active}
          legacy={legacy}
        />
      </div>

      {!operational ? (
        <p className="mt-5 max-w-3xl border-l-2 border-warning pl-4 text-sm leading-6 text-muted">
          {legacy
            ? "This is historical Guidance Services Staff Availability. Existing configuration can be reviewed or removed, but new operational Availability cannot be configured."
            : "This provider is inactive. Existing Availability can be reviewed or removed, but new Availability cannot be configured."}
        </p>
      ) : null}

      <div className="mt-9">
        {weekly.isPending ? (
          <AvailabilitySectionSkeleton label="Loading provider weekly Availability…" />
        ) : weekly.isError ? (
          <AvailabilityQueryError
            error={weekly.error}
            fallback="Provider weekly Availability could not be loaded."
            onRetry={() => void weekly.refetch()}
          />
        ) : (
          <WeeklyScheduleEditor
            key={weekly.data.data.windows.map((window) => window.id).join("|")}
            windows={weekly.data.data.windows}
            canMutate
            cleanupOnly={!operational}
            pending={replaceWeekly.isPending}
            error={weeklyAction.error}
            notice={weeklyAction.notice}
            onSave={saveWeekly}
          />
        )}
      </div>

      <div className="mt-12 border-t border-border pt-10">
        {exceptions.isPending ? (
          <AvailabilitySectionSkeleton label="Loading provider unavailability…" />
        ) : exceptions.isError ? (
          <AvailabilityQueryError
            error={exceptions.error}
            fallback="Provider unavailability could not be loaded."
            onRetry={() => void exceptions.refetch()}
          />
        ) : (
          <UnavailabilitySection
            items={exceptions.data.data.items}
            canCreate={operational}
            canRemove
            administrative
            createPending={createException.isPending}
            removePending={removeException.isPending}
            error={exceptionAction.error}
            notice={exceptionAction.notice}
            onCreate={addException}
            onRemove={removeExceptionById}
          />
        )}
      </div>

      {canPreview ? (
        <div className="mt-12 border-t border-border pt-10">
          <EffectiveAvailabilityPreview
            providerId={provider.id}
            refreshToken={previewRefresh}
          />
        </div>
      ) : null}

      {weeklyAction.stepUpDialog}
      {exceptionAction.stepUpDialog}
    </section>
  );
}

export function ProviderAvailabilityPage() {
  const { user } = usePortalSession();
  const allowed = canManageAvailability(user);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const search = (searchParams.get("search") ?? "").slice(0, 254).trim();
  const requestedPage = Number.parseInt(searchParams.get("page") ?? "1", 10);
  const page =
    Number.isFinite(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const [searchValue, setSearchValue] = useState(search);
  const [selected, setSelected] =
    useState<AvailabilityProviderSummary | null>(null);

  const providers = useAvailabilityListProviders(
    {
      ...(search ? { search } : {}),
      page,
      page_size: 20,
    },
    { query: { enabled: allowed, retry: false } },
  );

  useEffect(() => {
    if (searchValue === search) return;
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams.toString());
      const trimmed = searchValue.trim();
      if (trimmed) next.set("search", trimmed);
      else next.delete("search");
      next.delete("page");
      const query = next.toString();
      router.replace(query ? pathname + "?" + query : pathname, {
        scroll: false,
      });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [pathname, router, search, searchParams, searchValue]);

  if (!allowed) return <AvailabilityRouteUnavailable management />;

  function movePage(nextPage: number) {
    const next = new URLSearchParams(searchParams.toString());
    if (nextPage <= 1) next.delete("page");
    else next.set("page", String(nextPage));
    const query = next.toString();
    router.push(query ? pathname + "?" + query : pathname);
  }

  if (selected) {
    return (
      <ProviderWorkspace
        provider={selected}
        onBack={() => setSelected(null)}
      />
    );
  }

  return (
    <section>
      <AvailabilityPageHeading title="Counselor availability" />

      <div className="mt-8 border-y border-border py-5">
        <Label htmlFor="provider-search">Search Counselors</Label>
        <Input
          id="provider-search"
          className="mt-2 max-w-xl"
          value={searchValue}
          placeholder="Search Counselors by name or email"
          onChange={(event) => setSearchValue(event.target.value)}
        />
      </div>

      {providers.isPending ? (
        <AvailabilitySectionSkeleton label="Loading Counselors…" />
      ) : providers.isError ? (
        <div className="mt-6">
          <AvailabilityQueryError
            error={providers.error}
            fallback="Counselors could not be loaded."
            onRetry={() => void providers.refetch()}
          />
        </div>
      ) : providers.data.data.items.length === 0 ? (
        <p className="mt-5 border-y border-border py-8 text-sm text-muted">
          No providers match the current search.
        </p>
      ) : (
        <>
          {providers.isFetching ? (
            <p role="status" className="mt-4 text-xs text-muted">
              Refreshing Counselors…
            </p>
          ) : null}
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Name
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Email
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {providers.data.data.items.map((provider) => {
                  const legacy =
                    provider.role === "GUIDANCE_SERVICES_STAFF";
                  return (
                    <tr key={provider.id} className="border-t border-border">
                      <th
                        scope="row"
                        className="px-4 py-4 font-semibold text-ink"
                      >
                        {provider.full_name || provider.email}
                      </th>
                      <td className="px-4 py-4 text-muted">
                        {provider.email}
                      </td>
                      <td className="px-4 py-4">
                        <AvailabilityStatusBadge
                          active={provider.is_active}
                          legacy={legacy}
                        />
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Button
                          variant="quiet"
                          onClick={() => setSelected(provider)}
                        >
                          Manage
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {page > 1 || providers.data.data.has_next ? (
            <nav
              aria-label="Counselor pagination"
              className="mt-5 flex items-center justify-between gap-4"
            >
              <Button
                variant="secondary"
                disabled={page <= 1}
                onClick={() => movePage(page - 1)}
              >
                Previous
              </Button>
              <span className="text-sm text-muted">
                Page {providers.data.data.page}
              </span>
              <Button
                variant="secondary"
                disabled={!providers.data.data.has_next}
                onClick={() => movePage(page + 1)}
              >
                Next
              </Button>
            </nav>
          ) : null}
        </>
      )}
    </section>
  );
}

"use client";

import Link from "next/link";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { dataTable } from "@/components/ui/data-table";
import { focusHeading } from "@/lib/focus-heading";
import { cn } from "@/lib/utils/cn";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { safeQueryData, canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import {
  availabilityErrorMessage,
  AvailabilityPageHeading,
  AvailabilityQueryError,
  AvailabilityRouteUnavailable,
  AvailabilitySectionSkeleton,
  AvailabilityStatusBadge,
  canManageAvailability,
  canUseSelfAvailability,
  useAvailabilityAction,
} from "@/features/availability/availability-shared";
import { EffectiveAvailabilityPreview } from "@/features/availability/effective-availability-preview";
import { UnavailabilitySection } from "@/features/availability/unavailability-section";
import { WeeklyScheduleCleanup, WeeklyScheduleEditor } from "@/features/availability/weekly-schedule-editor";
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
  useAvailabilityGetProvider,
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

// The recurring schedule is the primary work and its dated exceptions are secondary, so they sit
// side by side (about two to one) once the page itself is wide enough, and stack otherwise. The
// decision uses the page's own width (a container query), so an expanded dock stacks them instead
// of squeezing the schedule. The preview of the result supports both and spans below them.
function AvailabilityLayout({
  schedule,
  exceptions,
  preview,
}: {
  schedule: ReactNode;
  exceptions: ReactNode;
  preview?: ReactNode;
}) {
  return (
    <div className="@container/availability">
      <div className="grid items-start gap-5 @[68rem]/availability:grid-cols-[minmax(0,2fr)_minmax(20rem,1fr)]">
        <div className="min-w-0">{schedule}</div>
        <div className="min-w-0">{exceptions}</div>
      </div>
      {preview ? <div className="mt-5">{preview}</div> : null}
    </div>
  );
}

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
  const status = useActionStatus();
  const [previewRefresh, setPreviewRefresh] = useState(0);
  const weeklyData = safeQueryData(weekly);
  const exceptionData = safeQueryData(exceptions);

  if (!allowed) return <AvailabilityRouteUnavailable />;

  async function saveWeekly(
    windows: WeeklyWindowRequest[],
  ): Promise<boolean> {
    status.dismiss();
    const response = await weeklyAction.run(
      () => replaceWeekly.mutateAsync({ data: { windows } }),
      "Your weekly Availability could not be saved.",
    );
    if (!response) return false;
    status.show("Weekly schedule saved.");
    await weekly.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  async function addException(
    payload: ExceptionCreateRequest,
  ): Promise<boolean> {
    status.dismiss();
    const response = await exceptionAction.run(
      () => createException.mutateAsync({ data: payload }),
      "Your unavailability could not be added.",
    );
    if (!response) return false;
    status.show("Unavailability added.");
    await exceptions.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  async function removeExceptionById(
    exceptionId: string,
  ): Promise<boolean> {
    status.dismiss();
    const response = await exceptionAction.run(
      () => removeException.mutateAsync({ exceptionId }),
      "Your unavailability could not be removed.",
    );
    if (!response) return false;
    await exceptions.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  return (
    <section>
      <AvailabilityPageHeading title="My availability" />

      <AvailabilityLayout
        schedule={
          <>
            {weekly.isError && canShowLastKnownData(weekly) ? <RefreshFailureNotice onRetry={() => void weekly.refetch()} retrying={weekly.isFetching} /> : null}
            {weekly.isPending ? (
              <AvailabilitySectionSkeleton label="Loading weekly Availability…" />
            ) : !weeklyData ? (
              <AvailabilityQueryError
                error={weekly.error}
                fallback="Your weekly Availability could not be loaded."
                onRetry={() => void weekly.refetch()}
              />
            ) : (
              <WeeklyScheduleEditor
                key={weeklyData.data.windows.map((window) => window.id).join("|")}
                windows={weeklyData.data.windows}
                canMutate={canMutate}
                pending={replaceWeekly.isPending}
                error={weeklyAction.error}
                onSave={saveWeekly}
              />
            )}
          </>
        }
        exceptions={
          <>
            {exceptions.isError && canShowLastKnownData(exceptions) ? <RefreshFailureNotice onRetry={() => void exceptions.refetch()} retrying={exceptions.isFetching} /> : null}
            {exceptions.isPending ? (
              <AvailabilitySectionSkeleton label="Loading unavailability…" />
            ) : !exceptionData ? (
              <AvailabilityQueryError
                error={exceptions.error}
                fallback="Your unavailability could not be loaded."
                onRetry={() => void exceptions.refetch()}
              />
            ) : (
              <UnavailabilitySection
                items={exceptionData.data.items}
                canCreate={canMutate}
                canRemove={canMutate}
                createPending={createException.isPending}
                removePending={removeException.isPending}
                error={exceptionAction.error}
                onCreate={addException}
                onRemove={removeExceptionById}
                onResetError={exceptionAction.resetError}
              />
            )}
          </>
        }
        preview={<EffectiveAvailabilityPreview providerId={user.id} refreshToken={previewRefresh} />}
      />

      <ActionStatus status={status.status} onDismiss={status.dismiss} />
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
  const status = useActionStatus();
  const weeklyData = safeQueryData(weekly);
  const exceptionData = safeQueryData(exceptions);

  if (!allowed) return <AvailabilityRouteUnavailable management />;

  async function saveWeekly(
    windows: WeeklyWindowRequest[],
  ): Promise<boolean> {
    status.dismiss();
    const response = await weeklyAction.run(
      () => replaceWeekly.mutateAsync({ data: { windows } }),
      "Office weekly Availability could not be saved.",
    );
    if (!response) return false;
    status.show("Office weekly schedule saved.");
    await weekly.refetch();
    return true;
  }

  async function addException(
    payload: ExceptionCreateRequest,
  ): Promise<boolean> {
    status.dismiss();
    const response = await exceptionAction.run(
      () => createException.mutateAsync({ data: payload }),
      "Office unavailability could not be added.",
    );
    if (!response) return false;
    status.show("Office unavailability added.");
    await exceptions.refetch();
    return true;
  }

  async function removeExceptionById(
    exceptionId: string,
  ): Promise<boolean> {
    status.dismiss();
    const response = await exceptionAction.run(
      () => removeException.mutateAsync({ exceptionId }),
      "Office unavailability could not be removed.",
    );
    if (!response) return false;
    await exceptions.refetch();
    return true;
  }

  return (
    <section>
      <AvailabilityPageHeading
        title="Office availability"
        description="New appointment times can be offered only when the office and a counselor are both available."
      />

      <AvailabilityLayout
        schedule={
          <>
            {weekly.isError && canShowLastKnownData(weekly) ? <RefreshFailureNotice onRetry={() => void weekly.refetch()} retrying={weekly.isFetching} /> : null}
            {weekly.isPending ? (
              <AvailabilitySectionSkeleton label="Loading Office weekly Availability…" />
            ) : !weeklyData ? (
              <AvailabilityQueryError
                error={weekly.error}
                fallback="Office weekly Availability could not be loaded."
                onRetry={() => void weekly.refetch()}
              />
            ) : (
              <WeeklyScheduleEditor
                key={weeklyData.data.windows.map((window) => window.id).join("|")}
                windows={weeklyData.data.windows}
                canMutate
                pending={replaceWeekly.isPending}
                error={weeklyAction.error}
                onSave={saveWeekly}
              />
            )}
          </>
        }
        exceptions={
          <>
            {exceptions.isError && canShowLastKnownData(exceptions) ? <RefreshFailureNotice onRetry={() => void exceptions.refetch()} retrying={exceptions.isFetching} /> : null}
            {exceptions.isPending ? (
              <AvailabilitySectionSkeleton label="Loading Office unavailability…" />
            ) : !exceptionData ? (
              <AvailabilityQueryError
                error={exceptions.error}
                fallback="Office unavailability could not be loaded."
                onRetry={() => void exceptions.refetch()}
              />
            ) : (
              <UnavailabilitySection
                items={exceptionData.data.items}
                canCreate
                canRemove
                createPending={createException.isPending}
                removePending={removeException.isPending}
                error={exceptionAction.error}
                onCreate={addException}
                onRemove={removeExceptionById}
                onResetError={exceptionAction.resetError}
              />
            )}
          </>
        }
      />

      <ActionStatus status={status.status} onDismiss={status.dismiss} />
    </section>
  );
}

function ProviderWorkspace({
  provider,
}: {
  provider: AvailabilityProviderSummary;
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
  const status = useActionStatus();
  const [previewRefresh, setPreviewRefresh] = useState(0);
  const weeklyData = safeQueryData(weekly);
  const exceptionData = safeQueryData(exceptions);

  // Place focus at the resource identity after its summary loads.
  useEffect(() => {
    focusHeading("provider-availability-heading");
  }, []);

  async function replaceProviderWeekly(windows: WeeklyWindowRequest[]): Promise<boolean> {
    status.dismiss();
    const response = await weeklyAction.run(
      () =>
        replaceWeekly.mutateAsync({
          providerId: provider.id,
          data: { windows },
        }),
      "The Counselor's weekly Availability could not be saved.",
    );
    if (!response) return false;
    await weekly.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  async function saveWeekly(windows: WeeklyWindowRequest[]): Promise<boolean> {
    const saved = await replaceProviderWeekly(windows);
    if (saved) status.show("Weekly schedule saved.");
    return saved;
  }

  async function addException(
    payload: ExceptionCreateRequest,
  ): Promise<boolean> {
    status.dismiss();
    const response = await exceptionAction.run(
      () =>
        createException.mutateAsync({
          providerId: provider.id,
          data: payload,
        }),
      "The Counselor's unavailability could not be added.",
    );
    if (!response) return false;
    status.show("Unavailability added.");
    await exceptions.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  async function removeExceptionById(
    exceptionId: string,
  ): Promise<boolean> {
    status.dismiss();
    const response = await exceptionAction.run(
      () =>
        removeException.mutateAsync({
          providerId: provider.id,
          exceptionId,
        }),
      "The Counselor's unavailability could not be removed.",
    );
    if (!response) return false;
    await exceptions.refetch();
    setPreviewRefresh((value) => value + 1);
    return true;
  }

  return (
    <section>
      <PageHeader
        title={provider.full_name || provider.email}
        headingId="provider-availability-heading"
        meta={<AvailabilityStatusBadge active={provider.is_active} legacy={legacy} />}
        back={
          <GuardedPortalLink href="/portal/availability/providers" className="text-sm text-brand hover:underline">
            ← Counselors
          </GuardedPortalLink>
        }
      >
        <p className="mt-1.5 break-all text-sm text-muted">{provider.email}</p>
      </PageHeader>

      {!operational ? (
        <Notice tone="warning" className="mb-5 max-w-3xl">
          <span className="text-muted">
            {legacy
              ? "This is historical Guidance Services Staff Availability. Existing configuration can be reviewed or removed, but new operational Availability cannot be configured."
              : "This Counselor is inactive. Existing Availability can be reviewed or removed, but new Availability cannot be added."}
          </span>
        </Notice>
      ) : null}

      <AvailabilityLayout
        schedule={
          <>
            {weekly.isError && canShowLastKnownData(weekly) ? <RefreshFailureNotice onRetry={() => void weekly.refetch()} retrying={weekly.isFetching} /> : null}
            {weekly.isPending ? (
              <AvailabilitySectionSkeleton label="Loading the Counselor's weekly Availability…" />
            ) : !weeklyData ? (
              <AvailabilityQueryError
                error={weekly.error}
                fallback="The Counselor's weekly Availability could not be loaded."
                onRetry={() => void weekly.refetch()}
              />
            ) : operational ? (
              <WeeklyScheduleEditor
                key={weeklyData.data.windows.map((window) => window.id).join("|")}
                windows={weeklyData.data.windows}
                canMutate
                pending={replaceWeekly.isPending}
                error={weeklyAction.error}
                onSave={saveWeekly}
              />
            ) : (
              <WeeklyScheduleCleanup
                windows={weeklyData.data.windows}
                pending={replaceWeekly.isPending}
                error={weeklyAction.error}
                onClear={() => replaceProviderWeekly([])}
                onResetError={weeklyAction.resetError}
              />
            )}
          </>
        }
        exceptions={
          <>
            {exceptions.isError && canShowLastKnownData(exceptions) ? <RefreshFailureNotice onRetry={() => void exceptions.refetch()} retrying={exceptions.isFetching} /> : null}
            {exceptions.isPending ? (
              <AvailabilitySectionSkeleton label="Loading the Counselor's unavailability…" />
            ) : !exceptionData ? (
              <AvailabilityQueryError
                error={exceptions.error}
                fallback="The Counselor's unavailability could not be loaded."
                onRetry={() => void exceptions.refetch()}
              />
            ) : (
              <UnavailabilitySection
                items={exceptionData.data.items}
                canCreate={operational}
                canRemove
                createPending={createException.isPending}
                removePending={removeException.isPending}
                error={exceptionAction.error}
                onCreate={addException}
                onRemove={removeExceptionById}
                onResetError={exceptionAction.resetError}
              />
            )}
          </>
        }
        preview={canPreview ? <EffectiveAvailabilityPreview providerId={provider.id} refreshToken={previewRefresh} /> : undefined}
      />

      <ActionStatus status={status.status} onDismiss={status.dismiss} />
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
  const [searchDraft, setSearchDraft] = useState({ applied: search, value: search });
  if (searchDraft.applied !== search) setSearchDraft({ applied: search, value: search });
  const searchValue = searchDraft.applied === search ? searchDraft.value : search;
  const searchTimer = useRef<number | null>(null);
  const providers = useAvailabilityListProviders(
    {
      ...(search ? { search } : {}),
      page,
      page_size: 20,
    },
    { query: { enabled: allowed, retry: false } },
  );
  const providersData = safeQueryData(providers);

  useEffect(() => {
    if (searchValue === search) return;
    searchTimer.current = window.setTimeout(() => {
      searchTimer.current = null;
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
    return () => {
      if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
      searchTimer.current = null;
    };
  }, [pathname, router, search, searchParams, searchValue]);

  if (!allowed) return <AvailabilityRouteUnavailable management />;

  function cancelPendingSearch() {
    if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
    searchTimer.current = null;
  }

  function movePage(nextPage: number) {
    cancelPendingSearch();
    const next = new URLSearchParams(searchParams.toString());
    if (nextPage <= 1) next.delete("page");
    else next.set("page", String(nextPage));
    const query = next.toString();
    router.push(query ? pathname + "?" + query : pathname);
  }

  return (
    <section>
      <AvailabilityPageHeading title="Counselor availability" />

      {/* A lone directory search that applies as you type. */}
      <FloatingListTools label="Counselor search">
        <ListSearchField
          id="provider-search"
          label="Search Counselors"
          value={searchValue}
          placeholder="Search Counselors by name or email"
          maxLength={254}
          onChange={(event) => setSearchDraft({ applied: search, value: event.target.value })}
        />
      </FloatingListTools>

      {providers.isError && canShowLastKnownData(providers) ? <RefreshFailureNotice onRetry={() => void providers.refetch()} retrying={providers.isFetching} /> : null}
      <Panel aria-labelledby="provider-results-heading">
        <PanelHeader
          title="Counselors"
          titleId="provider-results-heading"
          context={providers.isFetching && !providers.isPending
            ? "Refreshing Counselors…"
            : providersData
              ? describeResultPage({ count: providersData.data.items.length, page: providersData.data.page, hasNext: providersData.data.has_next, noun: { one: "Counselor", other: "Counselors" }, filtered: Boolean(search) })
              : null}
        />
        {providers.isPending ? (
          <RowsSkeleton label="Loading Counselors…" />
        ) : !providersData ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void providers.refetch()}>Retry</Button>}>
            {availabilityErrorMessage(providers.error, "Counselors could not be loaded.")}
          </PanelMessage>
        ) : providersData.data.items.length === 0 ? (
          <PanelMessage>
            {search
              ? "No counselors match the current search."
              : "No counselors are available."}
          </PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[32rem]`}>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={dataTable.headerCell}>Name</th>
                  <th scope="col" className={dataTable.headerCell}>Email</th>
                  <th scope="col" className={dataTable.headerCell}>Status</th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {providersData.data.items.map((provider) => {
                  const legacy =
                    provider.role === "GUIDANCE_SERVICES_STAFF";
                  return (
                    <tr key={provider.id} className={dataTable.row}>
                      <th scope="row" className={cn(dataTable.cell, "py-1.5 align-middle font-normal")}>
                        <Link
                          href={`/portal/availability/providers/${provider.id}`}
                          onClick={cancelPendingSearch}
                          className="inline-flex min-h-10 items-center rounded-sm text-left font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                        >
                          <span className="sr-only">Manage availability for </span>
                          {provider.full_name || provider.email}
                        </Link>
                      </th>
                      <td className={cn(dataTable.cell, "align-middle text-muted")}>
                        {provider.email}
                      </td>
                      <td className={cn(dataTable.cell, "align-middle")}>
                        <AvailabilityStatusBadge
                          active={provider.is_active}
                          legacy={legacy}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {providersData ? (
          <CanonicalPagination
            className="border-brand-line px-4 py-3 sm:px-5"
            page={providersData.data.page}
            hasNext={providersData.data.has_next}
            label="Counselor pagination"
            onPageChange={movePage}
          />
        ) : null}
      </Panel>
    </section>
  );
}

export function ProviderAvailabilityDetailPage({ providerId }: { providerId: string }) {
  const { user } = usePortalSession();
  const allowed = canManageAvailability(user);
  const summary = useAvailabilityGetProvider(providerId, {
    query: { enabled: allowed, retry: false },
  });
  // An unconfirmed eligibility summary cannot enable configuration mutations.
  if (!allowed) return <AvailabilityRouteUnavailable management />;
  if (summary.isPending) return <AvailabilitySectionSkeleton label="Loading Counselor Availability…" />;
  if (summary.isError || !summary.data) return (
    <section>
      <AvailabilityPageHeading title="Counselor availability" />
      <AvailabilityQueryError error={summary.error} fallback="The Counselor could not be loaded." onRetry={() => void summary.refetch()} />
      <Link href="/portal/availability/providers" className="mt-4 inline-block text-sm text-brand hover:underline">← Counselors</Link>
    </section>
  );
  return <ProviderWorkspace key={providerId} provider={summary.data.data} />;
}

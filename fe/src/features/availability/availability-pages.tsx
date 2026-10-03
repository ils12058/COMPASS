"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { dataTable } from "@/components/ui/data-table";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
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
  const weeklyData = safeQueryData(weekly);
  const exceptionData = safeQueryData(exceptions);

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

      <div className="mt-5">
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
            notice={weeklyAction.notice}
            onSave={saveWeekly}
          />
        )}
      </div>

      <div className="mt-5">
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

      <div className="mt-5">
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
  const weeklyData = safeQueryData(weekly);
  const exceptionData = safeQueryData(exceptions);

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
        description="Set the office's regular days and hours. New appointment times can be offered only when the office and a counselor are both available."
      />

      <div className="mt-5">
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
            notice={weeklyAction.notice}
            onSave={saveWeekly}
          />
        )}
      </div>

      <div className="mt-5">
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
  const weeklyData = safeQueryData(weekly);
  const exceptionData = safeQueryData(exceptions);

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
      <PageHeader
        title={provider.full_name || provider.email}
        meta={<AvailabilityStatusBadge active={provider.is_active} legacy={legacy} />}
        back={
          <Button variant="quiet" className="mb-2 px-1" onClick={onBack}>
            ← Counselors
          </Button>
        }
      >
        <p className="mt-1.5 break-all text-sm text-muted">{provider.email}</p>
      </PageHeader>

      {!operational ? (
        <Notice tone="warning" className="mt-5 max-w-3xl">
          <span className="text-muted">
            {legacy
              ? "This is historical Guidance Services Staff Availability. Existing configuration can be reviewed or removed, but new operational Availability cannot be configured."
              : "This provider is inactive. Existing Availability can be reviewed or removed, but new Availability cannot be configured."}
          </span>
        </Notice>
      ) : null}

      <div className="mt-5">
        {weekly.isError && canShowLastKnownData(weekly) ? <RefreshFailureNotice onRetry={() => void weekly.refetch()} retrying={weekly.isFetching} /> : null}
        {weekly.isPending ? (
          <AvailabilitySectionSkeleton label="Loading provider weekly Availability…" />
        ) : !weeklyData ? (
          <AvailabilityQueryError
            error={weekly.error}
            fallback="Provider weekly Availability could not be loaded."
            onRetry={() => void weekly.refetch()}
          />
        ) : (
          <WeeklyScheduleEditor
            key={weeklyData.data.windows.map((window) => window.id).join("|")}
            windows={weeklyData.data.windows}
            canMutate
            cleanupOnly={!operational}
            pending={replaceWeekly.isPending}
            error={weeklyAction.error}
            notice={weeklyAction.notice}
            onSave={saveWeekly}
          />
        )}
      </div>

      <div className="mt-5">
        {exceptions.isError && canShowLastKnownData(exceptions) ? <RefreshFailureNotice onRetry={() => void exceptions.refetch()} retrying={exceptions.isFetching} /> : null}
        {exceptions.isPending ? (
          <AvailabilitySectionSkeleton label="Loading provider unavailability…" />
        ) : !exceptionData ? (
          <AvailabilityQueryError
            error={exceptions.error}
            fallback="Provider unavailability could not be loaded."
            onRetry={() => void exceptions.refetch()}
          />
        ) : (
          <UnavailabilitySection
            items={exceptionData.data.items}
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
        <div className="mt-5">
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
  const providersData = safeQueryData(providers);

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

      {/* A lone directory search that applies as you type. */}
      <FilterToolbar className="mt-5" fieldsClassName="lg:grid-cols-[minmax(0,28rem)]">
        <FilterField label="Search Counselors" htmlFor="provider-search">
          <Input
            id="provider-search"
            type="search"
            value={searchValue}
            placeholder="Search Counselors by name or email"
            onChange={(event) => setSearchValue(event.target.value)}
          />
        </FilterField>
      </FilterToolbar>

      {providers.isError && canShowLastKnownData(providers) ? <RefreshFailureNotice onRetry={() => void providers.refetch()} retrying={providers.isFetching} /> : null}
      <Panel className="mt-5" aria-labelledby="provider-results-heading">
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
            <table className={`${dataTable.table} min-w-[40rem]`}>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={dataTable.headerCell}>Name</th>
                  <th scope="col" className={dataTable.headerCell}>Email</th>
                  <th scope="col" className={dataTable.headerCell}>Status</th>
                  <th scope="col" className={`${dataTable.headerCell} text-right`}>Action</th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {providersData.data.items.map((provider) => {
                  const legacy =
                    provider.role === "GUIDANCE_SERVICES_STAFF";
                  return (
                    <tr key={provider.id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} font-semibold text-ink`}>
                        {provider.full_name || provider.email}
                      </th>
                      <td className={`${dataTable.cell} text-muted`}>
                        {provider.email}
                      </td>
                      <td className={dataTable.cell}>
                        <AvailabilityStatusBadge
                          active={provider.is_active}
                          legacy={legacy}
                        />
                      </td>
                      <td className={`${dataTable.cell} py-2 text-right`}>
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

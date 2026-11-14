"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ContextHelp } from "@/components/ui/context-help";
import { dataTable } from "@/components/ui/data-table";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { Select } from "@/components/ui/select";
import { SortableColumnHeader } from "@/components/ui/sortable-column-header";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";
import { ReminderSender } from "@/features/appointments/appointment-reminders";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import {
  appointmentErrorMessage,
  updateAppointmentQuery,
} from "@/features/appointments/appointments-shared";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { GraduateTracerReminders } from "@/features/reminders/graduate-tracer-reminders";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useListOrdering } from "@/features/portal/components/list-ordering";
import { describeResultPage } from "@/features/portal/components/result-context";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  activityReminderParams,
  deliveryStateLabel,
  inAppStateLabel,
  lastReminderLabel,
  manualReminderLabel,
  MAX_REMINDER_SELECTION,
  nextAutomaticLabel,
  reminderDeliveryFilter,
  reminderIssuerLabel,
  reminderKindFilter,
  reminderKindLabel,
  reminderPageValue,
  reminderView,
  upcomingReminderParams,
} from "@/features/reminders/reminders-shared";
import {
  getAppointmentsListReminderActivityQueryKey,
  getAppointmentsListUpcomingRemindersQueryKey,
  useAppointmentsListReminderActivity,
  useAppointmentsListUpcomingReminders,
} from "@/lib/api/generated/appointments/appointments";
import { useAvailabilityListProviders } from "@/lib/api/generated/availability/availability";
import {
  AppointmentListOrdering,
  AppointmentReminderHistoryKind,
  AppointmentReminderTransportState,
} from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

const UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

const kindOptions: { value: AppointmentReminderHistoryKind; label: string }[] = [
  { value: AppointmentReminderHistoryKind.AUTO_24H, label: "24-hour reminder" },
  { value: AppointmentReminderHistoryKind.AUTO_3H, label: "3-hour reminder" },
  { value: AppointmentReminderHistoryKind.MANUAL, label: "Manual reminder" },
];

const deliveryOptions: { value: AppointmentReminderTransportState; label: string }[] = [
  { value: AppointmentReminderTransportState.NOT_REQUESTED, label: "Not requested" },
  { value: AppointmentReminderTransportState.PENDING, label: "Pending" },
  { value: AppointmentReminderTransportState.SENT, label: "Sent" },
  { value: AppointmentReminderTransportState.FAILED, label: "Not sent" },
  { value: AppointmentReminderTransportState.CANCELLED, label: "Cancelled" },
];

function RemindersHelp() {
  return (
    <ContextHelp
      title="Reminders"
      sections={[
        {
          heading: "Automatic reminders",
          content: (
            <p>
              COMPASS reminds the Student 24 hours and 3 hours before a scheduled Appointment. Each
              reminder is sent once per Appointment schedule and only while the Student account can
              receive it.
            </p>
          ),
        },
        {
          heading: "Manual reminders",
          content: (
            <p>
              A staff member can send a manual reminder after previewing exactly who will receive it
              and confirming. A reminder never changes the Appointment.
            </p>
          ),
        },
        {
          heading: "When you can send a manual reminder",
          content: (
            <p>
              The Appointment must still be scheduled, start in more than 15 minutes, and not have
              received a manual reminder in the last three hours. Each row says whether it is ready
              to send or why it is not.
            </p>
          ),
        },
        {
          heading: "Sent reminders and delivery",
          content: (
            <p>
              Sent shows reminders issued for Appointments you manage; email and browser notifications follow when available. Sent means handed off for delivery; it does not confirm that the Student read it.
            </p>
          ),
        },
        {
          heading: "Appointments you manage",
          content: <p>Only Appointments you manage appear here.</p>,
        },
      ]}
    />
  );
}

function ReminderSourceField({ id }: { id: string }) {
  return (
    <FilterField label="Source" htmlFor={id}>
      <Select id={id} defaultValue="appointments">
        <option value="appointments">Appointments</option>
      </Select>
    </FilterField>
  );
}

type UpcomingDraft = { from: string; to: string; counselor: string; availability: string };

function UpcomingFilters({
  applied,
  counselorOptions,
  counselorsPending,
  counselorsFailed,
  canFilterCounselor,
  onSubmit,
  onClear,
}: {
  applied: UpcomingDraft;
  counselorOptions: { id: string; full_name: string }[];
  counselorsPending: boolean;
  counselorsFailed: boolean;
  canFilterCounselor: boolean;
  onSubmit: (draft: UpcomingDraft) => void;
  onClear: () => void;
}) {
  const [draft, setDraft] = useState(applied);
  const appliedCounselorKnown = counselorOptions.some((option) => option.id === applied.counselor);

  function set(name: keyof UpcomingDraft, value: string) {
    setDraft((current) => ({ ...current, [name]: value }));
  }

  return (
    <form
      role="search"
      aria-label="Filter upcoming reminders"
      className="mb-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(draft);
      }}
    >
      <FilterToolbar
        fieldsClassName={canFilterCounselor ? "lg:grid-cols-5" : "lg:grid-cols-4"}
        actions={
          <>
            <Button type="button" variant="quiet" onClick={onClear}>
              Clear filters
            </Button>
            <Button type="submit">Apply filters</Button>
          </>
        }
      >
        <ReminderSourceField id="reminder-upcoming-source" />
        <FilterField label="From" htmlFor="reminder-upcoming-from">
          <Input
            id="reminder-upcoming-from"
            type="date"
            value={draft.from}
            onChange={(event) => set("from", event.target.value)}
          />
        </FilterField>
        <FilterField label="To" htmlFor="reminder-upcoming-to">
          <Input
            id="reminder-upcoming-to"
            type="date"
            value={draft.to}
            onChange={(event) => set("to", event.target.value)}
          />
        </FilterField>
        {canFilterCounselor ? (
          <FilterField
            label="Counselor"
            htmlFor="reminder-upcoming-counselor"
            hint={
              counselorsFailed ? (
                <p className="text-xs text-warning">Couldn&apos;t load Counselor choices. Try again.</p>
              ) : null
            }
          >
            <Select
              id="reminder-upcoming-counselor"
              value={draft.counselor}
              disabled={counselorsPending && !applied.counselor}
              onChange={(event) => set("counselor", event.target.value)}
            >
              <option value="">All Counselors</option>
              {applied.counselor && !appliedCounselorKnown ? (
                <option value={applied.counselor}>
                  {counselorsPending ? "Loading Counselor…" : "Selected Counselor"}
                </option>
              ) : null}
              {counselorOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.full_name}
                </option>
              ))}
            </Select>
          </FilterField>
        ) : null}
        <FilterField label="Manual reminder" htmlFor="reminder-upcoming-availability">
          <Select
            id="reminder-upcoming-availability"
            value={draft.availability}
            onChange={(event) => set("availability", event.target.value)}
          >
            <option value="">All Appointments</option>
            <option value="ready">Ready to send</option>
            <option value="blocked">Cannot send now</option>
          </Select>
        </FilterField>
      </FilterToolbar>
    </form>
  );
}

type SentDraft = { kind: string; delivery: string; from: string; to: string };

function SentFilters({
  applied,
  onSubmit,
  onClear,
}: {
  applied: SentDraft;
  onSubmit: (draft: SentDraft) => void;
  onClear: () => void;
}) {
  const [draft, setDraft] = useState(applied);

  function set(name: keyof SentDraft, value: string) {
    setDraft((current) => ({ ...current, [name]: value }));
  }

  return (
    <form
      role="search"
      aria-label="Filter sent reminders"
      className="mb-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(draft);
      }}
    >
      <FilterToolbar
        fieldsClassName="lg:grid-cols-5"
        actions={
          <>
            <Button type="button" variant="quiet" onClick={onClear}>
              Clear filters
            </Button>
            <Button type="submit">Apply filters</Button>
          </>
        }
      >
        <ReminderSourceField id="reminder-sent-source" />
        <FilterField label="Reminder" htmlFor="reminder-sent-kind">
          <Select
            id="reminder-sent-kind"
            value={draft.kind}
            onChange={(event) => set("kind", event.target.value)}
          >
            <option value="">All reminders</option>
            {kindOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </FilterField>
        <FilterField label="Delivery" htmlFor="reminder-sent-delivery">
          <Select
            id="reminder-sent-delivery"
            value={draft.delivery}
            onChange={(event) => set("delivery", event.target.value)}
          >
            <option value="">All delivery states</option>
            {deliveryOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </FilterField>
        <FilterField label="From" htmlFor="reminder-sent-from">
          <Input
            id="reminder-sent-from"
            type="date"
            value={draft.from}
            onChange={(event) => set("from", event.target.value)}
          />
        </FilterField>
        <FilterField label="To" htmlFor="reminder-sent-to">
          <Input
            id="reminder-sent-to"
            type="date"
            value={draft.to}
            onChange={(event) => set("to", event.target.value)}
          />
        </FilterField>
      </FilterToolbar>
    </form>
  );
}

const reminderTransports = [
  { key: "in_app", label: "In-app" },
  { key: "email", label: "Email" },
  { key: "push", label: "Browser push" },
] as const;

function RemindersWorkspace() {
  const { user } = usePortalSession();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [sendOpen, setSendOpen] = useState(false);

  const tab = reminderView(searchParams.get("tab"));
  const page = reminderPageValue(searchParams.get("page"));
  const fromDate = searchParams.get("from") ?? "";
  const toDate = searchParams.get("to") ?? "";
  const availableParam = searchParams.get("available");
  const availability =
    availableParam === "1" ? "ready" : availableParam === "0" ? "blocked" : "";
  const available = availability === "ready" ? true : availability === "blocked" ? false : undefined;
  const counselorParam = searchParams.get("counselor") ?? "";
  const kind = reminderKindFilter(searchParams.get("kind"));
  const delivery = reminderDeliveryFilter(searchParams.get("delivery"));
  const { requested: requestedOrdering, setOrdering } = useListOrdering(AppointmentListOrdering);

  // The counselor directory is readable by accounts with Availability management; other managers
  // keep the fixed date and manual-availability filters.
  const canFilterCounselor = user.capabilities.includes("availability.manage");
  const counselor = canFilterCounselor && UUID_PATTERN.test(counselorParam) ? counselorParam : "";
  const counselors = useAvailabilityListProviders(
    { page: 1, page_size: 50 },
    { query: { enabled: canFilterCounselor, retry: false, staleTime: 5 * 60_000 } },
  );
  const counselorOptions = counselors.data?.data.items ?? [];

  const upcoming = useAppointmentsListUpcomingReminders(
    upcomingReminderParams({ from: fromDate, to: toDate, counselor, available }, page, requestedOrdering),
    { query: { enabled: tab === "upcoming", retry: false } },
  );
  const activity = useAppointmentsListReminderActivity(
    activityReminderParams({ from: fromDate, to: toDate, kind, delivery }, page),
    { query: { enabled: tab === "sent", retry: false } },
  );

  const upcomingData = upcoming.data?.data;
  const activityData = activity.data?.data;
  const upcomingItems = upcomingData?.items ?? [];
  const activityItems = activityData?.items ?? [];
  const ordering = requestedOrdering ?? upcomingData?.ordering;
  const hasUpcomingFilters = Boolean(fromDate || toDate || counselor || availability);
  const hasSentFilters = Boolean(kind || delivery || fromDate || toDate);
  const selectable = upcomingItems.filter((item) => item.manual_available);
  const allSelected =
    selectable.length > 0 &&
    selectable.every((item) => selectedIds.includes(item.appointment_id));

  function tabHref(next: "upcoming" | "sent") {
    return next === "upcoming" ? pathname : `${pathname}?tab=sent`;
  }

  function applyUpcomingFilters(draft: UpcomingDraft) {
    router.replace(
      updateAppointmentQuery(
        pathname,
        new URLSearchParams(searchParams.toString()),
        {
          from: draft.from,
          to: draft.to,
          counselor: canFilterCounselor ? draft.counselor : "",
          available: draft.availability === "ready" ? "1" : draft.availability === "blocked" ? "0" : "",
        },
      ),
      { scroll: false },
    );
  }

  function clearUpcomingFilters() {
    router.replace(
      updateAppointmentQuery(
        pathname,
        new URLSearchParams(searchParams.toString()),
        { from: "", to: "", counselor: "", available: "" },
      ),
      { scroll: false },
    );
  }

  function applySentFilters(draft: SentDraft) {
    router.replace(
      updateAppointmentQuery(
        pathname,
        new URLSearchParams(searchParams.toString()),
        { kind: draft.kind, delivery: draft.delivery, from: draft.from, to: draft.to },
      ),
      { scroll: false },
    );
  }

  function clearSentFilters() {
    router.replace(
      updateAppointmentQuery(
        pathname,
        new URLSearchParams(searchParams.toString()),
        { kind: "", delivery: "", from: "", to: "" },
      ),
      { scroll: false },
    );
  }

  function movePage(nextPage: number) {
    router.push(
      updateAppointmentQuery(
        pathname,
        new URLSearchParams(searchParams.toString()),
        { page: String(nextPage) },
        false,
      ),
      { scroll: false },
    );
  }

  function toggleSelection(id: string, checked: boolean) {
    setSelectedIds((previous) =>
      checked
        ? previous.includes(id) || previous.length >= MAX_REMINDER_SELECTION
          ? previous
          : [...previous, id]
        : previous.filter((value) => value !== id),
    );
  }

  function selectPage(checked: boolean) {
    setSelectedIds(checked ? selectable.slice(0, MAX_REMINDER_SELECTION).map((item) => item.appointment_id) : []);
  }

  function remindersChanged() {
    void queryClient.invalidateQueries({ queryKey: getAppointmentsListUpcomingRemindersQueryKey() });
    void queryClient.invalidateQueries({ queryKey: getAppointmentsListReminderActivityQueryKey() });
  }

  return (
    <section aria-labelledby="reminders-heading">
      <PageHeader
        title="Reminders"
        headingId="reminders-heading"
        help={<RemindersHelp />}
      />

      <WorkspaceTabs label="Reminder views">
        {(
          [
            { value: "upcoming", label: "Upcoming" },
            { value: "sent", label: "Sent" },
          ] as const
        ).map((item) => {
          const current = tab === item.value;
          return (
            <Link
              key={item.value}
              href={tabHref(item.value)}
              aria-current={current ? "page" : undefined}
              className={workspaceTabClass(current)}
            >
              {item.label}
            </Link>
          );
        })}
      </WorkspaceTabs>

      <ReminderSender
        selected={selectedIds}
        open={sendOpen}
        onClose={() => {
          setSendOpen(false);
          setSelectedIds([]);
        }}
        onComplete={remindersChanged}
      />

      {tab === "upcoming" ? (
        <>
          <UpcomingFilters
            key={`upcoming:${searchParams.toString()}`}
            applied={{ from: fromDate, to: toDate, counselor, availability }}
            counselorOptions={counselorOptions}
            counselorsPending={counselors.isPending}
            counselorsFailed={counselors.isError}
            canFilterCounselor={canFilterCounselor}
            onSubmit={applyUpcomingFilters}
            onClear={clearUpcomingFilters}
          />
          <Panel aria-labelledby="upcoming-reminders-heading">
            <PanelHeader
              title="Upcoming reminders"
              titleId="upcoming-reminders-heading"
              context={
                upcoming.isFetching && !upcoming.isPending
                  ? "Refreshing upcoming reminders…"
                  : upcomingData && !upcoming.isError
                    ? describeResultPage({
                        count: upcomingItems.length,
                        page: upcomingData.page,
                        hasNext: upcomingData.has_next,
                        noun: { one: "appointment", other: "appointments" },
                        filtered: hasUpcomingFilters,
                      })
                    : null
              }
            />
            {selectedIds.length > 0 ? (
              <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
                <p className="text-sm text-ink">
                  {selectedIds.length} selected
                  <span className="block text-xs text-muted">
                    Only Appointments ready to send can be selected, up to {MAX_REMINDER_SELECTION}.
                  </span>
                </p>
                <Button disabled={selectedIds.length === 0 || sendOpen} onClick={() => setSendOpen(true)}>
                  {selectedIds.length === 1 ? "Send reminder" : "Send reminders"}
                </Button>
                <Button variant="secondary" onClick={() => setSelectedIds([])}>
                  Clear selection
                </Button>
              </div>
            ) : null}
            {upcoming.isPending ? (
              <RowsSkeleton label="Loading upcoming reminders…" framed={false} />
            ) : upcoming.isError ? (
              <PanelMessage
                role="alert"
                tone="danger"
                action={
                  <Button variant="secondary" onClick={() => void upcoming.refetch()}>
                    Retry
                  </Button>
                }
              >
                {appointmentErrorMessage(upcoming.error, "Couldn't load upcoming reminders. Try again.")}
              </PanelMessage>
            ) : upcomingItems.length === 0 ? (
              <PanelMessage
                action={
                  hasUpcomingFilters ? (
                    <Button variant="secondary" onClick={clearUpcomingFilters}>
                      Clear filters
                    </Button>
                  ) : undefined
                }
              >
                {hasUpcomingFilters
                  ? "No upcoming Appointments match the selected filters."
                  : "No Appointments are scheduled in the reminder window."}
              </PanelMessage>
            ) : (
              <>
                <div
                  className={`${dataTable.scroll} hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus md:block`}
                  role="region"
                  aria-label="Upcoming reminders. Scroll horizontally to view all columns."
                  tabIndex={0}
                >
                  <table className={`${dataTable.table} min-w-[1100px]`}>
                    <caption className="sr-only">Upcoming reminders</caption>
                    <thead className={dataTable.head}>
                      <tr>
                        <th scope="col" className={`${dataTable.headerCell} w-12`}>
                          <input
                            type="checkbox"
                            aria-label="Select Appointments that are ready to send on this page"
                            disabled={selectable.length === 0}
                            checked={allSelected}
                            onChange={(event) => selectPage(event.target.checked)}
                          />
                        </th>
                        <th scope="col" className={dataTable.headerCell}>Appointment</th>
                        <th scope="col" className={dataTable.headerCell}>Student</th>
                        <th scope="col" className={dataTable.headerCell}>Counselor</th>
                        <th scope="col" className={dataTable.headerCell}>Service</th>
                        <SortableColumnHeader
                          label="Starts"
                          ascending={AppointmentListOrdering.EARLIEST_START}
                          descending={AppointmentListOrdering.LATEST_START}
                          ascendingLabel="Earliest start first"
                          descendingLabel="Latest start first"
                          current={ordering}
                          onSort={setOrdering}
                          className={dataTable.headerCell}
                        />
                        <th scope="col" className={dataTable.headerCell}>Next automatic</th>
                        <th scope="col" className={dataTable.headerCell}>Last reminder</th>
                        <th scope="col" className={dataTable.headerCell}>Manual reminder</th>
                      </tr>
                    </thead>
                    <tbody className={dataTable.body}>
                      {upcomingItems.map((item) => (
                        <tr key={item.appointment_id} className={dataTable.row}>
                          <td className={dataTable.cell}>
                            <input
                              type="checkbox"
                              aria-label={`Select ${item.reference_code}`}
                              checked={selectedIds.includes(item.appointment_id)}
                              disabled={
                                !item.manual_available ||
                                (!selectedIds.includes(item.appointment_id) &&
                                  selectedIds.length >= MAX_REMINDER_SELECTION)
                              }
                              onChange={(event) => toggleSelection(item.appointment_id, event.target.checked)}
                            />
                          </td>
                          <th scope="row" className={`${dataTable.cell} font-normal`}>
                            <Link
                              href={`/portal/appointments/${item.appointment_id}`}
                              className="font-mono text-xs font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                            >
                              {item.reference_code}
                            </Link>
                          </th>
                          <td className={`${dataTable.cell} font-medium text-ink`}>{item.student_name}</td>
                          <td className={`${dataTable.cell} text-ink`}>{item.counselor.display_name}</td>
                          <td className={`${dataTable.cell} text-ink`}>{item.service_name}</td>
                          <td className={`${dataTable.cell} text-ink`}>
                            <time dateTime={item.starts_at}>{formatInstitutionalDateTime(item.starts_at)}</time>
                          </td>
                          <td className={`${dataTable.cell} text-ink`}>{nextAutomaticLabel(item.next_automatic)}</td>
                          <td className={`${dataTable.cell} text-ink`}>{lastReminderLabel(item)}</td>
                          <td className={`${dataTable.cell} ${item.manual_available ? "text-success" : "text-muted"}`}>
                            {manualReminderLabel(item)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <ul className="divide-y divide-border md:hidden">
                  {upcomingItems.map((item) => (
                    <li key={item.appointment_id} className="px-4 py-4">
                      <article>
                        <label className="mb-2 flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(item.appointment_id)}
                            disabled={
                              !item.manual_available ||
                              (!selectedIds.includes(item.appointment_id) &&
                                selectedIds.length >= MAX_REMINDER_SELECTION)
                            }
                            onChange={(event) => toggleSelection(item.appointment_id, event.target.checked)}
                          />
                          Select Appointment
                        </label>
                        <div className="min-w-0">
                          <Link
                            href={`/portal/appointments/${item.appointment_id}`}
                            className="break-all font-mono text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                          >
                            {item.reference_code}
                          </Link>
                          <p className="mt-1 break-words font-medium text-ink">{item.student_name}</p>
                        </div>
                        <dl className="mt-3 grid gap-x-5 gap-y-2 text-sm sm:grid-cols-2">
                          <div>
                            <dt className="text-xs text-muted">Counselor</dt>
                            <dd className="mt-0.5 text-ink">{item.counselor.display_name}</dd>
                          </div>
                          <div>
                            <dt className="text-xs text-muted">Service</dt>
                            <dd className="mt-0.5 text-ink">{item.service_name}</dd>
                          </div>
                          <div>
                            <dt className="text-xs text-muted">Starts</dt>
                            <dd className="mt-0.5 text-ink">
                              <time dateTime={item.starts_at}>{formatInstitutionalDateTime(item.starts_at)}</time>
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-muted">Next automatic</dt>
                            <dd className="mt-0.5 text-ink">{nextAutomaticLabel(item.next_automatic)}</dd>
                          </div>
                          <div>
                            <dt className="text-xs text-muted">Last reminder</dt>
                            <dd className="mt-0.5 text-ink">{lastReminderLabel(item)}</dd>
                          </div>
                          <div>
                            <dt className="text-xs text-muted">Manual reminder</dt>
                            <dd className={`mt-0.5 ${item.manual_available ? "text-success" : "text-muted"}`}>
                              {manualReminderLabel(item)}
                            </dd>
                          </div>
                        </dl>
                      </article>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {!upcoming.isPending && !upcoming.isError ? (
              <CanonicalPagination
                className="border-brand-line px-4 py-3 sm:px-5"
                page={upcomingData?.page ?? page}
                hasNext={upcomingData?.has_next ?? false}
                label="Upcoming reminder pages"
                disabled={upcoming.isFetching}
                onPageChange={movePage}
              />
            ) : null}
          </Panel>
        </>
      ) : (
        <>
          <SentFilters
            key={`sent:${searchParams.toString()}`}
            applied={{ kind: kind ?? "", delivery: delivery ?? "", from: fromDate, to: toDate }}
            onSubmit={applySentFilters}
            onClear={clearSentFilters}
          />
          <Panel aria-labelledby="sent-reminders-heading">
            <PanelHeader
              title="Sent reminders"
              titleId="sent-reminders-heading"
              context={
                activity.isFetching && !activity.isPending
                  ? "Refreshing sent reminders…"
                  : activityData && !activity.isError
                    ? describeResultPage({
                        count: activityItems.length,
                        page: activityData.page,
                        hasNext: activityData.has_next,
                        noun: { one: "reminder", other: "reminders" },
                        filtered: hasSentFilters,
                      })
                    : null
              }
            />
            {activity.isPending ? (
              <RowsSkeleton label="Loading sent reminders…" framed={false} />
            ) : activity.isError ? (
              <PanelMessage
                role="alert"
                tone="danger"
                action={
                  <Button variant="secondary" onClick={() => void activity.refetch()}>
                    Retry
                  </Button>
                }
              >
                {appointmentErrorMessage(activity.error, "Couldn't load sent reminders. Try again.")}
              </PanelMessage>
            ) : activityItems.length === 0 ? (
              <PanelMessage
                action={
                  hasSentFilters ? (
                    <Button variant="secondary" onClick={clearSentFilters}>
                      Clear filters
                    </Button>
                  ) : undefined
                }
              >
                {hasSentFilters
                  ? "No sent reminders match the selected filters."
                  : "No reminders have been sent for the Appointments you manage yet."}
              </PanelMessage>
            ) : (
              <>
                <div
                  className={`${dataTable.scroll} hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus md:block`}
                  role="region"
                  aria-label="Sent reminders. Scroll horizontally to view all columns."
                  tabIndex={0}
                >
                  <table className={`${dataTable.table} min-w-[1150px]`}>
                    <caption className="sr-only">Sent reminders</caption>
                    <thead className={dataTable.head}>
                      <tr>
                        <th scope="col" className={dataTable.headerCell}>Reminder</th>
                        <th scope="col" className={dataTable.headerCell}>Sent</th>
                        <th scope="col" className={dataTable.headerCell}>Appointment</th>
                        <th scope="col" className={dataTable.headerCell}>Student</th>
                        <th scope="col" className={dataTable.headerCell}>Scheduled start</th>
                        <th scope="col" className={dataTable.headerCell}>Sent by</th>
                        <th scope="col" className={dataTable.headerCell}>In-app</th>
                        <th scope="col" className={dataTable.headerCell}>Email</th>
                        <th scope="col" className={dataTable.headerCell}>Browser push</th>
                      </tr>
                    </thead>
                    <tbody className={dataTable.body}>
                      {activityItems.map((entry) => (
                        <tr key={entry.id} className={dataTable.row}>
                          <th scope="row" className={`${dataTable.cell} font-normal`}>
                            <span className="font-medium text-ink">{reminderKindLabel(entry.kind)}</span>
                            {entry.is_current ? null : (
                              <span className="mt-1 block text-xs text-warning">Superseded by reschedule</span>
                            )}
                          </th>
                          <td className={`${dataTable.cell} text-ink`}>
                            <time dateTime={entry.issued_at}>{formatInstitutionalDateTime(entry.issued_at)}</time>
                          </td>
                          <td className={dataTable.cell}>
                            <Link
                              href={`/portal/appointments/${entry.appointment_id}`}
                              className="font-mono text-xs font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                            >
                              {entry.reference_code}
                            </Link>
                          </td>
                          <td className={`${dataTable.cell} font-medium text-ink`}>{entry.student_name}</td>
                          <td className={`${dataTable.cell} text-ink`}>
                            <time dateTime={entry.scheduled_start}>
                              {formatInstitutionalDateTime(entry.scheduled_start)}
                            </time>
                          </td>
                          <td className={`${dataTable.cell} text-ink`}>{reminderIssuerLabel(entry.issued_by)}</td>
                          <td className={`${dataTable.cell} text-ink`}>{inAppStateLabel(entry.in_app)}</td>
                          <td className={`${dataTable.cell} text-ink`}>{deliveryStateLabel(entry.email)}</td>
                          <td className={`${dataTable.cell} text-ink`}>{deliveryStateLabel(entry.push)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <ul className="divide-y divide-border md:hidden">
                  {activityItems.map((entry) => (
                    <li key={entry.id} className="px-4 py-4">
                      <article>
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h3 className="font-semibold text-ink">{reminderKindLabel(entry.kind)}</h3>
                            <p className="mt-0.5 text-sm text-muted">
                              <time dateTime={entry.issued_at}>
                                {formatInstitutionalDateTime(entry.issued_at)}
                              </time>
                            </p>
                          </div>
                          <p className="text-sm text-ink">{reminderIssuerLabel(entry.issued_by)}</p>
                        </div>
                        {entry.is_current ? null : (
                          <p className="mt-1 text-xs text-warning">Superseded by reschedule</p>
                        )}
                        <div className="mt-2 min-w-0">
                          <Link
                            href={`/portal/appointments/${entry.appointment_id}`}
                            className="break-all font-mono text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                          >
                            {entry.reference_code}
                          </Link>
                          <p className="mt-1 break-words font-medium text-ink">{entry.student_name}</p>
                        </div>
                        <dl className="mt-3 grid gap-x-5 gap-y-2 text-sm sm:grid-cols-2">
                          <div>
                            <dt className="text-xs text-muted">Scheduled start</dt>
                            <dd className="mt-0.5 text-ink">
                              <time dateTime={entry.scheduled_start}>
                                {formatInstitutionalDateTime(entry.scheduled_start)}
                              </time>
                            </dd>
                          </div>
                          {reminderTransports.map((transport) => (
                            <div key={transport.key}>
                              <dt className="text-xs text-muted">{transport.label}</dt>
                              <dd className="mt-0.5 text-ink">
                                {transport.key === "in_app"
                                  ? inAppStateLabel(entry.in_app)
                                  : deliveryStateLabel(entry[transport.key])}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      </article>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {!activity.isPending && !activity.isError ? (
              <CanonicalPagination
                className="border-brand-line px-4 py-3 sm:px-5"
                page={activityData?.page ?? page}
                hasNext={activityData?.has_next ?? false}
                label="Sent reminder pages"
                disabled={activity.isFetching}
                onPageChange={movePage}
              />
            ) : null}
          </Panel>
        </>
      )}
    </section>
  );
}

export function RemindersPage() {
  const { user } = usePortalSession();
  const canManage = getAppointmentAccess(user).canManage;
  const canViewTracer = getGraduateTracerAccess(user).canViewOperational;
  if (!canManage && !canViewTracer) {
    return (
      <WorkspaceUnavailable title="Reminder access">
        You don&apos;t have access to reminders.
      </WorkspaceUnavailable>
    );
  }
  return (
    <>
      {canManage ? <RemindersWorkspace /> : <PageHeader title="Reminders" />}
      {canViewTracer ? <GraduateTracerReminders /> : null}
    </>
  );
}

export function RemindersSkeleton() {
  return <RowsSkeleton label="Loading reminders…" />;
}

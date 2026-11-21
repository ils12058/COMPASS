"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelSection } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { Select } from "@/components/ui/select";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getAppointmentsListCounselorApprovalsQueryKey,
  getAppointmentsListCounselorRequestsQueryKey,
  useAppointmentsChangeCounselorApproval,
  useAppointmentsEndCounselorApproval,
  useAppointmentsListCounselorApprovals,
  useAppointmentsListCounselorRequests,
} from "@/lib/api/generated/appointments/appointments";
import {
  CounselorBookingRequestState,
  type HeadCounselorApprovalItem,
} from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

import { getAppointmentAccess } from "./appointments-access";
import {
  AppointmentsLocalNavigation,
  AppointmentsPageHeading,
  AppointmentsUnavailable,
} from "./appointments-shared";
import {
  counselorRequestErrorMessage,
  counselorRequestStateLabel,
  isCounselorRequestStaleError,
  studentCollegeLabel,
} from "./counselor-request-presentation";

type ActiveTab = "requests" | "approvals";

export function HeadCounselorRequestsPage() {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);

  if (!access.canReviewCounselorRequests) {
    return (
      <section aria-labelledby="counselor-requests-unavailable-heading">
        <AppointmentsLocalNavigation />
        <AppointmentsUnavailable>
          Only the Head Guidance Counselor can review counselor requests and approvals.
        </AppointmentsUnavailable>
      </section>
    );
  }

  return <HeadCounselorRequestsWorkspace />;
}

function HeadCounselorRequestsWorkspace() {
  const [tab, setTab] = useState<ActiveTab>("requests");

  return (
    <section aria-labelledby="counselor-requests-heading" className="space-y-5">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="counselor-requests-heading"
        title="Counselor requests and approvals"
        description="Review student requests for a different counselor and manage current approvals."
      />

      <div role="tablist" aria-label="Counselor requests sections" className="flex flex-wrap gap-2">
        <Button
          type="button"
          role="tab"
          aria-selected={tab === "requests"}
          variant={tab === "requests" ? "primary" : "secondary"}
          onClick={() => setTab("requests")}
        >
          Requests
        </Button>
        <Button
          type="button"
          role="tab"
          aria-selected={tab === "approvals"}
          variant={tab === "approvals" ? "primary" : "secondary"}
          onClick={() => setTab("approvals")}
        >
          Current approvals
        </Button>
      </div>

      {tab === "requests" ? <RequestsPanel /> : <ApprovalsPanel />}
    </section>
  );
}

function RequestsPanel() {
  const [stateFilter, setStateFilter] = useState<"PENDING" | "ALL">("PENDING");
  const [page, setPage] = useState(1);

  const query = useAppointmentsListCounselorRequests(
    {
      ...(stateFilter === "PENDING" ? { state: CounselorBookingRequestState.PENDING } : {}),
      page,
      page_size: 20,
    },
    { query: { retry: false, refetchOnWindowFocus: true } },
  );

  const data = query.data?.data;
  const items = data?.items ?? [];

  return (
    <Panel>
      <PanelSection title="Student requests" titleId="head-counselor-requests-list-heading">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant={stateFilter === "PENDING" ? "primary" : "secondary"}
            onClick={() => {
              setStateFilter("PENDING");
              setPage(1);
            }}
          >
            Waiting for review
          </Button>
          <Button
            type="button"
            variant={stateFilter === "ALL" ? "primary" : "secondary"}
            onClick={() => {
              setStateFilter("ALL");
              setPage(1);
            }}
          >
            All requests
          </Button>
        </div>

        {query.isPending ? (
          <RowsSkeleton label="Loading counselor requests…" framed={false} />
        ) : query.isError ? (
          <Notice
            role="alert"
            tone="danger"
            action={
              <Button variant="secondary" onClick={() => void query.refetch()}>
                Retry
              </Button>
            }
          >
            {counselorRequestErrorMessage(query.error, "Couldn't load counselor requests. Try again.")}
          </Notice>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted">
            {stateFilter === "PENDING"
              ? "No student requests are waiting for your review."
              : "No counselor requests have been submitted yet."}
          </p>
        ) : (
          <>
            <ul className="divide-y divide-border rounded-sm border border-border">
              {items.map((item) => (
                <li
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-4 px-4 py-3.5"
                >
                  <div className="min-w-0 space-y-1">
                    <p className="font-semibold text-ink">
                      {item.student.display_name}
                      {item.student.institutional_id ? (
                        <span className="ml-2 text-xs font-normal text-muted">
                          {item.student.institutional_id}
                        </span>
                      ) : null}
                    </p>
                    <p className="text-sm text-muted">
                      {studentCollegeLabel(item.student)} · Default:{" "}
                      {item.default_counselor?.display_name ?? "None assigned"}
                    </p>
                    <p className="text-xs text-muted">
                      {counselorRequestStateLabel(item.state)} · Requested:{" "}
                      {item.preferred_counselor?.display_name ?? "No preference"} · Submitted{" "}
                      {formatInstitutionalDateTime(item.created_at)}
                    </p>
                  </div>
                  <Link
                    href={`/portal/appointments/counselor-requests/${item.id}`}
                    className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-3.5 text-sm font-semibold text-brand hover:bg-brand-wash focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    {item.state === CounselorBookingRequestState.PENDING
                      ? "Review request"
                      : "View details"}
                  </Link>
                </li>
              ))}
            </ul>
            {data ? (
              <CanonicalPagination
                page={data.page}
                hasNext={data.has_next}
                label="Counselor request pages"
                onPageChange={setPage}
              />
            ) : null}
          </>
        )}
      </PanelSection>
    </Panel>
  );
}

function ApprovalsPanel() {
  const queryClient = useQueryClient();
  const [includeEnded, setIncludeEnded] = useState(false);
  const [page, setPage] = useState(1);
  const [changing, setChanging] = useState<HeadCounselorApprovalItem | null>(null);
  const [nextCounselorId, setNextCounselorId] = useState("");
  const [ending, setEnding] = useState<HeadCounselorApprovalItem | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const query = useAppointmentsListCounselorApprovals(
    { include_ended: includeEnded, page, page_size: 20 },
    { query: { retry: false, refetchOnWindowFocus: true } },
  );
  const changeMutation = useAppointmentsChangeCounselorApproval({ mutation: { retry: false } });
  const endMutation = useAppointmentsEndCounselorApproval({ mutation: { retry: false } });

  const data = query.data?.data;
  const items = data?.items ?? [];
  const availableCounselors = data?.available_counselors ?? [];
  const canManage = data?.can_manage ?? false;

  async function refreshAll() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getAppointmentsListCounselorApprovalsQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getAppointmentsListCounselorRequestsQueryKey() }),
      invalidateGuidanceWork(queryClient),
    ]);
  }

  async function confirmChange() {
    if (!changing) return;
    if (!nextCounselorId) {
      setActionError("Choose a counselor.");
      return;
    }
    setActionError(null);
    try {
      await changeMutation.mutateAsync({
        approvalId: changing.id,
        data: {
          counselor_id: nextCounselorId,
          expected_version: changing.version,
        },
      });
      const chosenName =
        availableCounselors.find((c) => c.id === nextCounselorId)?.display_name ?? "the selected counselor";
      setChanging(null);
      setNextCounselorId("");
      setActionNotice(
        `Updated approval for ${changing.student.display_name} to ${chosenName}. The student has been notified.`,
      );
      await refreshAll();
    } catch (caught) {
      setActionError(
        counselorRequestErrorMessage(caught, "Couldn't change this approval. Try again."),
      );
      if (isCounselorRequestStaleError(caught)) {
        setChanging(null);
        await query.refetch();
      }
    }
  }

  async function confirmEnd() {
    if (!ending) return;
    setActionError(null);
    try {
      await endMutation.mutateAsync({
        approvalId: ending.id,
        data: { expected_version: ending.version },
      });
      setEnding(null);
      setActionNotice(
        `Ended approval for ${ending.student.display_name}. They now return to their default counselor and have been notified.`,
      );
      await refreshAll();
    } catch (caught) {
      setActionError(
        counselorRequestErrorMessage(caught, "Couldn't end this approval. Try again."),
      );
      if (isCounselorRequestStaleError(caught)) {
        setEnding(null);
        await query.refetch();
      }
    }
  }

  return (
    <>
      {actionNotice ? (
        <Notice role="status" tone="success">
          {actionNotice}
        </Notice>
      ) : null}
      {actionError && !changing && !ending ? (
        <Notice role="alert" tone="danger">
          {actionError}
        </Notice>
      ) : null}

      <Panel>
        <PanelSection title="Standing counselor approvals" titleId="head-counselor-approvals-heading">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted">
              An approval stays active until you change the approved counselor or end it.
            </p>
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                className="h-4 w-4 accent-brand"
                checked={includeEnded}
                onChange={(event) => {
                  setIncludeEnded(event.target.checked);
                  setPage(1);
                }}
              />
              Show ended approvals
            </label>
          </div>

          {query.isPending ? (
            <RowsSkeleton label="Loading counselor approvals…" framed={false} />
          ) : query.isError ? (
            <Notice
              role="alert"
              tone="danger"
              action={
                <Button variant="secondary" onClick={() => void query.refetch()}>
                  Retry
                </Button>
              }
            >
              {counselorRequestErrorMessage(query.error, "Couldn't load approvals. Try again.")}
            </Notice>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted">
              {includeEnded
                ? "No counselor approvals have been recorded yet."
                : "No active counselor approvals."}
            </p>
          ) : (
            <>
              <ul className="divide-y divide-border rounded-sm border border-border">
                {items.map((item) => {
                  const active = item.ended_at === null;
                  return (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-4 px-4 py-3.5"
                    >
                      <div className="min-w-0 space-y-1">
                        <p className="font-semibold text-ink">
                          {item.student.display_name}
                          {item.student.institutional_id ? (
                            <span className="ml-2 text-xs font-normal text-muted">
                              {item.student.institutional_id}
                            </span>
                          ) : null}
                        </p>
                        <p className="text-sm text-muted">
                          Approved counselor:{" "}
                          <strong className="font-semibold text-ink">
                            {item.counselor.display_name}
                          </strong>
                          {" · "}Default: {item.default_counselor?.display_name ?? "None assigned"}
                        </p>
                        <p className="text-xs text-muted">
                          {studentCollegeLabel(item.student)} · Approved{" "}
                          {formatInstitutionalDateTime(item.approved_at)}
                          {item.ended_at
                            ? ` · Ended ${formatInstitutionalDateTime(item.ended_at)}`
                            : ""}
                        </p>
                        {active && !item.counselor_is_active ? (
                          <p className="text-xs font-semibold text-warning">
                            This counselor is inactive. The student automatically falls back to
                            their default counselor.
                          </p>
                        ) : null}
                      </div>

                      {active && canManage ? (
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            onClick={() => {
                              setActionError(null);
                              setActionNotice(null);
                              setChanging(item);
                              setNextCounselorId("");
                            }}
                          >
                            Change counselor
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            onClick={() => {
                              setActionError(null);
                              setActionNotice(null);
                              setEnding(item);
                            }}
                          >
                            End approval
                          </Button>
                        </div>
                      ) : active ? (
                        <span className="text-xs text-muted">Active</span>
                      ) : (
                        <span className="text-xs text-muted">Ended</span>
                      )}
                    </li>
                  );
                })}
              </ul>
              {data ? (
                <CanonicalPagination
                  page={data.page}
                  hasNext={data.has_next}
                  label="Counselor approval pages"
                  onPageChange={setPage}
                />
              ) : null}
            </>
          )}
        </PanelSection>

        {!query.isPending && !query.isError && !canManage ? (
          <PanelBody className="border-t border-border">
            <Notice role="status">
              Changes to approvals require exactly one active Head Guidance Counselor. Contact the
              Guidance Office if another Head Guidance Counselor designation is active.
            </Notice>
          </PanelBody>
        ) : null}
      </Panel>

      <ConsequentialActionDialog
        open={changing !== null}
        title="Change approved counselor?"
        confirmLabel="Save change"
        pendingLabel="Saving…"
        pending={changeMutation.isPending}
        error={actionError}
        confirmDisabled={!nextCounselorId}
        onOpenChange={(next) => {
          if (!next) {
            setChanging(null);
            setActionError(null);
          }
        }}
        onConfirm={() => void confirmChange()}
        choices={
          <div className="grid gap-1.5">
            <Label htmlFor="change-approved-counselor">New approved counselor</Label>
            <Select
              id="change-approved-counselor"
              value={nextCounselorId}
              onChange={(event) => setNextCounselorId(event.target.value)}
              disabled={changeMutation.isPending}
            >
              <option value="">Choose a counselor…</option>
              {availableCounselors
                .filter((c) => c.id !== changing?.counselor.id)
                .map((counselor) => (
                  <option key={counselor.id} value={counselor.id}>
                    {counselor.display_name}
                  </option>
                ))}
            </Select>
          </div>
        }
      >
        {changing ? (
          <p>
            Update the approved counselor for <strong>{changing.student.display_name}</strong>{" "}
            (currently {changing.counselor.display_name}). Existing Appointments are not changed.
            The student will be notified.
          </p>
        ) : null}
      </ConsequentialActionDialog>

      <ConsequentialActionDialog
        open={ending !== null}
        title="End this counselor approval?"
        confirmLabel="End approval"
        pendingLabel="Ending…"
        variant="danger"
        pending={endMutation.isPending}
        error={actionError}
        onOpenChange={(next) => {
          if (!next) {
            setEnding(null);
            setActionError(null);
          }
        }}
        onConfirm={() => void confirmEnd()}
      >
        {ending ? (
          <p>
            End the approval allowing <strong>{ending.student.display_name}</strong> to book with{" "}
            <strong>{ending.counselor.display_name}</strong>? For new bookings, the student will
            return to their default counselor (
            {ending.default_counselor?.display_name ?? "none currently assigned"}). Existing
            Appointments are not changed. The student will be notified.
          </p>
        ) : null}
      </ConsequentialActionDialog>
    </>
  );
}

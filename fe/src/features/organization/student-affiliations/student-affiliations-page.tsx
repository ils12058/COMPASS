"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useOrganizationAction } from "@/features/organization/components/organization-action";
import { PeoplePicker } from "@/features/organization/components/people-picker";
import {
  PageHeading,
  QueryError,
  SearchField,
  StatusBadge,
  TableSkeleton,
  replaceQueryParam,
  selectClass,
} from "@/features/organization/components/organization-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getOrganizationListStudentAffiliationsQueryKey,
  useOrganizationListCampuses,
  useOrganizationListColleges,
  useOrganizationListStudentAffiliations,
  useOrganizationRemoveStudentAffiliation,
  useOrganizationSetStudentAffiliation,
} from "@/lib/api/generated/organization/organization";

function parsePage(value: string | null): number {
  const page = Number(value);
  return value && Number.isSafeInteger(page) && page > 0 ? page : 1;
}

export function StudentAffiliationsPage() {
  const { user } = usePortalSession();
  const canViewStructure = user.capabilities.includes("organization.structure.view");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const page = parsePage(searchParams.get("page"));
  const search = (searchParams.get("search") ?? "").slice(0, 200).trim();
  const campusId = searchParams.get("campus_id") ?? "";
  const collegeId = searchParams.get("college_id") ?? "";

  const campuses = useOrganizationListCampuses(
    {},
    { query: { enabled: canViewStructure, retry: false } },
  );
  const colleges = useOrganizationListColleges(
    {},
    { query: { enabled: canViewStructure, retry: false } },
  );
  const list = useOrganizationListStudentAffiliations(
    {
      page,
      page_size: 20,
      ...(search ? { search } : {}),
      ...(campusId ? { campus_id: campusId } : {}),
      ...(collegeId ? { college_id: collegeId } : {}),
    },
    { query: { retry: false } },
  );

  const setAffiliation = useOrganizationSetStudentAffiliation();
  const removeAffiliation = useOrganizationRemoveStudentAffiliation();
  const action = useOrganizationAction();

  const [dialog, setDialog] = useState<{
    studentId?: string;
    studentLabel?: string;
  } | null>(null);
  const [studentId, setStudentId] = useState("");
  const [targetCollegeId, setTargetCollegeId] = useState("");
  const [removal, setRemoval] = useState<{
    studentId: string;
    label: string;
  } | null>(null);

  const mutationPending =
    setAffiliation.isPending || removeAffiliation.isPending;

  async function refresh() {
    await queryClient.invalidateQueries({
      queryKey: getOrganizationListStudentAffiliationsQueryKey(),
    });
  }

  function openSet(
    existingStudentId?: string,
    studentLabel?: string,
    currentCollegeId = "",
  ) {
    action.setError(null);
    action.setNotice(null);
    setDialog({
      studentId: existingStudentId,
      studentLabel,
    });
    setStudentId(existingStudentId ?? "");
    setTargetCollegeId(currentCollegeId);
  }

  async function saveAffiliation() {
    if (!dialog || !studentId || !targetCollegeId) return;
    const target = dialog;
    const response = await action.run(
      () =>
        setAffiliation.mutateAsync({
          studentId,
          data: { college_id: targetCollegeId },
        }),
      "The Student affiliation could not be saved.",
      {
        onStepUpRequired: () => setDialog(null),
        onStepUpVerified: () => setDialog(target),
      },
    );
    if (!response) return;
    setDialog(null);
    action.setNotice(
      target.studentId ? "Student affiliation changed." : "Student affiliation set.",
    );
    await refresh();
  }

  async function confirmRemove() {
    if (!removal) return;
    const target = removal;
    const response = await action.run(
      () => removeAffiliation.mutateAsync({ studentId: target.studentId }),
      "The Student affiliation could not be removed.",
      {
        onStepUpRequired: () => setRemoval(null),
        onStepUpVerified: () => setRemoval(target),
      },
    );
    if (!response) return;
    setRemoval(null);
    action.setNotice("Student affiliation removed.");
    await refresh();
  }

  function updateFilter(key: string, value: string) {
    const current = new URLSearchParams(searchParams.toString());
    if (key === "campus_id") {
      if (value) current.set("campus_id", value);
      else current.delete("campus_id");
      current.delete("college_id");
      current.delete("page");
      const query = current.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
      return;
    }
    router.replace(
      replaceQueryParam(pathname, current, key, value),
      { scroll: false },
    );
  }

  function movePage(nextPage: number) {
    router.push(
      replaceQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        "page",
        String(nextPage),
        false,
      ),
    );
  }

  const structureReady =
    canViewStructure && Boolean(campuses.data) && Boolean(colleges.data);
  const filterColleges =
    colleges.data?.data.items.filter(
      (college) => !campusId || college.campus.id === campusId,
    ) ?? [];
  const activeColleges =
    colleges.data?.data.items.filter(
      (college) => college.is_active && college.campus.is_active,
    ) ?? [];

  return (
    <section>
      <PageHeading
        title="Student affiliations"
        action={
          structureReady ? (
            <Button onClick={() => openSet()}>Set affiliation</Button>
          ) : null
        }
      />

      {!canViewStructure ? (
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
          Your current access does not include Organization structure, so
          College choices for new or changed affiliations are unavailable.
          Existing affiliations are still listed.
        </p>
      ) : null}

      <div className="mt-8 flex flex-col gap-4 border-y border-border py-5 lg:flex-row lg:items-end">
        <SearchField
          label="Search Student affiliations"
          placeholder="Search by Student name or Institutional ID"
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:w-[30rem]">
          <div>
            <Label htmlFor="affiliation-campus-filter">Campus</Label>
            <select
              id="affiliation-campus-filter"
              className={`${selectClass} mt-2`}
              value={campusId}
              disabled={!structureReady}
              onChange={(event) =>
                updateFilter("campus_id", event.target.value)
              }
            >
              <option value="">All Campuses</option>
              {campuses.data?.data.items.map((campus) => (
                <option key={campus.id} value={campus.id}>
                  {campus.code} — {campus.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="affiliation-college-filter">College</Label>
            <select
              id="affiliation-college-filter"
              className={`${selectClass} mt-2`}
              value={collegeId}
              disabled={!structureReady}
              onChange={(event) =>
                updateFilter("college_id", event.target.value)
              }
            >
              <option value="">All Colleges</option>
              {filterColleges.map((college) => (
                <option key={college.id} value={college.id}>
                  {college.code} — {college.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {canViewStructure && (campuses.isError || colleges.isError) ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          Structure choices could not be loaded. The affiliation list remains
          available, but set/change controls are unavailable.
        </p>
      ) : null}
      {action.notice && !dialog && !removal ? action.messages : null}

      {list.isPending ? (
        <TableSkeleton />
      ) : list.isError ? (
        <div className="mt-6">
          <QueryError
            error={list.error}
            fallback="Student affiliations could not be loaded."
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : list.data.data.items.length === 0 ? (
        <p className="border-b border-border py-10 text-sm text-muted">
          No Student affiliations match the current filters.
        </p>
      ) : (
        <>
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[42rem] border-collapse text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Student
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Institutional ID
                  </th>
                  <th scope="col" className="px-4 py-3">
                    College
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Campus
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {list.data.data.items.map((item) => (
                  <tr key={item.student.id} className="border-t border-border">
                    <th scope="row" className="px-4 py-4">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-ink">
                            {item.student.full_name}
                          </span>
                          <StatusBadge active={item.student.is_active} />
                        </div>
                        <p className="text-xs text-muted">{item.student.email}</p>
                      </div>
                    </th>
                    <td className="px-4 py-4 font-medium text-ink">
                      {item.student.institutional_id ?? "—"}
                    </td>
                    <td className="px-4 py-4">{item.college.name}</td>
                    <td className="px-4 py-4">{item.college.campus.name}</td>
                    <td className="px-4 py-2">
                      <div className="flex justify-end gap-1">
                        {structureReady ? (
                          <Button
                            variant="quiet"
                            onClick={() =>
                              openSet(
                                item.student.id,
                                item.student.full_name,
                                item.college.id,
                              )
                            }
                          >
                            Change affiliation
                          </Button>
                        ) : null}
                        <Button
                          variant="quiet"
                          onClick={() =>
                            setRemoval({
                              studentId: item.student.id,
                              label: item.student.full_name,
                            })
                          }
                        >
                          Remove
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {page > 1 || list.data.data.has_next ? (
            <nav
              aria-label="Student affiliation pagination"
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
                Page {list.data.data.page}
              </span>
              <Button
                variant="secondary"
                disabled={!list.data.data.has_next}
                onClick={() => movePage(page + 1)}
              >
                Next
              </Button>
            </nav>
          ) : null}
        </>
      )}

      <Dialog
        open={Boolean(dialog)}
        onOpenChange={(open) => {
          if (mutationPending) return;
          if (!open) {
            setDialog(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <DialogContent className="max-w-xl">
          <DialogTitle>
            {dialog?.studentId ? "Change affiliation" : "Set affiliation"}
          </DialogTitle>
          <DialogDescription>
            Each Student has one College affiliation. Setting a new College
            replaces the current affiliation.
          </DialogDescription>
          <div className="mt-6 space-y-6">
            {dialog?.studentId ? (
              <div>
                <p className="text-sm font-semibold text-ink">Student</p>
                <p className="mt-2 rounded-md border border-border bg-surface-muted px-3 py-2 text-sm text-ink">
                  {dialog.studentLabel}
                </p>
              </div>
            ) : (
              <PeoplePicker
                id="student-affiliation-person-search"
                label="Student"
                role="STUDENT"
                enabled={Boolean(dialog)}
                value={studentId}
                onChange={setStudentId}
              />
            )}
            <div>
              <Label htmlFor="student-affiliation-college">College</Label>
              <select
                id="student-affiliation-college"
                required
                className={`${selectClass} mt-2`}
                value={targetCollegeId}
                onChange={(event) => setTargetCollegeId(event.target.value)}
              >
                <option value="">Select College</option>
                {activeColleges.map((college) => (
                  <option key={college.id} value={college.id}>
                    {college.code} — {college.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={mutationPending}
              onClick={() => setDialog(null)}
            >
              Cancel
            </Button>
            <Button
              disabled={mutationPending || !studentId || !targetCollegeId}
              onClick={() => void saveAffiliation()}
            >
              {setAffiliation.isPending
                ? "Saving…"
                : dialog?.studentId
                  ? "Change affiliation"
                  : "Set affiliation"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(removal)}
        onOpenChange={(open) => {
          if (mutationPending) return;
          if (!open) {
            setRemoval(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>Remove Student affiliation?</AlertDialogTitle>
          <AlertDialogDescription>
            {removal
              ? `COMPASS will no longer have a College affiliation for ${removal.label} until a new one is assigned.`
              : "The current College affiliation will be removed."}
          </AlertDialogDescription>
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={mutationPending}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant="danger"
              disabled={mutationPending}
              onClick={() => void confirmRemove()}
            >
              {removeAffiliation.isPending
                ? "Removing…"
                : "Remove affiliation"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      {action.stepUpDialog}
    </section>
  );
}

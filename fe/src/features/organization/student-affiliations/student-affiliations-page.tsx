"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useOrganizationAction } from "@/features/organization/components/organization-action";
import { PeoplePicker } from "@/features/organization/components/people-picker";
import {
  PageHeading,
  QueryError,
  SearchField,
  StatusBadge,
  TableSkeleton,
  replaceQueryParam,
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
import type { CollegeSummary, OrganizationPersonSummary } from "@/lib/api/generated/model";

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

  const [dialog, setDialog] = useState<{ student: OrganizationPersonSummary | null } | null>(null);
  const [studentId, setStudentId] = useState("");
  const [selectedStudent, setSelectedStudent] = useState<OrganizationPersonSummary | null>(null);
  const [targetCollegeId, setTargetCollegeId] = useState("");
  const [review, setReview] = useState<{
    student: OrganizationPersonSummary;
    currentCollege: CollegeSummary | null;
    newCollege: CollegeSummary;
  } | null>(null);
  const [removal, setRemoval] = useState<{
    student: OrganizationPersonSummary;
    college: CollegeSummary;
  } | null>(null);

  const selectedAffiliation = useOrganizationListStudentAffiliations(
    { student_id: studentId, page_size: 1 },
    { query: { enabled: Boolean(dialog && studentId), retry: false } },
  );
  const mutationPending =
    setAffiliation.isPending || removeAffiliation.isPending;

  async function refresh() {
    await queryClient.invalidateQueries({
      queryKey: getOrganizationListStudentAffiliationsQueryKey(),
    });
  }

  function openSet(
    student: OrganizationPersonSummary | null = null,
    currentCollegeId = "",
  ) {
    action.setError(null);
    action.setNotice(null);
    setDialog({ student });
    setStudentId(student?.id ?? "");
    setSelectedStudent(student);
    setTargetCollegeId(currentCollegeId);
  }

  function reviewAffiliation() {
    if (!selectedStudent || !targetCollegeId) return;
    const newCollege = activeColleges.find((college) => college.id === targetCollegeId);
    if (!newCollege) return;
    const currentCollege =
      selectedAffiliation.data?.data.items[0]?.college ??
      list.data?.data.items.find((item) => item.student.id === selectedStudent.id)?.college ??
      null;
    if (currentCollege?.id === newCollege.id) return;
    setReview({ student: selectedStudent, currentCollege, newCollege });
    setDialog(null);
    action.setError(null);
  }

  async function saveAffiliation() {
    if (!review) return;
    const target = review;
    const response = await action.run(
      () =>
        setAffiliation.mutateAsync({
          studentId: target.student.id,
          data: { college_id: target.newCollege.id },
        }),
      "The Student affiliation could not be saved.",
      {
        onStepUpRequired: () => setReview(null),
        onStepUpVerified: () => setReview(target),
      },
    );
    if (!response) return;
    setReview(null);
    action.setNotice(target.currentCollege ? "Student affiliation changed." : "Student affiliation set.");
    await refresh();
  }

  async function confirmRemove() {
    if (!removal) return;
    const target = removal;
    const response = await action.run(
      () => removeAffiliation.mutateAsync({ studentId: target.student.id }),
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
          Organization structure is unavailable to this account, so
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
            <Select
              id="affiliation-campus-filter"
              className="mt-2"
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
            </Select>
          </div>
          <div>
            <Label htmlFor="affiliation-college-filter">College</Label>
            <Select
              id="affiliation-college-filter"
              className="mt-2"
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
            </Select>
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
        <TableSkeleton label="Loading Student affiliations…" />
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
                              openSet(item.student, item.college.id)
                            }
                          >
                            Change affiliation
                          </Button>
                        ) : null}
                        <Button
                          variant="quiet"
                          onClick={() =>
                            setRemoval({
                              student: item.student,
                              college: item.college,
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
        </>
      )}
      {!list.isPending && !list.isError ? (
        <CanonicalPagination
          className="mt-5"
          page={list.data.data.page}
          hasNext={list.data.data.has_next}
          label="Student affiliation pagination"
          onPageChange={movePage}
        />
      ) : null}

      <Dialog
        open={Boolean(dialog)}
        onOpenChange={(open) => {
          if (!open) {
            setDialog(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <DialogContent className="max-w-xl" dismissible={!mutationPending}>
          <DialogTitle>{dialog?.student ? "Change affiliation" : "Set affiliation"}</DialogTitle>
          <DialogDescription>
            Choose a Student and College. The current and new affiliation will be reviewed before it is saved.
          </DialogDescription>
          <div className="mt-6 space-y-6">
            {dialog?.student ? (
              <div>
                <p className="text-sm font-semibold text-ink">Student</p>
                <div className="mt-2 border-l-2 border-support bg-support-soft/40 px-3 py-3 text-sm">
                  <p className="font-semibold text-ink">{dialog.student.full_name}</p>
                  <p className="mt-1 text-xs text-muted">
                    {dialog.student.institutional_id
                      ? `${dialog.student.institutional_id} · ${dialog.student.email}`
                      : dialog.student.email}
                  </p>
                </div>
              </div>
            ) : (
              <PeoplePicker
                id="student-affiliation-person-search"
                label="Student"
                role="STUDENT"
                enabled={Boolean(dialog)}
                value={studentId}
                selectedPerson={selectedStudent}
                onChange={(id, person) => {
                  setStudentId(id);
                  setSelectedStudent(person);
                }}
              />
            )}
            <div>
              <Label htmlFor="student-affiliation-college">College</Label>
              <Select
                id="student-affiliation-college"
                required
                className="mt-2"
                value={targetCollegeId}
                onChange={(event) => setTargetCollegeId(event.target.value)}
              >
                <option value="">Select College</option>
                {activeColleges.map((college) => (
                  <option key={college.id} value={college.id}>
                    {college.code} — {college.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          {selectedAffiliation.isError ? (
            <p role="alert" className="mt-4 text-sm text-danger">
              The Student&apos;s current affiliation could not be verified. Refresh and try again.
            </p>
          ) : null}
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="secondary" disabled={mutationPending} onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button
              disabled={
                mutationPending ||
                !selectedStudent ||
                !targetCollegeId ||
                selectedAffiliation.isPending ||
                selectedAffiliation.isError ||
                selectedAffiliation.data?.data.items[0]?.college.id === targetCollegeId
              }
              onClick={reviewAffiliation}
            >
              Review affiliation
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConsequentialActionDialog
        open={review !== null}
        title={review ? `${review.currentCollege ? "Change" : "Set"} ${review.student.full_name}'s College affiliation?` : "Review Student affiliation"}
        confirmLabel={review?.currentCollege ? "Change affiliation" : "Set affiliation"}
        pendingLabel={review?.currentCollege ? "Changing…" : "Setting…"}
        pending={mutationPending}
        error={action.error}
        onOpenChange={(open) => {
          if (!open) setReview(null);
        }}
        onConfirm={() => void saveAffiliation()}
      >
        {review ? (
          <>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div><dt className="text-muted">Student</dt><dd className="font-semibold text-ink">{review.student.full_name}</dd></div>
              <div><dt className="text-muted">Current College</dt><dd className="font-semibold text-ink">{review.currentCollege?.name ?? "Not assigned"}</dd></div>
              <div><dt className="text-muted">New College</dt><dd className="font-semibold text-ink">{review.newCollege.name}</dd></div>
            </dl>
            {review.currentCollege ? <p>Changing this affiliation replaces the current College relationship.</p> : null}
            <p>The College affiliation affects default institutional Counselor and routing behavior. Historical records are not rewritten by this change.</p>
          </>
        ) : null}
      </ConsequentialActionDialog>

      <ConsequentialActionDialog
        open={removal !== null}
        title={removal ? `Remove ${removal.student.full_name}'s College affiliation?` : "Remove Student affiliation?"}
        confirmLabel="Remove affiliation"
        pendingLabel="Removing…"
        pending={mutationPending}
        error={action.error}
        variant="danger"
        onOpenChange={(open) => {
          if (!open) {
            setRemoval(null);
            action.setError(null);
          }
        }}
        onConfirm={() => void confirmRemove()}
      >
        <p>
          {removal
            ? `${removal.student.full_name} will no longer be affiliated with ${removal.college.name} until a new College is assigned. Default institutional routing may change. Historical records are not deleted.`
            : "The current College affiliation will be removed."}
        </p>
      </ConsequentialActionDialog>

      {action.stepUpDialog}
    </section>
  );
}

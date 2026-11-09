"use client";

import { Link2, Search, Upload } from "lucide-react";
import Link from "next/link";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { PageAction, PageActionLink } from "@/components/ui/page-action";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select } from "@/components/ui/select";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { useOrganizationAction } from "@/features/organization/components/organization-action";
import { PeoplePicker } from "@/features/organization/components/people-picker";
import {
  PageHeading,
  PanelQueryError,
  StatusBadge,
  TableSkeleton,
  replaceQueryParam,
} from "@/features/organization/components/organization-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  canImportStudentAcademics,
  canManageStudentAcademics,
} from "@/features/student-academics/student-academics-access";
import {
  getStudentAcademicsListPlacementsQueryKey,
  useStudentAcademicsClearPlacement,
  useStudentAcademicsListPlacements,
  useStudentAcademicsSetPlacement,
} from "@/lib/api/generated/student-academics/student-academics";
import {
  useOrganizationListCampuses,
  useOrganizationListColleges,
} from "@/lib/api/generated/organization/organization";
import type {
  CollegeSummary,
  OrganizationPersonSummary,
} from "@/lib/api/generated/model";

function parsePage(value: string | null): number {
  const page = Number(value);
  return value && Number.isSafeInteger(page) && page > 0 ? page : 1;
}

export function StudentAcademicRecordsPage() {
  const { user } = usePortalSession();
  const canManage = canManageStudentAcademics(user);
  const canImport = canImportStudentAcademics(user);
  const canViewStructure = user.capabilities.includes("organization.structure.view");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const page = parsePage(searchParams.get("page"));
  const search = (searchParams.get("search") ?? "").slice(0, 200).trim();
  // URL search owns the applied query. A self-issued acknowledgement must leave newer
  // typing alone; an external search change adopts the URL. Popstate explicitly restores
  // history, even when its term also occurred among our pending navigations.
  const [searchDraft, setSearchDraft] = useState({
    applied: search,
    value: search,
    issued: [] as string[],
  });
  if (searchDraft.applied !== search) {
    const acknowledgement = searchDraft.issued.indexOf(search);
    setSearchDraft({
      applied: search,
      value: acknowledgement >= 0 ? searchDraft.value : search,
      issued: acknowledgement >= 0 ? searchDraft.issued.slice(acknowledgement + 1) : [],
    });
  }
  const searchValue = searchDraft.value;
  const searchTimer = useRef<number | null>(null);

  function cancelPendingSearch() {
    if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
    searchTimer.current = null;
  }

  useEffect(() => {
    const restore = () => {
      if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
      searchTimer.current = null;
      const value = (new URLSearchParams(window.location.search).get("search") ?? "").slice(0, 200).trim();
      setSearchDraft({ applied: value, value, issued: [] });
    };
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);

  useEffect(() => {
    const trimmed = searchValue.trim();
    if (trimmed === search) return;
    searchTimer.current = window.setTimeout(() => {
      searchTimer.current = null;
      const next = new URLSearchParams(searchParams.toString());
      if (trimmed) next.set("search", trimmed);
      else next.delete("search");
      next.delete("page");
      setSearchDraft((draft) => ({ ...draft, issued: [...draft.issued, trimmed] }));
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    }, 350);
    return () => {
      if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
      searchTimer.current = null;
    };
  }, [pathname, router, search, searchParams, searchValue]);

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
  const list = useStudentAcademicsListPlacements(
    {
      page,
      page_size: 20,
      ...(search ? { search } : {}),
      ...(campusId ? { campus_id: campusId } : {}),
      ...(collegeId ? { college_id: collegeId } : {}),
    },
    { query: { retry: false } },
  );

  const setPlacement = useStudentAcademicsSetPlacement();
  const clearPlacement = useStudentAcademicsClearPlacement();
  const action = useOrganizationAction();

  const [dialog, setDialog] = useState<{ student: OrganizationPersonSummary | null } | null>(null);
  const [studentId, setStudentId] = useState("");
  const [selectedStudent, setSelectedStudent] = useState<OrganizationPersonSummary | null>(null);
  const [targetCollegeId, setTargetCollegeId] = useState("");
  const [openRecord, setOpenRecord] = useState(false);
  const [recordStudentId, setRecordStudentId] = useState("");
  const [recordStudent, setRecordStudent] = useState<OrganizationPersonSummary | null>(null);
  const [review, setReview] = useState<{
    student: OrganizationPersonSummary;
    currentCollege: CollegeSummary | null;
    newCollege: CollegeSummary;
  } | null>(null);
  const [removal, setRemoval] = useState<{
    student: OrganizationPersonSummary;
    college: CollegeSummary;
  } | null>(null);

  const selectedPlacement = useStudentAcademicsListPlacements(
    { student_id: studentId, page_size: 1 },
    { query: { enabled: Boolean(dialog && studentId), retry: false } },
  );
  const mutationPending = setPlacement.isPending || clearPlacement.isPending;

  async function refresh() {
    await queryClient.invalidateQueries({
      queryKey: getStudentAcademicsListPlacementsQueryKey(),
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

  function reviewPlacement() {
    if (!selectedStudent || !targetCollegeId) return;
    const newCollege = activeColleges.find((college) => college.id === targetCollegeId);
    if (!newCollege) return;
    const currentCollege =
      selectedPlacement.data?.data.items[0]?.college ??
      list.data?.data.items.find((item) => item.student.id === selectedStudent.id)?.college ??
      null;
    if (currentCollege?.id === newCollege.id) return;
    setReview({ student: selectedStudent, currentCollege, newCollege });
    setDialog(null);
    action.setError(null);
  }

  async function savePlacement() {
    if (!review) return;
    const target = review;
    const response = await action.run(
      () =>
        setPlacement.mutateAsync({
          studentId: target.student.id,
          data: { college_id: target.newCollege.id },
        }),
      "Couldn't save the Student placement. Try again.",
      {
        onStepUpRequired: () => setReview(null),
      },
    );
    if (!response) return;
    setReview(null);
    action.setNotice(target.currentCollege ? "Student placement updated." : "Student placement assigned.");
    await refresh();
  }

  async function confirmClear() {
    if (!removal) return;
    const target = removal;
    const response = await action.run(
      () => clearPlacement.mutateAsync({ studentId: target.student.id }),
      "Couldn't clear the Student placement. Try again.",
      {
        onStepUpRequired: () => setRemoval(null),
      },
    );
    if (!response) return;
    setRemoval(null);
    action.setNotice("Student placement cleared.");
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

  const hasFilters = Boolean(search || campusId || collegeId);
  const listPage = list.data?.data;

  return (
    <section aria-labelledby="student-academic-records-heading">
      <PageHeading
        title="Student academic records"
        headingId="student-academic-records-heading"
        description={
          !canViewStructure
            ? "You don't have access to organization structure. You can view current placements, but adding or changing placements requires access to College choices."
            : undefined
        }
        action={
          <>
            {canManage && structureReady ? (
              <PageAction icon={Link2} label="Assign" labelDetail="placement" onClick={() => openSet()} />
            ) : null}
            {canImport ? (
              <PageActionLink
                href="/portal/organization/student-academics/import"
                icon={Upload}
                label="Import"
                labelDetail="academic roster"
                variant="secondary"
              />
            ) : null}
            <PageAction
              icon={Search}
              label="Open record"
              variant="secondary"
              onClick={() => {
                setRecordStudentId("");
                setRecordStudent(null);
                setOpenRecord(true);
              }}
            />
          </>
        }
      />

      {/* The search applies as you type and the structure choices apply on change. */}
      <FloatingListTools
        label="Student placement search and filters"
        filterCount={[campusId, collegeId].filter(Boolean).length}
        clear={hasFilters ? (
          <Button variant="quiet" onClick={() => {
            cancelPendingSearch();
            setSearchDraft((draft) => ({ ...draft, value: "", issued: [...draft.issued, ""] }));
            router.replace(pathname, { scroll: false });
          }}>
            Clear filters
          </Button>
        ) : undefined}
        filters={<>
        <FilterField label="Campus" htmlFor="placement-campus-filter">
          <Select
            id="placement-campus-filter"
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
        </FilterField>
        <FilterField label="College" htmlFor="placement-college-filter">
          <Select
            id="placement-college-filter"
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
        </FilterField>
        </>}
      >
        <ListSearchField
          id="organization-search" maxLength={200} value={searchValue}
          onChange={(event) => setSearchDraft((draft) => ({ ...draft, value: event.target.value }))}
          label="Search Student placements"
          placeholder="Search by Student name or institutional ID"
        />
      </FloatingListTools>

      {canViewStructure && (campuses.isError || colleges.isError) ? (
        <Notice role="alert" tone="warning" className="mb-5">
          Couldn&apos;t load Campus, College and Program choices. You can view placements; retry loading the choices before adding or changing a placement.
        </Notice>
      ) : null}
      {action.notice && !dialog && !removal ? action.messages : null}

      <Panel aria-labelledby="student-placements-heading">
        <PanelHeader
          title="Student placements"
          titleId="student-placements-heading"
          context={
            list.isFetching && !list.isPending
              ? "Refreshing Student placements…"
              : listPage && !list.isError
                ? describeResultPage({
                    count: listPage.items.length,
                    page: listPage.page,
                    hasNext: listPage.has_next,
                    noun: { one: "Student placement", other: "Student placements" },
                    filtered: hasFilters,
                  })
                : null
          }
        />
        {list.isPending ? (
          <TableSkeleton label="Loading Student placements…" />
        ) : list.isError ? (
          <PanelQueryError
            error={list.error}
            fallback="Couldn't load Student placements. Try again."
            onRetry={() => void list.refetch()}
          />
        ) : list.data.data.items.length === 0 ? (
          <PanelMessage>
            {hasFilters
              ? "No Student placements match the current filters."
              : "No Student placements have been recorded."}
          </PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[52rem]`}>
              <caption className="sr-only">Student placements</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>
                    Student
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Institutional ID
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    College
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Campus
                  </th>
                  <th scope="col" className={`${dataTable.headerCell} text-right`}>
                    {canManage ? "Action" : ""}
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {list.data.data.items.map((item) => (
                  <tr key={item.student.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-normal`}>
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            href={`/portal/organization/student-academics/${item.student.id}`}
                            className="font-semibold text-ink underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                          >
                            {item.student.full_name}
                          </Link>
                          <StatusBadge active={item.student.is_active} />
                        </div>
                        <p className="text-xs text-muted">{item.student.email}</p>
                      </div>
                    </th>
                    <td className={`${dataTable.cell} font-medium text-ink`}>
                      {item.student.institutional_id ?? "—"}
                    </td>
                    <td className={dataTable.cell}>{item.college.name}</td>
                    <td className={dataTable.cell}>{item.college.campus.name}</td>
                    <td className={`${dataTable.cell} py-2`}>
                      <div className="flex justify-end gap-1">
                        {canManage && structureReady ? (
                          <Button
                            variant="quiet"
                            onClick={() =>
                              openSet(item.student, item.college.id)
                            }
                          >
                            Update placement
                          </Button>
                        ) : null}
                        {canManage ? (
                          <Button
                            variant="quiet"
                            onClick={() =>
                              setRemoval({
                                student: item.student,
                                college: item.college,
                              })
                            }
                          >
                            Clear placement
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!list.isPending && !list.isError ? (
          <CanonicalPagination
            className="border-brand-line px-4 py-3 sm:px-5"
            page={list.data.data.page}
            hasNext={list.data.data.has_next}
            label="Student placement pagination"
            onPageChange={movePage}
          />
        ) : null}
      </Panel>

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
          <DialogTitle>{dialog?.student ? "Update placement" : "Assign placement"}</DialogTitle>
          <DialogDescription>
            Choose a Student and College. The current and new placement will be reviewed before it is saved.
          </DialogDescription>
          <div className="mt-6 space-y-6">
            {dialog?.student ? (
              <div>
                <p className="text-sm font-semibold text-ink">Student</p>
                <div className="mt-2 rounded-sm border border-brand-line bg-brand-wash px-3 py-3 text-sm">
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
                id="student-placement-person-search"
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
              <Label htmlFor="student-placement-college">College</Label>
              <Select
                id="student-placement-college"
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
          {selectedPlacement.isError ? (
            <p role="alert" className="mt-4 text-sm text-danger">
              Couldn&apos;t verify the Student&apos;s current placement. Refresh and try again.
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
                selectedPlacement.isPending ||
                selectedPlacement.isError ||
                selectedPlacement.data?.data.items[0]?.college.id === targetCollegeId
              }
              onClick={reviewPlacement}
            >
              Review placement
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={openRecord}
        onOpenChange={(open) => {
          if (!open) {
            setOpenRecord(false);
            setRecordStudentId("");
            setRecordStudent(null);
          }
        }}
      >
        <DialogContent className="max-w-xl">
          <DialogTitle>Open Student record</DialogTitle>
          <DialogDescription>
            Choose a Student to open their academic record, including Students without a current
            placement and graduated Students.
          </DialogDescription>
          <div className="mt-6">
            <PeoplePicker
              id="student-academic-record-person-search"
              label="Student"
              role="STUDENT"
              enabled={openRecord}
              value={recordStudentId}
              selectedPerson={recordStudent}
              onChange={(id, person) => {
                setRecordStudentId(id);
                setRecordStudent(person);
              }}
            />
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpenRecord(false)}>
              Cancel
            </Button>
            <Button
              disabled={!recordStudent}
              onClick={() =>
                router.push(
                  `/portal/organization/student-academics/${recordStudentId}`,
                )
              }
            >
              Open record
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConsequentialActionDialog
        open={review !== null}
        title={review ? `${review.currentCollege ? "Update" : "Assign"} ${review.student.full_name}'s College placement?` : "Review Student placement"}
        confirmLabel={review?.currentCollege ? "Update placement" : "Assign placement"}
        pendingLabel={review?.currentCollege ? "Updating…" : "Assigning…"}
        pending={mutationPending}
        error={action.error}
        onOpenChange={(open) => {
          if (!open) setReview(null);
        }}
        onConfirm={() => void savePlacement()}
      >
        {review ? (
          <>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div><dt className="text-muted">Student</dt><dd className="font-semibold text-ink">{review.student.full_name}</dd></div>
              <div><dt className="text-muted">Current College</dt><dd className="font-semibold text-ink">{review.currentCollege?.name ?? "Not assigned"}</dd></div>
              <div><dt className="text-muted">New College</dt><dd className="font-semibold text-ink">{review.newCollege.name}</dd></div>
            </dl>
            {review.currentCollege ? <p>Updating this placement replaces the current College relationship.</p> : null}
            <p>This College placement changes which Counselor handles new work. Past records stay as they are.</p>
          </>
        ) : null}
      </ConsequentialActionDialog>

      <ConsequentialActionDialog
        open={removal !== null}
        title={removal ? `Clear ${removal.student.full_name}'s College placement?` : "Clear Student placement?"}
        confirmLabel="Clear placement"
        pendingLabel="Clearing…"
        pending={mutationPending}
        error={action.error}
        variant="danger"
        onOpenChange={(open) => {
          if (!open) {
            setRemoval(null);
            action.setError(null);
          }
        }}
        onConfirm={() => void confirmClear()}
      >
        <p>
          {removal
            ? `${removal.student.full_name} will no longer be placed in ${removal.college.name} until a new College is assigned. Default institutional routing may change. Historical records are not deleted.`
            : "The current College placement will be cleared."}
        </p>
      </ConsequentialActionDialog>

      {action.stepUpDialog}
    </section>
  );
}

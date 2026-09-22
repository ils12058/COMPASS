"use client";

import { FormEvent, useState } from "react";
import { Check, GraduationCap, Search, UserRound, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getOrganizationListStudentAffiliationsQueryKey,
  useOrganizationListCampuses,
  useOrganizationListColleges,
  useOrganizationListEligiblePeople,
  useOrganizationListStudentAffiliations,
  useOrganizationRemoveStudentAffiliation,
  useOrganizationSetStudentAffiliation,
} from "@/lib/api/generated/organization/organization";
import { OrganizationListEligiblePeopleRole } from "@/lib/api/generated/model";
import type { StudentAffiliationResponse } from "@/lib/api/generated/model";
import {
  AssignmentEmptyState,
  AssignmentListSkeleton,
  AssignmentPerson,
  AssignmentQueryError,
  AssignmentSection,
  OrganizationActionMessage,
} from "@/features/portal/admin/organization/assignments/portal-it-admin-organization-assignment-shared";
import {
  organizationAdminError,
  organizationSelectClassName,
} from "@/features/portal/admin/organization/portal-it-admin-organization-shared";

const PAGE_SIZE = 20;

export function PortalItAdminOrganizationStudentAffiliations() {
  const queryClient = useQueryClient();
  const [campusFilter, setCampusFilter] = useState("");
  const [collegeFilter, setCollegeFilter] = useState("");
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [studentDraftSearch, setStudentDraftSearch] = useState("");
  const [studentSearch, setStudentSearch] = useState("");
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [newCollegeId, setNewCollegeId] = useState("");
  const [collegeSelections, setCollegeSelections] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const campusesQuery = useOrganizationListCampuses(undefined, {
    query: { retry: false, staleTime: 30_000 },
  });
  const collegesQuery = useOrganizationListColleges(
    { campus_id: campusFilter || undefined },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const affiliationsQuery = useOrganizationListStudentAffiliations(
    {
      campus_id: campusFilter || undefined,
      college_id: collegeFilter || undefined,
      search: search || undefined,
      page,
      page_size: PAGE_SIZE,
    },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const studentsQuery = useOrganizationListEligiblePeople(
    {
      role: OrganizationListEligiblePeopleRole.STUDENT,
      search: studentSearch || undefined,
      page: 1,
      page_size: 25,
    },
    {
      query: {
        enabled: Boolean(studentSearch),
        retry: false,
        staleTime: 30_000,
      },
    },
  );
  const setAffiliation = useOrganizationSetStudentAffiliation();
  const removeAffiliation = useOrganizationRemoveStudentAffiliation();
  const campuses = campusesQuery.data?.data.items ?? [];
  const colleges = collegesQuery.data?.data.items ?? [];
  const affiliations = affiliationsQuery.data?.data.items ?? [];
  const students = studentsQuery.data?.data.items ?? [];
  const response = affiliationsQuery.data?.data;
  const isMutating = setAffiliation.isPending || removeAffiliation.isPending;
  const hasError = campusesQuery.isError || collegesQuery.isError || affiliationsQuery.isError || studentsQuery.isError;

  function submitAffiliationSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(draftSearch.trim());
  }

  function changeCampusFilter(value: string) {
    setCampusFilter(value);
    setCollegeFilter("");
    setPage(1);
  }

  function beginStudentSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelectedStudentId("");
    setNewCollegeId("");
    setStudentSearch(studentDraftSearch.trim());
  }

  function selectedCollegeId(affiliation: StudentAffiliationResponse) {
    return collegeSelections[affiliation.student.id] ?? affiliation.college.id;
  }

  async function saveNewAffiliation() {
    if (!selectedStudentId || !newCollegeId) {
      setError("Choose a student and a college before saving the affiliation.");
      return;
    }

    const student = students.find((item) => item.id === selectedStudentId);
    setError(null);
    setMessage(null);

    try {
      await setAffiliation.mutateAsync({
        studentId: selectedStudentId,
        data: { college_id: newCollegeId },
      });
      setSelectedStudentId("");
      setNewCollegeId("");
      setStudentDraftSearch("");
      setStudentSearch("");
      setMessage(`Affiliation saved${student ? ` for ${student.display_name}` : ""}.`);
      await queryClient.invalidateQueries({ queryKey: getOrganizationListStudentAffiliationsQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t save this student affiliation. Please try again."));
    }
  }

  async function saveExistingAffiliation(affiliation: StudentAffiliationResponse) {
    const collegeId = selectedCollegeId(affiliation);
    if (collegeId === affiliation.college.id) {
      setMessage("No change to save for this student.");
      return;
    }

    setError(null);
    setMessage(null);

    try {
      await setAffiliation.mutateAsync({
        studentId: affiliation.student.id,
        data: { college_id: collegeId },
      });
      setMessage(`Affiliation updated for ${affiliation.student.display_name}.`);
      await queryClient.invalidateQueries({ queryKey: getOrganizationListStudentAffiliationsQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t update this student affiliation. Please try again."));
    }
  }

  async function removeExistingAffiliation(affiliation: StudentAffiliationResponse) {
    if (!window.confirm(`Remove the college affiliation for ${affiliation.student.display_name}?`)) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      await removeAffiliation.mutateAsync({ studentId: affiliation.student.id });
      setCollegeSelections((current) => {
        const next = { ...current };
        delete next[affiliation.student.id];
        return next;
      });
      setMessage(`Affiliation removed for ${affiliation.student.display_name}.`);
      await queryClient.invalidateQueries({ queryKey: getOrganizationListStudentAffiliationsQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t remove this student affiliation. Please try again."));
    }
  }

  return (
    <AssignmentSection
      icon={GraduationCap}
      title="Student affiliations"
      description="Keep each student connected to the college used by organizational routing and support workflows."
    >
      <div className="space-y-5">
        <section className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
                <UserRound aria-hidden="true" className="size-4" />
              </span>
              <div>
                <h3 className="font-semibold">Add or move a student</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">Search eligible student accounts, then choose their college.</p>
              </div>
            </div>
            {selectedStudentId ? (
              <Button type="button" variant="ghost" size="icon-sm" aria-label="Clear student selection" onClick={() => { setSelectedStudentId(""); setNewCollegeId(""); }}>
                <X aria-hidden="true" />
              </Button>
            ) : null}
          </div>
          <form className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end" onSubmit={beginStudentSearch}>
            <div className="min-w-0 flex-1">
              <Label htmlFor="student-affiliation-person-search">Find a student</Label>
              <div className="relative mt-2">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input id="student-affiliation-person-search" className="h-10 pl-9" placeholder="Search by name or institutional email" value={studentDraftSearch} onChange={(event) => setStudentDraftSearch(event.target.value)} />
              </div>
            </div>
            <Button type="submit" variant="outline" className="h-10" disabled={!studentDraftSearch.trim()}>
              <Search aria-hidden="true" />
              Search students
            </Button>
          </form>
          {studentSearch ? (
            studentsQuery.isPending ? (
              <div className="mt-4 h-12 animate-pulse rounded-xl bg-muted" aria-label="Loading students" />
            ) : students.length ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {students.map((student) => (
                  <button
                    key={student.id}
                    type="button"
                    className={`rounded-xl border p-3 text-left transition-colors ${selectedStudentId === student.id ? "border-[var(--compass-brand-maroon)] bg-card" : "border-[var(--compass-border)] bg-card hover:bg-[var(--compass-surface-muted)]"}`}
                    onClick={() => setSelectedStudentId(student.id)}
                  >
                    <span className="flex items-start gap-2">
                      <UserRound aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-[var(--compass-brand-maroon)]" />
                      <span className="min-w-0"><span className="block break-words font-semibold">{student.display_name}</span><span className="mt-1 block text-xs text-muted-foreground">Select this student</span></span>
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">No eligible students matched that search.</p>
            )
          ) : null}
          {selectedStudentId ? (
            <div className="mt-4 flex flex-col gap-3 rounded-xl border border-[var(--compass-border)] bg-card p-3 sm:flex-row sm:items-end">
              <div className="min-w-0 flex-1">
                <Label htmlFor="new-student-affiliation-college">College</Label>
                <select id="new-student-affiliation-college" className={`${organizationSelectClassName} mt-2`} value={newCollegeId} onChange={(event) => setNewCollegeId(event.target.value)}>
                  <option value="">Choose a college</option>
                  {colleges.filter((college) => college.is_active).map((college) => (
                    <option key={college.id} value={college.id}>{college.name} · {college.campus.name}</option>
                  ))}
                </select>
              </div>
              <Button type="button" disabled={isMutating || !newCollegeId} onClick={() => void saveNewAffiliation()}>
                <Check aria-hidden="true" />
                {setAffiliation.isPending ? "Saving…" : "Save affiliation"}
              </Button>
            </div>
          ) : null}
        </section>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <form className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-end" onSubmit={submitAffiliationSearch}>
            <div className="min-w-0 flex-1">
              <Label htmlFor="student-affiliation-search">Search assigned students</Label>
              <Input id="student-affiliation-search" className="mt-2 h-10" placeholder="Name" value={draftSearch} onChange={(event) => setDraftSearch(event.target.value)} />
            </div>
            <Button type="submit" variant="outline" className="h-10"><Search aria-hidden="true" />Search</Button>
          </form>
          <div className="flex flex-wrap gap-2">
            <select aria-label="Filter affiliations by campus" className={organizationSelectClassName} value={campusFilter} onChange={(event) => changeCampusFilter(event.target.value)}>
              <option value="">All campuses</option>
              {campuses.map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}
            </select>
            <select aria-label="Filter affiliations by college" className={organizationSelectClassName} value={collegeFilter} onChange={(event) => { setCollegeFilter(event.target.value); setPage(1); }}>
              <option value="">All colleges</option>
              {colleges.map((college) => <option key={college.id} value={college.id}>{college.name}</option>)}
            </select>
          </div>
        </div>

        <OrganizationActionMessage error={error} message={message} />

        {hasError ? (
          <AssignmentQueryError
            onRetry={() => {
              void campusesQuery.refetch();
              void collegesQuery.refetch();
              void affiliationsQuery.refetch();
              if (studentSearch) void studentsQuery.refetch();
            }}
          />
        ) : affiliationsQuery.isPending ? (
          <AssignmentListSkeleton />
        ) : affiliations.length ? (
          <div className="space-y-3">
            {affiliations.map((affiliation) => (
              <article key={affiliation.student.id} className="rounded-2xl border border-[var(--compass-border)] bg-card p-4 shadow-sm sm:p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
                      <GraduationCap aria-hidden="true" className="size-5" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="break-words font-semibold"><AssignmentPerson person={affiliation.student} /></h3>
                      <p className="mt-1 text-sm text-muted-foreground">Current college: {affiliation.college.name}</p>
                      <Badge className="mt-2" variant="outline">{affiliation.college.campus.name}</Badge>
                    </div>
                  </div>
                  <div className="flex min-w-0 flex-col gap-2 lg:w-80">
                    <Label htmlFor={`student-college-${affiliation.student.id}`} className="text-xs uppercase tracking-[0.12em] text-muted-foreground">College</Label>
                    <div className="flex flex-col gap-2 sm:flex-row lg:flex-col xl:flex-row">
                      <select id={`student-college-${affiliation.student.id}`} className={organizationSelectClassName} value={selectedCollegeId(affiliation)} onChange={(event) => setCollegeSelections((current) => ({ ...current, [affiliation.student.id]: event.target.value }))}>
                        {colleges.map((college) => <option key={college.id} value={college.id}>{college.name}</option>)}
                      </select>
                      <Button type="button" disabled={isMutating} onClick={() => void saveExistingAffiliation(affiliation)}>
                        <Check aria-hidden="true" />
                        {setAffiliation.isPending ? "Saving…" : "Save"}
                      </Button>
                    </div>
                    <Button type="button" variant="ghost" size="sm" className="self-start" disabled={isMutating} onClick={() => void removeExistingAffiliation(affiliation)}>
                      Remove affiliation
                    </Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <AssignmentEmptyState
            title="No affiliations match"
            description={search || campusFilter || collegeFilter ? "Try a different search or filter." : "No student affiliations have been recorded yet."}
          />
        )}

        {response ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--compass-border)] pt-4">
            <p className="text-sm text-muted-foreground">Page {response.page}</p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button>
              <Button type="button" variant="outline" size="sm" disabled={!response.has_next} onClick={() => setPage((current) => current + 1)}>Next</Button>
            </div>
          </div>
        ) : null}
      </div>
    </AssignmentSection>
  );
}

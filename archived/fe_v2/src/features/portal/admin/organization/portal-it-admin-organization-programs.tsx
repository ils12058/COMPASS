"use client";

import { FormEvent, useState } from "react";
import { Check, GraduationCap, Pencil, Plus, Search, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getOrganizationListProgramsQueryKey,
  useOrganizationCreateProgram,
  useOrganizationDisableProgram,
  useOrganizationEnableProgram,
  useOrganizationListColleges,
  useOrganizationListPrograms,
  useOrganizationUpdateProgram,
} from "@/lib/api/generated/organization/organization";
import type { ProgramSummary } from "@/lib/api/generated/model";
import {
  OrganizationActionMessage,
  OrganizationEmptyState,
  OrganizationListSkeleton,
  OrganizationQueryError,
  OrganizationSection,
  OrganizationStatusBadge,
  organizationAdminError,
  organizationSelectClassName,
} from "@/features/portal/admin/organization/portal-it-admin-organization-shared";

type StatusFilter = "all" | "active" | "disabled";

const INITIAL_DRAFT = { collegeId: "", code: "", name: "" };

function getActiveFilter(value: StatusFilter) {
  if (value === "active") {
    return true;
  }

  if (value === "disabled") {
    return false;
  }

  return undefined;
}

export function PortalItAdminOrganizationPrograms({
  canManage,
}: {
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [collegeFilter, setCollegeFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createDraft, setCreateDraft] = useState(INITIAL_DRAFT);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState({ code: "", name: "" });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const collegesQuery = useOrganizationListColleges(undefined, {
    query: { retry: false, staleTime: 30_000 },
  });
  const programsQuery = useOrganizationListPrograms(
    {
      college_id: collegeFilter || undefined,
      search: search || undefined,
      is_active: getActiveFilter(status),
    },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const createProgram = useOrganizationCreateProgram();
  const updateProgram = useOrganizationUpdateProgram();
  const disableProgram = useOrganizationDisableProgram();
  const enableProgram = useOrganizationEnableProgram();
  const colleges = collegesQuery.data?.data.items ?? [];
  const programs = programsQuery.data?.data.items ?? [];
  const isMutating =
    createProgram.isPending ||
    updateProgram.isPending ||
    disableProgram.isPending ||
    enableProgram.isPending;

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearch(draftSearch.trim());
  }

  function beginEdit(program: ProgramSummary) {
    setEditingId(program.id);
    setEditDraft({ code: program.code, name: program.name });
    setError(null);
    setMessage(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDraft({ code: "", name: "" });
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      await createProgram.mutateAsync({
        data: {
          college_id: createDraft.collegeId,
          code: createDraft.code.trim(),
          name: createDraft.name.trim(),
        },
      });
      setCreateDraft(INITIAL_DRAFT);
      setShowCreate(false);
      setMessage("Program added.");
      await queryClient.invalidateQueries({ queryKey: getOrganizationListProgramsQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t add that program. Please review the details and try again."));
    }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>, programId: string) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      await updateProgram.mutateAsync({
        programId,
        data: {
          code: editDraft.code.trim(),
          name: editDraft.name.trim(),
        },
      });
      cancelEdit();
      setMessage("Program details updated.");
      await queryClient.invalidateQueries({ queryKey: getOrganizationListProgramsQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t update that program. Please try again."));
    }
  }

  async function toggleProgram(program: ProgramSummary) {
    const nextState = program.is_active ? "disable" : "enable";
    if (!window.confirm(`${nextState === "disable" ? "Disable" : "Enable"} ${program.name}?`)) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      if (program.is_active) {
        await disableProgram.mutateAsync({ programId: program.id });
      } else {
        await enableProgram.mutateAsync({ programId: program.id });
      }
      setMessage(`Program ${program.is_active ? "disabled" : "enabled"}.`);
      await queryClient.invalidateQueries({ queryKey: getOrganizationListProgramsQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t change that program status. Please try again."));
    }
  }

  return (
    <OrganizationSection
      icon={GraduationCap}
      title="Programs"
      description="Keep academic programs under the correct college so student affiliations and operational routing remain clear."
    >
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <form className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-end" onSubmit={submitSearch}>
            <div className="min-w-0 flex-1">
              <Label htmlFor="organization-program-search">Search programs</Label>
              <div className="relative mt-2">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="organization-program-search"
                  className="h-10 pl-9"
                  placeholder="Name or code"
                  value={draftSearch}
                  onChange={(event) => setDraftSearch(event.target.value)}
                />
              </div>
            </div>
            <Button type="submit" variant="outline" className="h-10">
              <Search aria-hidden="true" />
              Search
            </Button>
          </form>
          <div className="flex flex-wrap gap-2 sm:justify-end">
            <select
              aria-label="Filter programs by college"
              className={organizationSelectClassName}
              value={collegeFilter}
              onChange={(event) => setCollegeFilter(event.target.value)}
            >
              <option value="">All colleges</option>
              {colleges.map((college) => (
                <option key={college.id} value={college.id}>
                  {college.name}
                </option>
              ))}
            </select>
            <select
              aria-label="Program status"
              className={organizationSelectClassName}
              value={status}
              onChange={(event) => setStatus(event.target.value as StatusFilter)}
            >
              <option value="all">All statuses</option>
              <option value="active">Active only</option>
              <option value="disabled">Disabled only</option>
            </select>
            {canManage ? (
              <Button type="button" onClick={() => setShowCreate((current) => !current)}>
                <Plus aria-hidden="true" />
                Add program
              </Button>
            ) : null}
          </div>
        </div>

        <OrganizationActionMessage error={error} message={message} />

        {canManage && showCreate ? (
          <form className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:p-5" onSubmit={submitCreate}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">Add a program</h3>
                <p className="mt-1 text-sm text-muted-foreground">Choose the college that owns this program.</p>
              </div>
              <Button type="button" variant="ghost" size="icon-sm" aria-label="Close add program form" onClick={() => setShowCreate(false)}>
                <X aria-hidden="true" />
              </Button>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <div>
                <Label htmlFor="create-program-college">College</Label>
                <select id="create-program-college" className={`${organizationSelectClassName} mt-2`} value={createDraft.collegeId} onChange={(event) => setCreateDraft((current) => ({ ...current, collegeId: event.target.value }))} required>
                  <option value="">Choose a college</option>
                  {colleges.filter((college) => college.is_active).map((college) => (
                    <option key={college.id} value={college.id}>{college.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="create-program-code">Code</Label>
                <Input id="create-program-code" className="mt-2 h-10" value={createDraft.code} onChange={(event) => setCreateDraft((current) => ({ ...current, code: event.target.value }))} required />
              </div>
              <div>
                <Label htmlFor="create-program-name">Name</Label>
                <Input id="create-program-name" className="mt-2 h-10" value={createDraft.name} onChange={(event) => setCreateDraft((current) => ({ ...current, name: event.target.value }))} required />
              </div>
            </div>
            {colleges.length === 0 ? <p className="mt-3 text-sm text-[var(--compass-brand-maroon)]">Add an active college before creating a program.</p> : null}
            <div className="mt-4 flex justify-end">
              <Button type="submit" disabled={isMutating || colleges.filter((college) => college.is_active).length === 0}>
                {createProgram.isPending ? "Adding…" : "Add program"}
              </Button>
            </div>
          </form>
        ) : null}

        {collegesQuery.isError || programsQuery.isError ? (
          <OrganizationQueryError
            onRetry={() => {
              void collegesQuery.refetch();
              void programsQuery.refetch();
            }}
          />
        ) : programsQuery.isPending ? (
          <OrganizationListSkeleton />
        ) : programs.length ? (
          <div className="space-y-3">
            {programs.map((program) => (
              <article key={program.id} className="rounded-2xl border border-[var(--compass-border)] bg-card p-4 shadow-sm sm:p-5">
                {editingId === program.id ? (
                  <form className="space-y-4" onSubmit={(event) => void submitEdit(event, program.id)}>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <Label htmlFor={`edit-program-code-${program.id}`}>Code</Label>
                        <Input id={`edit-program-code-${program.id}`} className="mt-2 h-10" value={editDraft.code} onChange={(event) => setEditDraft((current) => ({ ...current, code: event.target.value }))} required />
                      </div>
                      <div>
                        <Label htmlFor={`edit-program-name-${program.id}`}>Name</Label>
                        <Input id={`edit-program-name-${program.id}`} className="mt-2 h-10" value={editDraft.name} onChange={(event) => setEditDraft((current) => ({ ...current, name: event.target.value }))} required />
                      </div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button type="button" variant="ghost" onClick={cancelEdit}>Cancel</Button>
                      <Button type="submit" disabled={isMutating}>
                        <Check aria-hidden="true" />
                        {updateProgram.isPending ? "Saving…" : "Save changes"}
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
                        <GraduationCap aria-hidden="true" className="size-5" />
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="break-words font-semibold">{program.name}</h3>
                          <Badge variant="outline">{program.code}</Badge>
                          <OrganizationStatusBadge active={program.is_active} />
                        </div>
                        <p className="mt-1 break-words text-sm text-muted-foreground">{program.college.name} · {program.college.campus.name}</p>
                      </div>
                    </div>
                    {canManage ? (
                      <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                        <Button type="button" size="sm" variant="outline" onClick={() => beginEdit(program)}>
                          <Pencil aria-hidden="true" />
                          Edit
                        </Button>
                        <Button type="button" size="sm" variant="ghost" disabled={isMutating} onClick={() => void toggleProgram(program)}>
                          {program.is_active ? "Disable" : "Enable"}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                )}
              </article>
            ))}
          </div>
        ) : (
          <OrganizationEmptyState
            title="No programs match"
            description={search || collegeFilter || status !== "all" ? "Try a different search, college, or status filter." : "Add the first program under an active college."}
            action={canManage && !showCreate ? <Button type="button" onClick={() => setShowCreate(true)}>Add program</Button> : undefined}
          />
        )}
      </div>
    </OrganizationSection>
  );
}

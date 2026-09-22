"use client";

import { FormEvent, useState } from "react";
import { Check, Pencil, Plus, School, Search, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getOrganizationListCollegesQueryKey,
  useOrganizationCreateCollege,
  useOrganizationDisableCollege,
  useOrganizationEnableCollege,
  useOrganizationListCampuses,
  useOrganizationListColleges,
  useOrganizationUpdateCollege,
} from "@/lib/api/generated/organization/organization";
import type { CollegeSummary } from "@/lib/api/generated/model";
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

const INITIAL_DRAFT = { campusId: "", code: "", name: "" };

function getActiveFilter(value: StatusFilter) {
  if (value === "active") {
    return true;
  }

  if (value === "disabled") {
    return false;
  }

  return undefined;
}

export function PortalItAdminOrganizationColleges({
  canManage,
}: {
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [campusFilter, setCampusFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createDraft, setCreateDraft] = useState(INITIAL_DRAFT);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState({ code: "", name: "" });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const campusesQuery = useOrganizationListCampuses(undefined, {
    query: { retry: false, staleTime: 30_000 },
  });
  const collegesQuery = useOrganizationListColleges(
    {
      campus_id: campusFilter || undefined,
      search: search || undefined,
      is_active: getActiveFilter(status),
    },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const createCollege = useOrganizationCreateCollege();
  const updateCollege = useOrganizationUpdateCollege();
  const disableCollege = useOrganizationDisableCollege();
  const enableCollege = useOrganizationEnableCollege();
  const campuses = campusesQuery.data?.data.items ?? [];
  const colleges = collegesQuery.data?.data.items ?? [];
  const isMutating =
    createCollege.isPending ||
    updateCollege.isPending ||
    disableCollege.isPending ||
    enableCollege.isPending;

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearch(draftSearch.trim());
  }

  function beginEdit(college: CollegeSummary) {
    setEditingId(college.id);
    setEditDraft({ code: college.code, name: college.name });
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
      await createCollege.mutateAsync({
        data: {
          campus_id: createDraft.campusId,
          code: createDraft.code.trim(),
          name: createDraft.name.trim(),
        },
      });
      setCreateDraft(INITIAL_DRAFT);
      setShowCreate(false);
      setMessage("College added.");
      await queryClient.invalidateQueries({ queryKey: getOrganizationListCollegesQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t add that college. Please review the details and try again."));
    }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>, collegeId: string) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      await updateCollege.mutateAsync({
        collegeId,
        data: {
          code: editDraft.code.trim(),
          name: editDraft.name.trim(),
        },
      });
      cancelEdit();
      setMessage("College details updated.");
      await queryClient.invalidateQueries({ queryKey: getOrganizationListCollegesQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t update that college. Please try again."));
    }
  }

  async function toggleCollege(college: CollegeSummary) {
    const nextState = college.is_active ? "disable" : "enable";
    if (!window.confirm(`${nextState === "disable" ? "Disable" : "Enable"} ${college.name}?`)) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      if (college.is_active) {
        await disableCollege.mutateAsync({ collegeId: college.id });
      } else {
        await enableCollege.mutateAsync({ collegeId: college.id });
      }
      setMessage(`College ${college.is_active ? "disabled" : "enabled"}.`);
      await queryClient.invalidateQueries({ queryKey: getOrganizationListCollegesQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t change that college status. Please try again."));
    }
  }

  return (
    <OrganizationSection
      icon={School}
      title="Colleges"
      description="Place each college under its campus, then keep its code and name current for downstream assignments."
    >
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <form className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-end" onSubmit={submitSearch}>
            <div className="min-w-0 flex-1">
              <Label htmlFor="organization-college-search">Search colleges</Label>
              <div className="relative mt-2">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="organization-college-search"
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
              aria-label="Filter colleges by campus"
              className={organizationSelectClassName}
              value={campusFilter}
              onChange={(event) => setCampusFilter(event.target.value)}
            >
              <option value="">All campuses</option>
              {campuses.map((campus) => (
                <option key={campus.id} value={campus.id}>
                  {campus.name}
                </option>
              ))}
            </select>
            <select
              aria-label="College status"
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
                Add college
              </Button>
            ) : null}
          </div>
        </div>

        <OrganizationActionMessage error={error} message={message} />

        {canManage && showCreate ? (
          <form className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:p-5" onSubmit={submitCreate}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">Add a college</h3>
                <p className="mt-1 text-sm text-muted-foreground">Choose the campus first so the hierarchy stays explicit.</p>
              </div>
              <Button type="button" variant="ghost" size="icon-sm" aria-label="Close add college form" onClick={() => setShowCreate(false)}>
                <X aria-hidden="true" />
              </Button>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <div>
                <Label htmlFor="create-college-campus">Campus</Label>
                <select id="create-college-campus" className={`${organizationSelectClassName} mt-2`} value={createDraft.campusId} onChange={(event) => setCreateDraft((current) => ({ ...current, campusId: event.target.value }))} required>
                  <option value="">Choose a campus</option>
                  {campuses.filter((campus) => campus.is_active).map((campus) => (
                    <option key={campus.id} value={campus.id}>{campus.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="create-college-code">Code</Label>
                <Input id="create-college-code" className="mt-2 h-10" value={createDraft.code} onChange={(event) => setCreateDraft((current) => ({ ...current, code: event.target.value }))} required />
              </div>
              <div>
                <Label htmlFor="create-college-name">Name</Label>
                <Input id="create-college-name" className="mt-2 h-10" value={createDraft.name} onChange={(event) => setCreateDraft((current) => ({ ...current, name: event.target.value }))} required />
              </div>
            </div>
            {campuses.length === 0 ? <p className="mt-3 text-sm text-[var(--compass-brand-maroon)]">Add an active campus before creating a college.</p> : null}
            <div className="mt-4 flex justify-end">
              <Button type="submit" disabled={isMutating || campuses.filter((campus) => campus.is_active).length === 0}>
                {createCollege.isPending ? "Adding…" : "Add college"}
              </Button>
            </div>
          </form>
        ) : null}

        {campusesQuery.isError || collegesQuery.isError ? (
          <OrganizationQueryError
            onRetry={() => {
              void campusesQuery.refetch();
              void collegesQuery.refetch();
            }}
          />
        ) : collegesQuery.isPending ? (
          <OrganizationListSkeleton />
        ) : colleges.length ? (
          <div className="space-y-3">
            {colleges.map((college) => (
              <article key={college.id} className="rounded-2xl border border-[var(--compass-border)] bg-card p-4 shadow-sm sm:p-5">
                {editingId === college.id ? (
                  <form className="space-y-4" onSubmit={(event) => void submitEdit(event, college.id)}>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <Label htmlFor={`edit-college-code-${college.id}`}>Code</Label>
                        <Input id={`edit-college-code-${college.id}`} className="mt-2 h-10" value={editDraft.code} onChange={(event) => setEditDraft((current) => ({ ...current, code: event.target.value }))} required />
                      </div>
                      <div>
                        <Label htmlFor={`edit-college-name-${college.id}`}>Name</Label>
                        <Input id={`edit-college-name-${college.id}`} className="mt-2 h-10" value={editDraft.name} onChange={(event) => setEditDraft((current) => ({ ...current, name: event.target.value }))} required />
                      </div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button type="button" variant="ghost" onClick={cancelEdit}>Cancel</Button>
                      <Button type="submit" disabled={isMutating}>
                        <Check aria-hidden="true" />
                        {updateCollege.isPending ? "Saving…" : "Save changes"}
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
                        <School aria-hidden="true" className="size-5" />
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="break-words font-semibold">{college.name}</h3>
                          <Badge variant="outline">{college.code}</Badge>
                          <OrganizationStatusBadge active={college.is_active} />
                        </div>
                        <p className="mt-1 break-words text-sm text-muted-foreground">{college.campus.name} · {college.campus.code}</p>
                      </div>
                    </div>
                    {canManage ? (
                      <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                        <Button type="button" size="sm" variant="outline" onClick={() => beginEdit(college)}>
                          <Pencil aria-hidden="true" />
                          Edit
                        </Button>
                        <Button type="button" size="sm" variant="ghost" disabled={isMutating} onClick={() => void toggleCollege(college)}>
                          {college.is_active ? "Disable" : "Enable"}
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
            title="No colleges match"
            description={search || campusFilter || status !== "all" ? "Try a different search, campus, or status filter." : "Add the first college under an active campus."}
            action={canManage && !showCreate ? <Button type="button" onClick={() => setShowCreate(true)}>Add college</Button> : undefined}
          />
        )}
      </div>
    </OrganizationSection>
  );
}

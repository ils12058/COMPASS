"use client";

import { FormEvent, useState } from "react";
import { Building2, Check, Pencil, Plus, Search, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getOrganizationListCampusesQueryKey,
  useOrganizationCreateCampus,
  useOrganizationDisableCampus,
  useOrganizationEnableCampus,
  useOrganizationListCampuses,
  useOrganizationUpdateCampus,
} from "@/lib/api/generated/organization/organization";
import type { CampusSummary } from "@/lib/api/generated/model";
import {
  OrganizationActionMessage,
  OrganizationEmptyState,
  OrganizationListSkeleton,
  OrganizationQueryError,
  OrganizationSection,
  OrganizationStatusBadge,
  organizationAdminError,
} from "@/features/portal/admin/organization/portal-it-admin-organization-shared";

type StatusFilter = "all" | "active" | "disabled";

const INITIAL_DRAFT = { code: "", name: "" };

function getActiveFilter(value: StatusFilter) {
  if (value === "active") {
    return true;
  }

  if (value === "disabled") {
    return false;
  }

  return undefined;
}

export function PortalItAdminOrganizationCampuses({
  canManage,
}: {
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [createDraft, setCreateDraft] = useState(INITIAL_DRAFT);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState(INITIAL_DRAFT);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const campusesQuery = useOrganizationListCampuses(
    { search: search || undefined, is_active: getActiveFilter(status) },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const createCampus = useOrganizationCreateCampus();
  const updateCampus = useOrganizationUpdateCampus();
  const disableCampus = useOrganizationDisableCampus();
  const enableCampus = useOrganizationEnableCampus();
  const campuses = campusesQuery.data?.data.items ?? [];
  const isMutating =
    createCampus.isPending ||
    updateCampus.isPending ||
    disableCampus.isPending ||
    enableCampus.isPending;

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearch(draftSearch.trim());
  }

  function beginEdit(campus: CampusSummary) {
    setEditingId(campus.id);
    setEditDraft({ code: campus.code, name: campus.name });
    setError(null);
    setMessage(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDraft(INITIAL_DRAFT);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      await createCampus.mutateAsync({
        data: {
          code: createDraft.code.trim(),
          name: createDraft.name.trim(),
        },
      });
      setCreateDraft(INITIAL_DRAFT);
      setShowCreate(false);
      setMessage("Campus added.");
      await queryClient.invalidateQueries({ queryKey: getOrganizationListCampusesQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t add that campus. Please review the details and try again."));
    }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>, campusId: string) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      await updateCampus.mutateAsync({
        campusId,
        data: {
          code: editDraft.code.trim(),
          name: editDraft.name.trim(),
        },
      });
      cancelEdit();
      setMessage("Campus details updated.");
      await queryClient.invalidateQueries({ queryKey: getOrganizationListCampusesQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t update that campus. Please try again."));
    }
  }

  async function toggleCampus(campus: CampusSummary) {
    const nextState = campus.is_active ? "disable" : "enable";
    if (!window.confirm(`${nextState === "disable" ? "Disable" : "Enable"} ${campus.name}?`)) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      if (campus.is_active) {
        await disableCampus.mutateAsync({ campusId: campus.id });
      } else {
        await enableCampus.mutateAsync({ campusId: campus.id });
      }
      setMessage(`Campus ${campus.is_active ? "disabled" : "enabled"}.`);
      await queryClient.invalidateQueries({ queryKey: getOrganizationListCampusesQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t change that campus status. Please try again."));
    }
  }

  return (
    <OrganizationSection
      icon={Building2}
      title="Campuses"
      description="Manage the top level of the organization structure. Codes should stay stable because other records refer to them."
    >
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <form className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-end" onSubmit={submitSearch}>
            <div className="min-w-0 flex-1">
              <Label htmlFor="organization-campus-search">Search campuses</Label>
              <div className="relative mt-2">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="organization-campus-search"
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
              aria-label="Campus status"
              className="h-10 rounded-lg border border-input bg-card px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
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
                Add campus
              </Button>
            ) : null}
          </div>
        </div>

        <OrganizationActionMessage error={error} message={message} />

        {canManage && showCreate ? (
          <form className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:p-5" onSubmit={submitCreate}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">Add a campus</h3>
                <p className="mt-1 text-sm text-muted-foreground">The server will check the code for conflicts before saving.</p>
              </div>
              <Button type="button" variant="ghost" size="icon-sm" aria-label="Close add campus form" onClick={() => setShowCreate(false)}>
                <X aria-hidden="true" />
              </Button>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="create-campus-code">Code</Label>
                <Input id="create-campus-code" className="mt-2 h-10" value={createDraft.code} onChange={(event) => setCreateDraft((current) => ({ ...current, code: event.target.value }))} required />
              </div>
              <div>
                <Label htmlFor="create-campus-name">Name</Label>
                <Input id="create-campus-name" className="mt-2 h-10" value={createDraft.name} onChange={(event) => setCreateDraft((current) => ({ ...current, name: event.target.value }))} required />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button type="submit" disabled={isMutating}>
                {createCampus.isPending ? "Adding…" : "Add campus"}
              </Button>
            </div>
          </form>
        ) : null}

        {campusesQuery.isPending ? (
          <OrganizationListSkeleton />
        ) : campusesQuery.isError ? (
          <OrganizationQueryError onRetry={() => void campusesQuery.refetch()} />
        ) : campuses.length ? (
          <div className="space-y-3">
            {campuses.map((campus) => (
              <article key={campus.id} className="rounded-2xl border border-[var(--compass-border)] bg-card p-4 shadow-sm sm:p-5">
                {editingId === campus.id ? (
                  <form className="space-y-4" onSubmit={(event) => void submitEdit(event, campus.id)}>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <Label htmlFor={`edit-campus-code-${campus.id}`}>Code</Label>
                        <Input id={`edit-campus-code-${campus.id}`} className="mt-2 h-10" value={editDraft.code} onChange={(event) => setEditDraft((current) => ({ ...current, code: event.target.value }))} required />
                      </div>
                      <div>
                        <Label htmlFor={`edit-campus-name-${campus.id}`}>Name</Label>
                        <Input id={`edit-campus-name-${campus.id}`} className="mt-2 h-10" value={editDraft.name} onChange={(event) => setEditDraft((current) => ({ ...current, name: event.target.value }))} required />
                      </div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button type="button" variant="ghost" onClick={cancelEdit}>Cancel</Button>
                      <Button type="submit" disabled={isMutating}>
                        <Check aria-hidden="true" />
                        {updateCampus.isPending ? "Saving…" : "Save changes"}
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
                        <Building2 aria-hidden="true" className="size-5" />
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="break-words font-semibold">{campus.name}</h3>
                          <Badge variant="outline">{campus.code}</Badge>
                          <OrganizationStatusBadge active={campus.is_active} />
                        </div>
                        <p className="mt-1 break-words text-sm text-muted-foreground">Campus record</p>
                      </div>
                    </div>
                    {canManage ? (
                      <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                        <Button type="button" size="sm" variant="outline" onClick={() => beginEdit(campus)}>
                          <Pencil aria-hidden="true" />
                          Edit
                        </Button>
                        <Button type="button" size="sm" variant="ghost" disabled={isMutating} onClick={() => void toggleCampus(campus)}>
                          {campus.is_active ? "Disable" : "Enable"}
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
            title="No campuses match"
            description={search || status !== "all" ? "Try a different search or status filter." : "Add the first campus to start the organization structure."}
            action={canManage && !showCreate ? <Button type="button" onClick={() => setShowCreate(true)}>Add campus</Button> : undefined}
          />
        )}
      </div>
    </OrganizationSection>
  );
}

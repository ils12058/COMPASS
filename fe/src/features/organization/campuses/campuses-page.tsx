"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOrganizationAction } from "@/features/organization/components/organization-action";
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
  getOrganizationListCampusesQueryKey,
  getOrganizationListCollegesQueryKey,
  useOrganizationCreateCampus,
  useOrganizationDisableCampus,
  useOrganizationEnableCampus,
  useOrganizationListCampuses,
  useOrganizationUpdateCampus,
} from "@/lib/api/generated/organization/organization";

export function CampusesPage() {
  const { user } = usePortalSession();
  const canManage = user.capabilities.includes("organization.manage");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const search = (searchParams.get("search") ?? "").slice(0, 200).trim();
  const status = searchParams.get("is_active") ?? "";
  const filters = {
    ...(status === "true" || status === "false"
      ? { is_active: status === "true" }
      : {}),
    ...(search ? { search } : {}),
  };
  const list = useOrganizationListCampuses(filters, {
    query: { retry: false },
  });
  const create = useOrganizationCreateCampus();
  const update = useOrganizationUpdateCampus();
  const enable = useOrganizationEnableCampus();
  const disable = useOrganizationDisableCampus();
  const action = useOrganizationAction();

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [lifecycle, setLifecycle] = useState<{
    id: string;
    name: string;
    active: boolean;
  } | null>(null);

  const formPending = create.isPending || update.isPending;
  const lifecyclePending = enable.isPending || disable.isPending;

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getOrganizationListCampusesQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getOrganizationListCollegesQueryKey(),
      }),
    ]);
  }

  function openCreate() {
    action.setError(null);
    action.setNotice(null);
    setEditingId(null);
    setCode("");
    setName("");
    setFormOpen(true);
  }

  function openEdit(id: string, nextCode: string, nextName: string) {
    action.setError(null);
    action.setNotice(null);
    setEditingId(id);
    setCode(nextCode);
    setName(nextName);
    setFormOpen(true);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = editingId
      ? await action.run(
          () =>
            update.mutateAsync({
              campusId: editingId,
              data: { code, name },
            }),
          "The Campus could not be updated.",
          {
            onStepUpRequired: () => setFormOpen(false),
            onStepUpVerified: () => setFormOpen(true),
          },
        )
      : await action.run(
          () => create.mutateAsync({ data: { code, name } }),
          "The Campus could not be created.",
          {
            onStepUpRequired: () => setFormOpen(false),
            onStepUpVerified: () => setFormOpen(true),
          },
        );
    if (!response) return;
    setFormOpen(false);
    action.setNotice(editingId ? "Campus updated." : "Campus created.");
    await refresh();
  }

  async function confirmLifecycle() {
    if (!lifecycle) return;
    const target = lifecycle;
    const response = await action.run(
      () =>
        target.active
          ? disable.mutateAsync({ campusId: target.id })
          : enable.mutateAsync({ campusId: target.id }),
      `The Campus could not be ${target.active ? "disabled" : "enabled"}.`,
      {
        onStepUpRequired: () => setLifecycle(null),
        onStepUpVerified: () => setLifecycle(target),
      },
    );
    if (!response) return;
    setLifecycle(null);
    action.setNotice(
      `Campus ${target.active ? "disabled" : "enabled"}.`,
    );
    await refresh();
  }

  function updateFilter(value: string) {
    router.replace(
      replaceQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        "is_active",
        value,
      ),
      { scroll: false },
    );
  }

  return (
    <section aria-labelledby="campuses-heading">
      <div className="sr-only" id="campuses-heading">
        Campuses
      </div>
      <PageHeading
        title="Campuses"
        action={
          canManage ? <Button onClick={openCreate}>Add campus</Button> : null
        }
      />
      <div className="mt-8 flex flex-col gap-4 border-y border-border py-5 sm:flex-row sm:items-end">
        <SearchField label="Search campuses" placeholder="Search campuses…" />
        <div className="sm:w-44">
          <Label htmlFor="campus-status">Status</Label>
          <select
            id="campus-status"
            className={`${selectClass} mt-2`}
            value={status === "true" || status === "false" ? status : ""}
            onChange={(event) => updateFilter(event.target.value)}
          >
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>
      </div>

      {action.notice && !formOpen && !lifecycle ? action.messages : null}

      {list.isPending ? (
        <TableSkeleton />
      ) : list.isError ? (
        <div className="mt-6">
          <QueryError
            error={list.error}
            fallback="Campuses could not be loaded."
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : list.data.data.items.length === 0 ? (
        <p className="border-b border-border py-10 text-sm text-muted">
          {search || status
            ? "No Campuses match the current search or filters."
            : "No Campuses are available."}
        </p>
      ) : (
        <>
          {list.isFetching ? (
            <p role="status" className="mt-4 text-xs text-muted">
              Refreshing Campuses…
            </p>
          ) : null}
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Code
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Campus
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Status
                  </th>
                  {canManage ? (
                    <th scope="col" className="px-4 py-3 text-right">
                      Actions
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {list.data.data.items.map((campus) => (
                  <tr key={campus.id} className="border-t border-border">
                    <td className="px-4 py-4 font-mono text-xs text-muted">
                      {campus.code}
                    </td>
                    <th scope="row" className="px-4 py-4 font-semibold text-ink">
                      {campus.name}
                    </th>
                    <td className="px-4 py-4">
                      <StatusBadge active={campus.is_active} />
                    </td>
                    {canManage ? (
                      <td className="px-4 py-2 text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="quiet"
                            onClick={() =>
                              openEdit(campus.id, campus.code, campus.name)
                            }
                          >
                            Edit
                          </Button>
                          <Button
                            variant={campus.is_active ? "quiet" : "secondary"}
                            onClick={() =>
                              setLifecycle({
                                id: campus.id,
                                name: campus.name,
                                active: campus.is_active,
                              })
                            }
                          >
                            {campus.is_active ? "Disable" : "Enable"}
                          </Button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Dialog
        open={formOpen}
        onOpenChange={(open) => {
          if (formPending) return;
          setFormOpen(open);
          if (!open) {
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <DialogContent
          onEscapeKeyDown={(event) => {
            if (formPending) event.preventDefault();
          }}
          onPointerDownOutside={(event) => {
            if (formPending) event.preventDefault();
          }}
        >
          <DialogTitle>{editingId ? "Edit Campus" : "Add Campus"}</DialogTitle>
          <DialogDescription>
            {editingId
              ? "Update the Campus code or name."
              : "Create an institutional Campus."}
          </DialogDescription>
          <form className="mt-6 space-y-5" onSubmit={submit}>
            <div className="grid gap-2">
              <Label htmlFor="campus-code">Code</Label>
              <Input
                id="campus-code"
                required
                value={code}
                onChange={(event) => setCode(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="campus-name">Name</Label>
              <Input
                id="campus-name"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            {action.messages}
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                disabled={formPending}
                onClick={() => setFormOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={formPending}>
                {formPending
                  ? editingId
                    ? "Saving…"
                    : "Creating…"
                  : editingId
                    ? "Save changes"
                    : "Create Campus"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(lifecycle)}
        onOpenChange={(open) => {
          if (lifecyclePending) return;
          if (!open) {
            setLifecycle(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>
            {lifecycle?.active ? "Disable Campus?" : "Enable Campus?"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {lifecycle?.active
              ? `${lifecycle.name ?? "This Campus"} cannot be disabled while it still contains active Colleges. COMPASS will refuse the change rather than cascade it.`
              : `Enable ${lifecycle?.name ?? "this Campus"} for active use?`}
          </AlertDialogDescription>
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={lifecyclePending}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant={lifecycle?.active ? "danger" : "primary"}
              disabled={lifecyclePending}
              onClick={() => void confirmLifecycle()}
            >
              {lifecyclePending
                ? lifecycle?.active
                  ? "Disabling…"
                  : "Enabling…"
                : lifecycle?.active
                  ? "Disable Campus"
                  : "Enable Campus"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      {action.stepUpDialog}
    </section>
  );
}

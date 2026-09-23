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
  getOrganizationListCollegesQueryKey,
  getOrganizationListProgramsQueryKey,
  useOrganizationCreateCollege,
  useOrganizationDisableCollege,
  useOrganizationEnableCollege,
  useOrganizationListCampuses,
  useOrganizationListColleges,
  useOrganizationUpdateCollege,
} from "@/lib/api/generated/organization/organization";

export function CollegesPage() {
  const { user } = usePortalSession();
  const canManage = user.capabilities.includes("organization.manage");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const search = (searchParams.get("search") ?? "").slice(0, 200).trim();
  const status = searchParams.get("is_active") ?? "";
  const campusId = searchParams.get("campus_id") ?? "";
  const campuses = useOrganizationListCampuses(
    {},
    { query: { retry: false } },
  );
  const list = useOrganizationListColleges(
    {
      ...(campusId ? { campus_id: campusId } : {}),
      ...(status === "true" || status === "false"
        ? { is_active: status === "true" }
        : {}),
      ...(search ? { search } : {}),
    },
    { query: { retry: false } },
  );
  const create = useOrganizationCreateCollege();
  const update = useOrganizationUpdateCollege();
  const enable = useOrganizationEnableCollege();
  const disable = useOrganizationDisableCollege();
  const action = useOrganizationAction();

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [parentCampusId, setParentCampusId] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [lifecycle, setLifecycle] = useState<{
    id: string;
    name: string;
    active: boolean;
  } | null>(null);

  const formPending = create.isPending || update.isPending;
  const lifecyclePending = enable.isPending || disable.isPending;
  const editing = editingId
    ? list.data?.data.items.find((college) => college.id === editingId)
    : undefined;

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getOrganizationListCollegesQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getOrganizationListProgramsQueryKey(),
      }),
    ]);
  }

  function openCreate() {
    action.setError(null);
    action.setNotice(null);
    setEditingId(null);
    setParentCampusId("");
    setCode("");
    setName("");
    setFormOpen(true);
  }

  function openEdit(id: string, nextCode: string, nextName: string) {
    action.setError(null);
    action.setNotice(null);
    setEditingId(id);
    setParentCampusId("");
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
              collegeId: editingId,
              data: { code, name },
            }),
          "The College could not be updated.",
          {
            onStepUpRequired: () => setFormOpen(false),
            onStepUpVerified: () => setFormOpen(true),
          },
        )
      : await action.run(
          () =>
            create.mutateAsync({
              data: { campus_id: parentCampusId, code, name },
            }),
          "The College could not be created.",
          {
            onStepUpRequired: () => setFormOpen(false),
            onStepUpVerified: () => setFormOpen(true),
          },
        );
    if (!response) return;
    setFormOpen(false);
    action.setNotice(editingId ? "College updated." : "College created.");
    await refresh();
  }

  async function confirmLifecycle() {
    if (!lifecycle) return;
    const target = lifecycle;
    const response = await action.run(
      () =>
        target.active
          ? disable.mutateAsync({ collegeId: target.id })
          : enable.mutateAsync({ collegeId: target.id }),
      `The College could not be ${target.active ? "disabled" : "enabled"}.`,
      {
        onStepUpRequired: () => setLifecycle(null),
        onStepUpVerified: () => setLifecycle(target),
      },
    );
    if (!response) return;
    setLifecycle(null);
    action.setNotice(
      `College ${target.active ? "disabled" : "enabled"}.`,
    );
    await refresh();
  }

  function updateFilter(key: string, value: string) {
    router.replace(
      replaceQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        key,
        value,
      ),
      { scroll: false },
    );
  }

  const activeCampuses =
    campuses.data?.data.items.filter((campus) => campus.is_active) ?? [];

  return (
    <section>
      <PageHeading
        title="Colleges"
        action={
          canManage ? <Button onClick={openCreate}>Add College</Button> : null
        }
      />
      <div className="mt-8 flex flex-col gap-4 border-y border-border py-5 lg:flex-row lg:items-end">
        <SearchField label="Search Colleges" placeholder="Search Colleges…" />
        <div className="grid gap-4 sm:grid-cols-2 lg:w-[26rem]">
          <div>
            <Label htmlFor="college-campus-filter">Campus</Label>
            <select
              id="college-campus-filter"
              className={`${selectClass} mt-2`}
              value={campusId}
              disabled={campuses.isPending || campuses.isError}
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
            <Label htmlFor="college-status">Status</Label>
            <select
              id="college-status"
              className={`${selectClass} mt-2`}
              value={status === "true" || status === "false" ? status : ""}
              onChange={(event) =>
                updateFilter("is_active", event.target.value)
              }
            >
              <option value="">All</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </div>
        </div>
      </div>

      {campuses.isError ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          Campus choices could not be loaded. The College list remains available.
        </p>
      ) : null}
      {action.notice && !formOpen && !lifecycle ? action.messages : null}

      {list.isPending ? (
        <TableSkeleton />
      ) : list.isError ? (
        <div className="mt-6">
          <QueryError
            error={list.error}
            fallback="Colleges could not be loaded."
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : list.data.data.items.length === 0 ? (
        <p className="border-b border-border py-10 text-sm text-muted">
          {search || status || campusId
            ? "No Colleges match the current search or filters."
            : "No Colleges are available."}
        </p>
      ) : (
        <div className="mt-5 overflow-x-auto border-y border-border">
          <table className="w-full min-w-[42rem] border-collapse text-left text-sm">
            <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-3">
                  College
                </th>
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
              {list.data.data.items.map((college) => (
                <tr key={college.id} className="border-t border-border">
                  <th scope="row" className="px-4 py-4 font-semibold text-ink">
                    {college.name}
                  </th>
                  <td className="px-4 py-4 font-mono text-xs text-muted">
                    {college.code}
                  </td>
                  <td className="px-4 py-4">
                    {college.campus.code} — {college.campus.name}
                  </td>
                  <td className="px-4 py-4">
                    <StatusBadge active={college.is_active} />
                  </td>
                  {canManage ? (
                    <td className="px-4 py-2 text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="quiet"
                          onClick={() =>
                            openEdit(college.id, college.code, college.name)
                          }
                        >
                          Edit
                        </Button>
                        <Button
                          variant={college.is_active ? "quiet" : "secondary"}
                          onClick={() =>
                            setLifecycle({
                              id: college.id,
                              name: college.name,
                              active: college.is_active,
                            })
                          }
                        >
                          {college.is_active ? "Disable" : "Enable"}
                        </Button>
                      </div>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
        <DialogContent>
          <DialogTitle>{editingId ? "Edit College" : "Add College"}</DialogTitle>
          <DialogDescription>
            {editingId
              ? "Update the College code or name. Its parent Campus cannot be changed."
              : "Create a College under an active Campus."}
          </DialogDescription>
          <form className="mt-6 space-y-5" onSubmit={submit}>
            {editingId ? (
              <div>
                <Label>Campus</Label>
                <p className="mt-2 rounded-md border border-border bg-surface-muted px-3 py-2 text-sm text-ink">
                  {editing
                    ? `${editing.campus.code} — ${editing.campus.name}`
                    : "Current Campus"}
                </p>
              </div>
            ) : (
              <div className="grid gap-2">
                <Label htmlFor="college-campus">Campus</Label>
                <select
                  id="college-campus"
                  required
                  className={selectClass}
                  value={parentCampusId}
                  onChange={(event) => setParentCampusId(event.target.value)}
                  disabled={campuses.isPending || campuses.isError}
                >
                  <option value="">Select Campus</option>
                  {activeCampuses.map((campus) => (
                    <option key={campus.id} value={campus.id}>
                      {campus.code} — {campus.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="college-code">Code</Label>
              <Input
                id="college-code"
                required
                value={code}
                onChange={(event) => setCode(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="college-name">Name</Label>
              <Input
                id="college-name"
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
              <Button
                type="submit"
                disabled={
                  formPending ||
                  (!editingId &&
                    (campuses.isPending ||
                      campuses.isError ||
                      !parentCampusId))
                }
              >
                {formPending
                  ? editingId
                    ? "Saving…"
                    : "Creating…"
                  : editingId
                    ? "Save changes"
                    : "Create College"}
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
            {lifecycle?.active ? "Disable College?" : "Enable College?"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {lifecycle?.active
              ? `${lifecycle.name ?? "This College"} cannot be disabled while it still has Student affiliations, a responsible Counselor, or active Programs. COMPASS will not remove or disable those relationships automatically.`
              : `Enable ${lifecycle?.name ?? "this College"}? Its parent Campus must be active.`}
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
                  ? "Disable College"
                  : "Enable College"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      {action.stepUpDialog}
    </section>
  );
}

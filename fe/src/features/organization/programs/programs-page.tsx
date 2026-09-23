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
  getOrganizationListProgramsQueryKey,
  useOrganizationCreateProgram,
  useOrganizationDisableProgram,
  useOrganizationEnableProgram,
  useOrganizationListColleges,
  useOrganizationListPrograms,
  useOrganizationUpdateProgram,
} from "@/lib/api/generated/organization/organization";

export function ProgramsPage() {
  const { user } = usePortalSession();
  const canManage = user.capabilities.includes("organization.manage");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const search = (searchParams.get("search") ?? "").slice(0, 200).trim();
  const status = searchParams.get("is_active") ?? "";
  const collegeId = searchParams.get("college_id") ?? "";
  const colleges = useOrganizationListColleges(
    {},
    { query: { retry: false } },
  );
  const list = useOrganizationListPrograms(
    {
      ...(collegeId ? { college_id: collegeId } : {}),
      ...(status === "true" || status === "false"
        ? { is_active: status === "true" }
        : {}),
      ...(search ? { search } : {}),
    },
    { query: { retry: false } },
  );
  const create = useOrganizationCreateProgram();
  const update = useOrganizationUpdateProgram();
  const enable = useOrganizationEnableProgram();
  const disable = useOrganizationDisableProgram();
  const action = useOrganizationAction();

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [parentCollegeId, setParentCollegeId] = useState("");
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
    ? list.data?.data.items.find((program) => program.id === editingId)
    : undefined;

  async function refresh() {
    await queryClient.invalidateQueries({
      queryKey: getOrganizationListProgramsQueryKey(),
    });
  }

  function openCreate() {
    action.setError(null);
    action.setNotice(null);
    setEditingId(null);
    setParentCollegeId("");
    setCode("");
    setName("");
    setFormOpen(true);
  }

  function openEdit(id: string, nextCode: string, nextName: string) {
    action.setError(null);
    action.setNotice(null);
    setEditingId(id);
    setParentCollegeId("");
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
              programId: editingId,
              data: { code, name },
            }),
          "The Program could not be updated.",
          {
            onStepUpRequired: () => setFormOpen(false),
            onStepUpVerified: () => setFormOpen(true),
          },
        )
      : await action.run(
          () =>
            create.mutateAsync({
              data: { college_id: parentCollegeId, code, name },
            }),
          "The Program could not be created.",
          {
            onStepUpRequired: () => setFormOpen(false),
            onStepUpVerified: () => setFormOpen(true),
          },
        );
    if (!response) return;
    setFormOpen(false);
    action.setNotice(editingId ? "Program updated." : "Program created.");
    await refresh();
  }

  async function confirmLifecycle() {
    if (!lifecycle) return;
    const target = lifecycle;
    const response = await action.run(
      () =>
        target.active
          ? disable.mutateAsync({ programId: target.id })
          : enable.mutateAsync({ programId: target.id }),
      `The Program could not be ${target.active ? "disabled" : "enabled"}.`,
      {
        onStepUpRequired: () => setLifecycle(null),
        onStepUpVerified: () => setLifecycle(target),
      },
    );
    if (!response) return;
    setLifecycle(null);
    action.setNotice(
      `Program ${target.active ? "disabled" : "enabled"}.`,
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

  const activeColleges =
    colleges.data?.data.items.filter(
      (college) => college.is_active && college.campus.is_active,
    ) ?? [];

  return (
    <section>
      <PageHeading
        title="Programs"
        action={
          canManage ? <Button onClick={openCreate}>Add Program</Button> : null
        }
      />
      <div className="mt-8 flex flex-col gap-4 border-y border-border py-5 lg:flex-row lg:items-end">
        <SearchField label="Search Programs" placeholder="Search Programs…" />
        <div className="grid gap-4 sm:grid-cols-2 lg:w-[30rem]">
          <div>
            <Label htmlFor="program-college-filter">College</Label>
            <select
              id="program-college-filter"
              className={`${selectClass} mt-2`}
              value={collegeId}
              disabled={colleges.isPending || colleges.isError}
              onChange={(event) =>
                updateFilter("college_id", event.target.value)
              }
            >
              <option value="">All Colleges</option>
              {colleges.data?.data.items.map((college) => (
                <option key={college.id} value={college.id}>
                  {college.code} — {college.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="program-status">Status</Label>
            <select
              id="program-status"
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

      {colleges.isError ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          College choices could not be loaded. The Program list remains available.
        </p>
      ) : null}
      {action.notice && !formOpen && !lifecycle ? action.messages : null}

      {list.isPending ? (
        <TableSkeleton />
      ) : list.isError ? (
        <div className="mt-6">
          <QueryError
            error={list.error}
            fallback="Programs could not be loaded."
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : list.data.data.items.length === 0 ? (
        <p className="border-b border-border py-10 text-sm text-muted">
          {search || status || collegeId
            ? "No Programs match the current search or filters."
            : "No Programs are available."}
        </p>
      ) : (
        <div className="mt-5 overflow-x-auto border-y border-border">
          <table className="w-full min-w-[46rem] border-collapse text-left text-sm">
            <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-3">
                  Program
                </th>
                <th scope="col" className="px-4 py-3">
                  Code
                </th>
                <th scope="col" className="px-4 py-3">
                  College
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
              {list.data.data.items.map((program) => (
                <tr key={program.id} className="border-t border-border">
                  <th scope="row" className="px-4 py-4 font-semibold text-ink">
                    {program.name}
                  </th>
                  <td className="px-4 py-4 font-mono text-xs text-muted">
                    {program.code}
                  </td>
                  <td className="px-4 py-4">{program.college.name}</td>
                  <td className="px-4 py-4">{program.college.campus.name}</td>
                  <td className="px-4 py-4">
                    <StatusBadge active={program.is_active} />
                  </td>
                  {canManage ? (
                    <td className="px-4 py-2 text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="quiet"
                          onClick={() =>
                            openEdit(program.id, program.code, program.name)
                          }
                        >
                          Edit
                        </Button>
                        <Button
                          variant={program.is_active ? "quiet" : "secondary"}
                          onClick={() =>
                            setLifecycle({
                              id: program.id,
                              name: program.name,
                              active: program.is_active,
                            })
                          }
                        >
                          {program.is_active ? "Disable" : "Enable"}
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
          <DialogTitle>{editingId ? "Edit Program" : "Add Program"}</DialogTitle>
          <DialogDescription>
            {editingId
              ? "Update the Program code or name. Its parent College cannot be changed."
              : "Create a Program under an active College."}
          </DialogDescription>
          <form className="mt-6 space-y-5" onSubmit={submit}>
            {editingId ? (
              <div>
                <Label>College</Label>
                <p className="mt-2 rounded-md border border-border bg-surface-muted px-3 py-2 text-sm text-ink">
                  {editing
                    ? `${editing.college.code} — ${editing.college.name}`
                    : "Current College"}
                </p>
              </div>
            ) : (
              <div className="grid gap-2">
                <Label htmlFor="program-college">College</Label>
                <select
                  id="program-college"
                  required
                  className={selectClass}
                  value={parentCollegeId}
                  onChange={(event) => setParentCollegeId(event.target.value)}
                  disabled={colleges.isPending || colleges.isError}
                >
                  <option value="">Select College</option>
                  {activeColleges.map((college) => (
                    <option key={college.id} value={college.id}>
                      {college.code} — {college.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="program-code">Code</Label>
              <Input
                id="program-code"
                required
                value={code}
                onChange={(event) => setCode(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="program-name">Name</Label>
              <Input
                id="program-name"
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
                    (colleges.isPending ||
                      colleges.isError ||
                      !parentCollegeId))
                }
              >
                {formPending
                  ? editingId
                    ? "Saving…"
                    : "Creating…"
                  : editingId
                    ? "Save changes"
                    : "Create Program"}
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
            {lifecycle?.active ? "Disable Program?" : "Enable Program?"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {lifecycle?.active
              ? `Disable ${lifecycle.name ?? "this Program"}? This does not change its College or Campus.`
              : `Enable ${lifecycle?.name ?? "this Program"}? Its College and Campus must both be active.`}
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
                  ? "Disable Program"
                  : "Enable Program"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      {action.stepUpDialog}
    </section>
  );
}

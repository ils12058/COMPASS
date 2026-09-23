"use client";

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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  ManagedActionFeedback,
  managedAccountError,
  useInvalidateManagedAccount,
  useManagedAction,
} from "@/features/accounts/components/account-action";
import { useManagedAccount } from "@/features/accounts/detail/account-detail-frame";
import {
  compatibleDesignation,
  designationLabels,
  formatAccountDate,
  isDesignationCode,
  isRoleCode,
  roleLabels,
  roles,
} from "@/features/accounts/presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useAccountsAssignDesignation,
  useAccountsChangeRole,
  useAccountsGetEffectiveAccess,
  useAccountsListCapabilityOverrides,
  useAccountsListDesignations,
  useAccountsRemoveCapabilityOverride,
  useAccountsRemoveDesignation,
  useAccountsSetCapabilityOverride,
} from "@/lib/api/generated/accounts/accounts";
import {
  Effect,
  type CapabilityCode,
  type DesignationCode,
  type RoleCode,
} from "@/lib/api/generated/model";

type Confirmation =
  | { kind: "role"; role: RoleCode }
  | { kind: "assign"; designation: DesignationCode }
  | { kind: "removeDesignation"; designation: DesignationCode }
  | {
      kind: "setOverride";
      capability: CapabilityCode;
      effect: Effect;
      reason: string;
      expires_at: string | null;
    }
  | { kind: "removeOverride"; capability: CapabilityCode }
  | null;

const selectClass =
  "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function AccountAccess() {
  const account = useManagedAccount();
  const { user } = usePortalSession();
  const self = user.id === account.id;
  const mayManageDesignations = user.capabilities.includes(
    "institutional_designations.manage",
  );
  const invalidate = useInvalidateManagedAccount(account.id);
  const action = useManagedAction();
  const effective = useAccountsGetEffectiveAccess(account.id, {
    query: { retry: false },
  });
  const assigned = useAccountsListDesignations(account.id, {
    query: { retry: false },
  });
  const overrides = useAccountsListCapabilityOverrides(account.id, {
    query: { retry: false },
  });
  const changeRole = useAccountsChangeRole();
  const assignDesignation = useAccountsAssignDesignation();
  const removeDesignation = useAccountsRemoveDesignation();
  const setOverride = useAccountsSetCapabilityOverride();
  const removeOverride = useAccountsRemoveCapabilityOverride();
  const [roleDraft, setRoleDraft] = useState<RoleCode | null>(null);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideCapability, setOverrideCapability] = useState<
    CapabilityCode | ""
  >("");
  const [overrideEffect, setOverrideEffect] = useState<Effect>(Effect.GRANT);
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideExpiry, setOverrideExpiry] = useState("");
  const [confirm, setConfirm] = useState<Confirmation>(null);
  const busy =
    changeRole.isPending ||
    assignDesignation.isPending ||
    removeDesignation.isPending ||
    setOverride.isPending ||
    removeOverride.isPending;
  const eligibleDesignation = compatibleDesignation(account.role);
  const currentDesignations =
    assigned.data?.data.designations ?? account.designations;

  function reviewOverride(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!overrideCapability || !overrideReason.trim()) return;
    const expiry = overrideExpiry ? new Date(overrideExpiry) : null;
    if (expiry && Number.isNaN(expiry.getTime())) {
      action.setError("Enter a valid expiry date and time.");
      return;
    }
    action.setError(null);
    setOverrideOpen(false);
    setConfirm({
      kind: "setOverride",
      capability: overrideCapability,
      effect: overrideEffect,
      reason: overrideReason.trim(),
      expires_at: expiry?.toISOString() ?? null,
    });
  }

  async function confirmAction() {
    const item = confirm;
    if (!item) return;
    async function perform(): Promise<boolean> {
      if (!item) return false;
      switch (item.kind) {
        case "role":
          return Boolean(
            await action.run(
              () =>
                changeRole.mutateAsync({
                  userId: account.id,
                  data: { role: item.role },
                }),
              "Role could not be changed.",
              () => setConfirm(null),
            ),
          );
        case "assign":
          return Boolean(
            await action.run(
              () =>
                assignDesignation.mutateAsync({
                  userId: account.id,
                  designationCode: item.designation,
                }),
              "Designation could not be assigned.",
              () => setConfirm(null),
            ),
          );
        case "removeDesignation":
          return Boolean(
            await action.run(
              () =>
                removeDesignation.mutateAsync({
                  userId: account.id,
                  designationCode: item.designation,
                }),
              "Designation could not be removed.",
              () => setConfirm(null),
            ),
          );
        case "setOverride":
          return Boolean(
            await action.run(
              () =>
                setOverride.mutateAsync({
                  userId: account.id,
                  capabilityCode: item.capability,
                  data: {
                    effect: item.effect,
                    reason: item.reason,
                    expires_at: item.expires_at,
                  },
                }),
              "Override could not be set.",
              () => setConfirm(null),
            ),
          );
        case "removeOverride":
          return Boolean(
            await action.run(
              () =>
                removeOverride.mutateAsync({
                  userId: account.id,
                  capabilityCode: item.capability,
                }),
              "Override could not be removed.",
              () => setConfirm(null),
            ),
          );
      }
    }
    if (!(await perform())) return;
    setConfirm(null);
    if (item.kind === "role") setRoleDraft(null);
    if (item.kind === "setOverride") {
      setOverrideCapability("");
      setOverrideReason("");
      setOverrideExpiry("");
    }
    await invalidate();
    action.setNotice(
      item.kind === "removeOverride"
        ? "Override removed. Effective access has been refreshed."
        : "Access change saved.",
    );
  }

  function confirmationText(
    item: NonNullable<Confirmation>,
  ): [string, string, string] {
    if (item.kind === "role")
      return [
        `Change ${account.full_name}'s role from ${roleLabels[account.role]} to ${roleLabels[item.role]}?`,
        "This changes baseline COMPASS access and may invalidate existing authenticated access.",
        "Change role",
      ];
    if (item.kind === "assign")
      return [
        `Assign ${designationLabels[item.designation]} to ${account.full_name}?`,
        "This designation changes the account's institutional authority and may invalidate current access.",
        "Assign designation",
      ];
    if (item.kind === "removeDesignation")
      return [
        `Remove ${designationLabels[item.designation]} from ${account.full_name}?`,
        "This removes designation-based access and may invalidate current authenticated access.",
        "Remove designation",
      ];
    if (item.kind === "setOverride")
      return [
        `${item.effect === Effect.GRANT ? "Grant" : "Revoke"} ${effective.data?.data.capabilities.find((capability) => capability.code === item.capability)?.name ?? item.capability} for ${account.full_name}?`,
        `Reason: ${item.reason}${item.expires_at ? `. Expires: ${formatAccountDate(item.expires_at)}` : ". No expiry set."}`,
        "Set override",
      ];
    return [
      `Remove ${account.full_name}'s ${effective.data?.data.capabilities.find((capability) => capability.code === item.capability)?.name ?? item.capability} override?`,
      "Effective access will return to the role and designation baseline for this capability.",
      "Remove override",
    ];
  }

  const confirmation = confirm ? confirmationText(confirm) : null;

  return (
    <div className="space-y-10">
      <section aria-labelledby="role-heading">
        <h2
          id="role-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Role
        </h2>
        <p className="mt-3 text-sm text-muted">
          Current role:{" "}
          <span className="font-semibold text-ink">
            {roleLabels[account.role]}
          </span>
        </p>
        {self ? (
          <p className="mt-3 text-sm text-muted">
            You cannot change your own administrative authority here.
          </p>
        ) : (
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <div className="w-full max-w-xs">
              <Label htmlFor="managed-role">New role</Label>
              <select
                id="managed-role"
                className={`${selectClass} mt-2`}
                value={roleDraft ?? account.role}
                onChange={(event) => {
                  if (isRoleCode(event.target.value))
                    setRoleDraft(event.target.value);
                }}
              >
                {roles.map((role) => (
                  <option key={role} value={role}>
                    {roleLabels[role]}
                  </option>
                ))}
              </select>
            </div>
            <Button
              variant="secondary"
              disabled={!roleDraft || roleDraft === account.role}
              onClick={() => {
                if (roleDraft) setConfirm({ kind: "role", role: roleDraft });
              }}
            >
              Change role
            </Button>
          </div>
        )}
      </section>

      <section aria-labelledby="designations-heading">
        <h2
          id="designations-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Institutional designations
        </h2>
        {assigned.isError ? (
          <div role="alert" className="mt-3 text-sm text-danger">
            {managedAccountError(
              assigned.error,
              "Designations could not be loaded.",
            )}{" "}
            <button
              className="font-semibold underline"
              onClick={() => void assigned.refetch()}
            >
              Retry
            </button>
          </div>
        ) : assigned.isPending ? (
          <Skeleton className="mt-4 h-12 w-full" />
        ) : (
          <div className="mt-4 border-t border-border py-4">
            <p className="text-sm text-ink">
              {currentDesignations.length
                ? currentDesignations
                    .map((designation) => designationLabels[designation])
                    .join(", ")
                : "No institutional designations assigned."}
            </p>
            {self ? (
              <p className="mt-3 text-sm text-muted">
                You cannot change your own institutional designations here.
              </p>
            ) : mayManageDesignations ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {eligibleDesignation &&
                !currentDesignations.includes(eligibleDesignation) ? (
                  <Button
                    variant="secondary"
                    onClick={() =>
                      setConfirm({
                        kind: "assign",
                        designation: eligibleDesignation,
                      })
                    }
                  >
                    Assign {designationLabels[eligibleDesignation]}
                  </Button>
                ) : null}
                {currentDesignations.map((designation) => (
                  <Button
                    key={designation}
                    variant="quiet"
                    onClick={() =>
                      setConfirm({ kind: "removeDesignation", designation })
                    }
                  >
                    Remove {designationLabels[designation]}
                  </Button>
                ))}
                {!eligibleDesignation && currentDesignations.length === 0 ? (
                  <p className="text-sm text-muted">
                    No institutional designation is compatible with this role.
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">
                You can view designations, but your current access does not
                allow changing them.
              </p>
            )}
          </div>
        )}
      </section>

      <section aria-labelledby="effective-heading">
        <h2
          id="effective-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Effective access
        </h2>
        <p className="mt-2 text-sm text-muted">
          This is the backend&apos;s current access projection, including role,
          designations, and overrides.
        </p>
        {effective.isPending ? (
          <div aria-busy="true" className="mt-5 space-y-2">
            {Array.from({ length: 5 }, (_, index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </div>
        ) : effective.isError ? (
          <div role="alert" className="mt-4 text-sm text-danger">
            {managedAccountError(
              effective.error,
              "Effective access could not be loaded.",
            )}{" "}
            <button
              className="font-semibold underline"
              onClick={() => void effective.refetch()}
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="mt-5 max-h-[40rem] overflow-auto border-y border-border">
            <table className="w-full min-w-[43rem] text-left text-sm">
              <thead className="sticky top-0 bg-surface-subtle text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-3 py-3">
                    Capability
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Effective
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Granted by
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Override
                  </th>
                </tr>
              </thead>
              <tbody>
                {effective.data.data.capabilities.map((capability) => (
                  <tr
                    key={capability.code}
                    className="border-t border-border align-top"
                  >
                    <th
                      scope="row"
                      className="px-3 py-3 font-semibold text-ink"
                    >
                      {capability.name}
                      <span className="mt-1 block font-normal text-muted">
                        {capability.description}
                      </span>
                    </th>
                    <td className="px-3 py-3">
                      {capability.effective ? "Yes" : "No"}
                    </td>
                    <td className="px-3 py-3">
                      {capability.baseline_sources.length
                        ? capability.baseline_sources
                            .map((source) =>
                              source.type === "ROLE" && isRoleCode(source.code)
                                ? `Role: ${roleLabels[source.code]}`
                                : source.type === "DESIGNATION" &&
                                    isDesignationCode(source.code)
                                  ? `Designation: ${designationLabels[source.code]}`
                                  : `${source.type}: ${source.code}`,
                            )
                            .join(", ")
                        : "—"}
                    </td>
                    <td className="px-3 py-3">
                      {capability.override
                        ? `${capability.override.effect === Effect.GRANT ? "Grant" : "Revoke"}${capability.override.active ? "" : " (expired)"}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="overrides-heading">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2
            id="overrides-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Capability overrides
          </h2>
          {!self && effective.isSuccess ? (
            <Button
              variant="secondary"
              onClick={() => {
                action.setError(null);
                setOverrideOpen(true);
              }}
            >
              Set override
            </Button>
          ) : null}
        </div>
        <p className="mt-2 text-sm text-muted">
          Overrides are exceptional changes to role and designation access.
        </p>
        {self ? (
          <p className="mt-3 text-sm text-muted">
            You cannot change your own capability overrides here.
          </p>
        ) : null}
        {overrides.isPending ? (
          <Skeleton className="mt-5 h-20 w-full" />
        ) : overrides.isError ? (
          <div role="alert" className="mt-4 text-sm text-danger">
            {managedAccountError(
              overrides.error,
              "Overrides could not be loaded.",
            )}{" "}
            <button
              className="font-semibold underline"
              onClick={() => void overrides.refetch()}
            >
              Retry
            </button>
          </div>
        ) : overrides.data.data.overrides.length === 0 ? (
          <p className="mt-5 border-t border-border py-5 text-sm text-muted">
            No capability overrides are recorded.
          </p>
        ) : (
          <div className="mt-5 divide-y divide-border border-y border-border">
            {overrides.data.data.overrides.map((override) => {
              const capability = effective.data?.data.capabilities.find(
                (item) => item.code === override.capability,
              );
              const active = capability?.override?.active;
              return (
                <div
                  key={override.capability}
                  className="flex flex-wrap items-start justify-between gap-4 py-4 text-sm"
                >
                  <div>
                    <p className="font-semibold text-ink">
                      {capability?.name ?? override.capability} ·{" "}
                      {override.effect === Effect.GRANT ? "Grant" : "Revoke"} ·{" "}
                      {active === true
                        ? "Active"
                        : active === false
                          ? "Expired"
                          : "Status unavailable"}
                    </p>
                    <p className="mt-1 text-muted">Reason: {override.reason}</p>
                    <p className="mt-1 text-muted">
                      Created {formatAccountDate(override.created_at)} by{" "}
                      {override.created_by?.full_name ||
                        override.created_by?.email ||
                        "Unknown"}
                      . Expiry:{" "}
                      {override.expires_at
                        ? formatAccountDate(override.expires_at)
                        : "None"}
                      .
                    </p>
                  </div>
                  {!self ? (
                    <Button
                      variant="quiet"
                      onClick={() =>
                        setConfirm({
                          kind: "removeOverride",
                          capability: override.capability,
                        })
                      }
                    >
                      Remove override
                    </Button>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <ManagedActionFeedback action={action} />
      <Dialog
        open={overrideOpen}
        onOpenChange={(open) => {
          if (!busy) setOverrideOpen(open);
        }}
      >
        <DialogContent>
          <DialogTitle>Set capability override</DialogTitle>
          <DialogDescription>
            Choose one exception to this account&apos;s baseline access. A
            reason is required.
          </DialogDescription>
          <form className="mt-6 space-y-4" onSubmit={reviewOverride}>
            <div className="grid gap-2">
              <Label htmlFor="override-capability">Capability</Label>
              <select
                id="override-capability"
                className={selectClass}
                required
                value={overrideCapability}
                onChange={(event) => {
                  const code = effective.data?.data.capabilities.find(
                    (item) => item.code === event.target.value,
                  )?.code;
                  setOverrideCapability(code ?? "");
                }}
              >
                <option value="">Select capability</option>
                {effective.data?.data.capabilities.map((capability) => (
                  <option key={capability.code} value={capability.code}>
                    {capability.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="override-effect">Effect</Label>
              <select
                id="override-effect"
                className={selectClass}
                value={overrideEffect}
                onChange={(event) =>
                  setOverrideEffect(
                    event.target.value === Effect.REVOKE
                      ? Effect.REVOKE
                      : Effect.GRANT,
                  )
                }
              >
                <option value={Effect.GRANT}>Grant</option>
                <option value={Effect.REVOKE}>Revoke</option>
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="override-reason">Reason</Label>
              <Textarea
                id="override-reason"
                required
                value={overrideReason}
                onChange={(event) => setOverrideReason(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="override-expiry">Expiry (optional)</Label>
              <Input
                id="override-expiry"
                type="datetime-local"
                value={overrideExpiry}
                onChange={(event) => setOverrideExpiry(event.target.value)}
              />
            </div>
            {action.error ? (
              <p role="alert" className="text-sm text-danger">
                {action.error}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => setOverrideOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit">Review override</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
      <AlertDialog
        open={confirm !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setConfirm(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>{confirmation?.[0]}</AlertDialogTitle>
          <AlertDialogDescription>{confirmation?.[1]}</AlertDialogDescription>
          {action.error ? (
            <p role="alert" className="mt-3 text-sm text-danger">
              {action.error}
            </p>
          ) : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={busy}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button disabled={busy} onClick={() => void confirmAction()}>
              {busy ? "Saving access…" : confirmation?.[2]}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

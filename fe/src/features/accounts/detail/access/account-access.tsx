"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { dataTable } from "@/components/ui/data-table";
import { Panel, PanelBody, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import {
  ManagedActionFeedback,
  managedAccountError,
  useInvalidateManagedAccount,
  useManagedAction,
} from "@/features/accounts/components/account-action";
import { useManagedAccount } from "@/features/accounts/detail/account-detail-frame";
import {
  accountName,
  compatibleDesignations,
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
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateTimeInputToISO,
} from "@/lib/institutional-time";

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
  const assignedData = safeQueryData(assigned)?.data;
  const effectiveData = safeQueryData(effective)?.data;
  const overridesData = safeQueryData(overrides)?.data;
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
  const [overrideExpiryError, setOverrideExpiryError] = useState<string | null>(
    null,
  );
  const [confirm, setConfirm] = useState<Confirmation>(null);
  const busy =
    changeRole.isPending ||
    assignDesignation.isPending ||
    removeDesignation.isPending ||
    setOverride.isPending ||
    removeOverride.isPending;
  const eligibleDesignations = compatibleDesignations(account.role);
  const currentDesignations =
    assignedData?.designations ?? account.designations;
  const capabilities = effectiveData?.capabilities ?? [];
  const selectedOverrideCapability = overrideCapability
    ? capabilities.find((capability) => capability.code === overrideCapability)
    : undefined;
  const missingGrantRequirements =
    overrideEffect === Effect.GRANT
      ? (selectedOverrideCapability?.missing_required_capabilities ?? [])
      : [];
  const grantDependencyBlocked = missingGrantRequirements.length > 0;

  function capabilityName(code: CapabilityCode): string {
    return capabilities.find((capability) => capability.code === code)?.name ?? "Permission details not loaded";
  }

  function reviewOverride(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!overrideCapability || !overrideReason.trim()) return;
    if (grantDependencyBlocked) {
      action.setError(
        `Grant ${missingGrantRequirements.map(capabilityName).join(", ")} first.`,
      );
      return;
    }
    const expiresAt = overrideExpiry
      ? institutionalDateTimeInputToISO(overrideExpiry)
      : null;
    if (overrideExpiry && !expiresAt) {
      action.setError(null);
      setOverrideExpiryError("Enter a valid expiry date and time.");
      return;
    }
    action.setError(null);
    setOverrideExpiryError(null);
    setOverrideOpen(false);
    setConfirm({
      kind: "setOverride",
      capability: overrideCapability,
      effect: overrideEffect,
      reason: overrideReason.trim(),
      expires_at: expiresAt,
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
              "Couldn't change role. Try again.",
              () => setConfirm(null),
              undefined,
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
              "Couldn't assign designation. Try again.",
              () => setConfirm(null),
              undefined,
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
              "Couldn't remove designation. Try again.",
              () => setConfirm(null),
              undefined,
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
              "Couldn't set override. Try again.",
              () => setConfirm(null),
              undefined,
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
              "Couldn't remove override. Try again.",
              () => setConfirm(null),
              undefined,
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
      setOverrideExpiryError(null);
    }
    await invalidate();
    action.setNotice(
      item.kind === "removeOverride"
        ? "Override removed. Access updated."
        : "Access change saved.",
    );
  }

  function confirmationText(
    item: NonNullable<Confirmation>,
  ): [string, string, string, string] {
    const name = accountName(account);
    if (item.kind === "role")
      return [
        `Change ${name}'s role from ${roleLabels[account.role]} to ${roleLabels[item.role]}?`,
        `${name} will be signed out everywhere and will need to sign in again on every device.${account.role === "FACULTY" ? " The Faculty home College will be cleared; its history stays in the activity record." : ""}${item.role === "FACULTY" ? " Digital Referrals are not offered; assign the Faculty home College on the account overview." : ""}${item.role === "STUDENT" && !account.student_lifecycle_status ? " The account will begin with current Student status." : ""}`,
        "Change role",
        "Changing role…",
      ];
    if (item.kind === "assign")
      return [
        `Assign ${designationLabels[item.designation]} to ${name}?`,
        `${name}'s access will change with this designation. They will be signed out everywhere and will need to sign in again on every device.`,
        "Assign designation",
        "Assigning…",
      ];
    if (item.kind === "removeDesignation")
      return [
        `Remove ${designationLabels[item.designation]} from ${name}?`,
        `${name} will lose the access this designation grants. They will be signed out everywhere and will need to sign in again on every device.`,
        "Remove designation",
        "Removing…",
      ];
    if (item.kind === "setOverride") {
      const affectedDependents =
        item.effect === Effect.REVOKE
          ? capabilities.filter(
              (capability) =>
                capability.effective &&
                capability.required_capabilities.includes(item.capability),
            )
          : [];
      const dependencyConsequence = affectedDependents.length
        ? ` This will also make ${affectedDependents
            .map((capability) => capability.name)
            .join(", ")} unusable until the required permission is restored; their grants and overrides stay recorded.`
        : "";
      return [
        `${item.effect === Effect.GRANT ? "Grant" : "Revoke"} ${capabilityName(item.capability)} for ${name}?`,
        `Reason: ${item.reason}${
          item.expires_at
            ? `. Expires: ${formatInstitutionalDateTime(item.expires_at)} ${INSTITUTION_TIME_ZONE_LABEL}.`
            : ". No expiry set."
        }${dependencyConsequence} ${name} will be signed out everywhere and will need to sign in again on every device.`,
        "Set override",
        "Setting override…",
      ];
    }
    return [
      `Remove ${name}'s ${capabilityName(item.capability)} override?`,
      `${name}'s access will go back to what their role, designations and remaining overrides allow, with required permissions still applying. They will be signed out everywhere and will need to sign in again on every device.`,
      "Remove override",
      "Removing override…",
    ];
  }

  const confirmation = confirm ? confirmationText(confirm) : null;

  return (
    <div className="space-y-5">
      <Panel aria-labelledby="role-heading">
        <PanelHeader
          title="Role"
          titleId="role-heading"
          description={
            <>
              Current role:{" "}
              <span className="font-semibold text-ink">
                {roleLabels[account.role]}
              </span>
            </>
          }
        />
        <PanelBody>
        {self ? (
          <p className="text-sm text-muted">
            You cannot change your own administrative authority here.
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <div className="grid w-full max-w-xs gap-1.5">
              <Label htmlFor="managed-role">New role</Label>
              <Select
                id="managed-role"
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
              </Select>
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
        </PanelBody>
      </Panel>

      {assigned.isError && assignedData ? <RefreshFailureNotice onRetry={() => void assigned.refetch()} retrying={assigned.isFetching} /> : null}
      <Panel aria-labelledby="designations-heading">
        <PanelHeader title="Institutional designations" titleId="designations-heading" />
        {assigned.isError && !assignedData ? (
          <div role="alert" className="px-4 py-5 text-sm text-danger sm:px-5">
            {managedAccountError(
              assigned.error,
              "Couldn't load designations. Try again.",
            )}{" "}
            <button
              type="button"
              className="min-h-10 font-semibold underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              onClick={() => void assigned.refetch()}
            >
              Retry
            </button>
          </div>
        ) : assigned.isPending ? (
          <LoadingRegion label="Loading designations…" className="px-4 py-5 sm:px-5">
            <Skeleton className="h-12 w-full" />
          </LoadingRegion>
        ) : (
          <PanelBody>
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
            ) : mayManageDesignations && !assigned.isError ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {eligibleDesignations
                  .filter((designation) => !currentDesignations.includes(designation))
                  .map((designation) => (
                    <Button
                      key={designation}
                      variant="secondary"
                      onClick={() => setConfirm({ kind: "assign", designation })}
                    >
                      Assign {designationLabels[designation]}
                    </Button>
                  ))}
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
                {eligibleDesignations.length === 0 && currentDesignations.length === 0 ? (
                  <p className="text-sm text-muted">
                    No institutional designation is compatible with this role.
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">
                You can view these designations, but cannot change them with this account.
              </p>
            )}
          </PanelBody>
        )}
      </Panel>

      {effective.isError && effectiveData ? <RefreshFailureNotice onRetry={() => void effective.refetch()} retrying={effective.isFetching} /> : null}
      <Panel aria-labelledby="effective-heading">
        <PanelHeader
          title="Effective access"
          titleId="effective-heading"
          description="Current access resulting from this account's role, designations, and overrides."
        />
        {effective.isPending ? (
          <RowsSkeleton label="Loading effective access…" rows={5} />
        ) : !effectiveData ? (
          <div role="alert" className="px-4 py-5 text-sm text-danger sm:px-5">
            {managedAccountError(
              effective.error,
              "Couldn't load effective access. Try again.",
            )}{" "}
            <button
              type="button"
              className="min-h-10 font-semibold underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              onClick={() => void effective.refetch()}
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="max-h-[40rem] overflow-auto rounded-b-sm">
            <table className={`${dataTable.table} min-w-[43rem]`}>
              <caption className="sr-only">Effective access</caption>
              <thead className={`${dataTable.head} sticky top-0 z-10`}>
                <tr>
                  <th scope="col" className={dataTable.headerCell}>
                    Permission
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Effective
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Granted by
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Override
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {effectiveData.capabilities.map((capability) => (
                  <tr key={capability.code} className={dataTable.row}>
                    <th
                      scope="row"
                      className={`${dataTable.cell} font-semibold text-ink`}
                    >
                      {capability.name}
                      <span className="mt-1 block font-normal text-muted">
                        {capability.description}
                      </span>
                      {capability.required_capabilities.length ? (
                        <span className="mt-2 block font-normal text-muted">
                          Requires:{" "}
                          {capability.required_capabilities
                            .map(capabilityName)
                            .join(", ")}
                        </span>
                      ) : null}
                      {capability.missing_required_capabilities.length ? (
                        <span className="mt-1 block font-normal text-warning">
                          Access blocked because:{" "}
                          {capability.missing_required_capabilities
                            .map(capabilityName)
                            .join(", ")}{" "}
                          {capability.missing_required_capabilities.length === 1
                            ? "is"
                            : "are"}{" "}
                          not granted.
                        </span>
                      ) : null}
                    </th>
                    <td className={dataTable.cell}>
                      {capability.effective ? "Yes" : "No"}
                    </td>
                    <td className={dataTable.cell}>
                      {capability.baseline_sources.length
                        ? capability.baseline_sources
                            .map((source) =>
                              source.type === "ROLE" && isRoleCode(source.code)
                                ? `Role: ${roleLabels[source.code]}`
                                : source.type === "DESIGNATION" &&
                                    isDesignationCode(source.code)
                                  ? `Designation: ${designationLabels[source.code]}`
                                  : "Other account assignment",
                            )
                            .join(", ")
                        : "—"}
                    </td>
                    <td className={dataTable.cell}>
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
      </Panel>

      {overrides.isError && overridesData ? <RefreshFailureNotice onRetry={() => void overrides.refetch()} retrying={overrides.isFetching} /> : null}
      <Panel aria-labelledby="overrides-heading">
        <PanelHeader
          title="Permission overrides"
          titleId="overrides-heading"
          description="Overrides are exceptional changes to role and designation access."
          actions={
            !self && account.role !== "FACULTY" && effective.isSuccess && !overrides.isError ? (
              <Button
                variant="secondary"
                onClick={() => {
                  action.setError(null);
                  setOverrideExpiryError(null);
                  setOverrideOpen(true);
                }}
              >
                Set override
              </Button>
            ) : null
          }
        />
        {self ? (
          <p className="border-b border-border px-4 py-3 text-sm text-muted sm:px-5">
            You cannot change your own permission overrides here.
          </p>
        ) : null}
        {overrides.isPending ? (
          <RowsSkeleton label="Loading permission overrides…" rows={2} />
        ) : !overridesData ? (
          <div role="alert" className="px-4 py-5 text-sm text-danger sm:px-5">
            {managedAccountError(
              overrides.error,
              "Couldn't load overrides. Try again.",
            )}{" "}
            <button
              type="button"
              className="min-h-10 font-semibold underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              onClick={() => void overrides.refetch()}
            >
              Retry
            </button>
          </div>
        ) : overridesData.overrides.length === 0 ? (
          <PanelMessage>No permission overrides are recorded.</PanelMessage>
        ) : (
          <div className="divide-y divide-border">
            {overridesData.overrides.map((override) => {
              const capability = effectiveData?.capabilities.find(
                (item) => item.code === override.capability,
              );
              const active = capability?.override?.active;
              return (
                <div
                  key={override.capability}
                  className="flex flex-wrap items-start justify-between gap-4 px-4 py-4 text-sm sm:px-5"
                >
                  <div>
                    <p className="font-semibold text-ink">
                      {capability?.name ?? "Permission details not loaded"} ·{" "}
                      {override.effect === Effect.GRANT ? "Grant" : "Revoke"} ·{" "}
                      {active === true
                        ? "Active"
                        : active === false
                          ? "Expired"
                          : "Status not confirmed"}
                    </p>
                    <p className="mt-1 text-muted">Reason: {override.reason}</p>
                    <p className="mt-1 text-muted">
                      Created {formatAccountDate(override.created_at)} by{" "}
                      {override.created_by?.full_name ||
                        override.created_by?.email ||
                        "Unknown"}
                      . Expiry:{" "}
                      {override.expires_at
                        ? `${formatInstitutionalDateTime(
                            override.expires_at,
                          )} ${INSTITUTION_TIME_ZONE_LABEL}`
                        : "None"}
                      .
                    </p>
                  </div>
                  {!self && !overrides.isError && !effective.isError ? (
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
      </Panel>

      <ManagedActionFeedback action={action} showMessages={confirm === null} />
      <Dialog open={overrideOpen} onOpenChange={setOverrideOpen}>
        <DialogContent dismissible={!busy}>
          <DialogTitle>Set permission override</DialogTitle>
          <DialogDescription>
            Choose a permission to grant or revoke, and enter a reason.
          </DialogDescription>
          <form className="mt-6 space-y-4" onSubmit={reviewOverride}>
            <div className="grid gap-2">
              <Label htmlFor="override-capability">Permission</Label>
              <Select
                id="override-capability"
                required
                value={overrideCapability}
                onChange={(event) => {
                  const code = effectiveData?.capabilities.find(
                    (item) => item.code === event.target.value,
                  )?.code;
                  action.setError(null);
                  setOverrideCapability(code ?? "");
                }}
              >
                <option value="">Select permission</option>
                {effectiveData?.capabilities.map((capability) => (
                  <option key={capability.code} value={capability.code}>
                    {capability.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="override-effect">Effect</Label>
              <Select
                id="override-effect"
                value={overrideEffect}
                onChange={(event) => {
                  action.setError(null);
                  setOverrideEffect(
                    event.target.value === Effect.REVOKE
                      ? Effect.REVOKE
                      : Effect.GRANT,
                  );
                }}
              >
                <option value={Effect.GRANT}>Grant</option>
                <option value={Effect.REVOKE}>Revoke</option>
              </Select>
            </div>
            {selectedOverrideCapability?.required_capabilities.length ? (
              <div className="rounded-sm bg-surface-subtle px-3 py-2.5 text-sm leading-6 text-muted">
                <p>
                  This permission requires:{" "}
                  {selectedOverrideCapability.required_capabilities
                    .map(capabilityName)
                    .join(", ")}.
                </p>
                {grantDependencyBlocked ? (
                  <p className="mt-1 text-warning">
                    Grant the required permission first.
                  </p>
                ) : null}
              </div>
            ) : null}
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
                aria-invalid={overrideExpiryError ? true : undefined}
                aria-describedby={`override-expiry-hint${overrideExpiryError ? " override-expiry-error" : ""}`}
                onChange={(event) => {
                  setOverrideExpiry(event.target.value);
                  setOverrideExpiryError(null);
                }}
              />
              <p id="override-expiry-hint" className="text-xs leading-5 text-muted">
                Times use {INSTITUTION_TIME_ZONE_LABEL}.
              </p>
              {overrideExpiryError ? (
                <p id="override-expiry-error" className="text-sm text-danger">
                  {overrideExpiryError}
                </p>
              ) : null}
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
              <Button type="submit" disabled={grantDependencyBlocked}>
                Review override
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
      <ConsequentialActionDialog
        open={confirm !== null}
        title={confirmation?.[0] ?? "Review access change"}
        confirmLabel={confirmation?.[2] ?? "Apply access change"}
        pendingLabel={confirmation?.[3] ?? "Applying change…"}
        pending={busy}
        error={action.error}
        variant={
          confirm?.kind === "removeDesignation" || confirm?.kind === "removeOverride"
            ? "danger"
            : "primary"
        }
        onOpenChange={(open) => {
          if (!open) setConfirm(null);
        }}
        onConfirm={() => void confirmAction()}
      >
        <p>{confirmation?.[1]}</p>
      </ConsequentialActionDialog>
    </div>
  );
}

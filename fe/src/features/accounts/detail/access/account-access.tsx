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
  const eligibleDesignation = compatibleDesignation(account.role);
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
    return capabilities.find((capability) => capability.code === code)?.name ?? code;
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
              "Role could not be changed.",
              () => setConfirm(null),
              undefined,
              () => setConfirm(item),
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
              undefined,
              () => setConfirm(item),
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
              undefined,
              () => setConfirm(item),
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
              undefined,
              () => setConfirm(item),
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
              undefined,
              () => setConfirm(item),
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
        ? "Override removed. Effective access has been refreshed."
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
        `This changes the account's baseline COMPASS access. If completed, ${name} will be signed out of active COMPASS sessions, saved trusted-browser authorization will be removed, and they will need to authenticate again.${item.role === "STUDENT" && !account.student_lifecycle_status ? " The account will also begin with current student status." : ""}`,
        "Change role",
        "Changing role…",
      ];
    if (item.kind === "assign")
      return [
        `Assign ${designationLabels[item.designation]} to ${name}?`,
        `This designation changes the account's institutional authority. If completed, ${name} will be signed out of active COMPASS sessions, saved trusted-browser authorization will be removed, and they will need to authenticate again.`,
        "Assign designation",
        "Assigning…",
      ];
    if (item.kind === "removeDesignation")
      return [
        `Remove ${designationLabels[item.designation]} from ${name}?`,
        `This removes designation-based access. If completed, ${name} will be signed out of active COMPASS sessions, saved trusted-browser authorization will be removed, and they will need to authenticate again.`,
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
            .join(", ")} ineffective while this capability remains unavailable. Their underlying grants or overrides remain recorded.`
        : "";
      return [
        `${item.effect === Effect.GRANT ? "Grant" : "Revoke"} ${capabilityName(item.capability)} for ${name}?`,
        `Reason: ${item.reason}${
          item.expires_at
            ? `. Expires: ${formatInstitutionalDateTime(item.expires_at)} ${INSTITUTION_TIME_ZONE_LABEL}.`
            : ". No expiry set."
        }${dependencyConsequence} If completed, ${name} will be signed out of active COMPASS sessions, saved trusted-browser authorization will be removed, and they will need to authenticate again.`,
        "Set override",
        "Setting override…",
      ];
    }
    return [
      `Remove ${name}'s ${capabilityName(item.capability)} override?`,
      `Effective access will be recalculated from the account's role, designations, remaining overrides, and capability requirements. If completed, ${name} will be signed out of active COMPASS sessions, saved trusted-browser authorization will be removed, and they will need to authenticate again.`,
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
              "Designations could not be loaded.",
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
              "Effective access could not be loaded.",
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
                    Capability
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
                          Unavailable because:{" "}
                          {capability.missing_required_capabilities
                            .map(capabilityName)
                            .join(", ")}{" "}
                          {capability.missing_required_capabilities.length === 1
                            ? "is"
                            : "are"}{" "}
                          not currently effective.
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
                                  : `${source.type}: ${source.code}`,
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
          title="Capability overrides"
          titleId="overrides-heading"
          description="Overrides are exceptional changes to role and designation access."
          actions={
            !self && effective.isSuccess && !overrides.isError ? (
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
            You cannot change your own capability overrides here.
          </p>
        ) : null}
        {overrides.isPending ? (
          <RowsSkeleton label="Loading capability overrides…" rows={2} />
        ) : !overridesData ? (
          <div role="alert" className="px-4 py-5 text-sm text-danger sm:px-5">
            {managedAccountError(
              overrides.error,
              "Overrides could not be loaded.",
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
          <PanelMessage>No capability overrides are recorded.</PanelMessage>
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
          <DialogTitle>Set capability override</DialogTitle>
          <DialogDescription>
            Choose one exception to this account&apos;s baseline access. A
            reason is required.
          </DialogDescription>
          <form className="mt-6 space-y-4" onSubmit={reviewOverride}>
            <div className="grid gap-2">
              <Label htmlFor="override-capability">Capability</Label>
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
                <option value="">Select capability</option>
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
                  This capability requires:{" "}
                  {selectedOverrideCapability.required_capabilities
                    .map(capabilityName)
                    .join(", ")}.
                </p>
                {grantDependencyBlocked ? (
                  <p className="mt-1 text-warning">
                    Grant the required capability first.
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

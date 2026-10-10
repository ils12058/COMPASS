"use client";

import { FormEvent, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, ListChecks, Plus, ShieldCheck, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getAccountsGetEffectiveAccessQueryKey,
  getAccountsGetQueryKey,
  getAccountsListCapabilityOverridesQueryKey,
  getAccountsListDesignationsQueryKey,
  useAccountsAssignDesignation,
  useAccountsGetEffectiveAccess,
  useAccountsListCapabilityOverrides,
  useAccountsListDesignations,
  useAccountsRemoveCapabilityOverride,
  useAccountsRemoveDesignation,
  useAccountsSetCapabilityOverride,
} from "@/lib/api/generated/accounts/accounts";
import {
  CapabilityCode,
  DesignationCode,
  Effect,
} from "@/lib/api/generated/model";
import type {
  AccountDetailResponse,
  CapabilityCode as CapabilityCodeType,
  DesignationCode as DesignationCodeType,
  Effect as EffectType,
} from "@/lib/api/generated/model";
import {
  AccountActionMessage,
  AccountSection,
  DesignationBadge,
  accountAdminError,
} from "@/features/portal/admin/accounts/portal-it-admin-account-shared";
import { formatAdminDate, formatAdminLabel } from "@/features/portal/admin/portal-it-admin-shared";

const selectClassName =
  "h-10 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function PortalItAdminAccountAccess({
  account,
}: {
  account: AccountDetailResponse;
}) {
  const queryClient = useQueryClient();
  const accessQuery = useAccountsGetEffectiveAccess(account.id, {
    query: { retry: false, staleTime: 30_000 },
  });
  const designationQuery = useAccountsListDesignations(account.id, {
    query: { retry: false, staleTime: 30_000 },
  });
  const overridesQuery = useAccountsListCapabilityOverrides(account.id, {
    query: { retry: false, staleTime: 30_000 },
  });
  const assignDesignation = useAccountsAssignDesignation();
  const removeDesignation = useAccountsRemoveDesignation();
  const setOverride = useAccountsSetCapabilityOverride();
  const removeOverride = useAccountsRemoveCapabilityOverride();
  const [designation, setDesignation] = useState<DesignationCodeType>(DesignationCode.DPO);
  const [capability, setCapability] = useState<CapabilityCodeType>(CapabilityCode.accountsview);
  const [effect, setEffect] = useState<EffectType>(Effect.GRANT);
  const [reason, setReason] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [filter, setFilter] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const access = accessQuery.data?.data;
  const designations = designationQuery.data?.data.designations ?? account.designations;
  const overrides = overridesQuery.data?.data.overrides ?? [];
  const capabilities = useMemo(() => {
    const normalizedFilter = filter.trim().toLowerCase();
    return (access?.capabilities ?? [])
      .filter((item) => showAll || item.effective)
      .filter((item) => {
        if (!normalizedFilter) {
          return true;
        }

        return `${item.name} ${item.code} ${item.description}`.toLowerCase().includes(normalizedFilter);
      })
      .sort((first, second) => first.name.localeCompare(second.name));
  }, [access?.capabilities, filter, showAll]);

  async function refreshAccess() {
    await queryClient.invalidateQueries({ queryKey: getAccountsGetQueryKey(account.id) });
    await queryClient.invalidateQueries({ queryKey: getAccountsGetEffectiveAccessQueryKey(account.id) });
    await queryClient.invalidateQueries({ queryKey: getAccountsListCapabilityOverridesQueryKey(account.id) });
    await queryClient.invalidateQueries({ queryKey: getAccountsListDesignationsQueryKey(account.id) });
  }

  async function assignSelectedDesignation() {
    setError(null);
    setMessage(null);

    try {
      await assignDesignation.mutateAsync({ userId: account.id, designationCode: selectedDesignation });
      await refreshAccess();
      setMessage(`${formatAdminLabel(selectedDesignation)} was assigned to this account.`);
    } catch (caught) {
      setError(accountAdminError(caught, "We couldn’t assign that designation. Please try again."));
    }
  }

  async function removeSelectedDesignation(value: DesignationCodeType) {
    setError(null);
    setMessage(null);

    try {
      await removeDesignation.mutateAsync({ userId: account.id, designationCode: value });
      await refreshAccess();
      setMessage(`${formatAdminLabel(value)} was removed from this account.`);
    } catch (caught) {
      setError(accountAdminError(caught, "We couldn’t remove that designation. Please try again."));
    }
  }

  async function saveOverride(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    if (!reason.trim()) {
      setError("Add a reason before saving an override.");
      return;
    }

    try {
      await setOverride.mutateAsync({
        userId: account.id,
        capabilityCode: capability,
        data: {
          effect,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
          reason: reason.trim(),
        },
      });
      await refreshAccess();
      setReason("");
      setExpiresAt("");
      setMessage(`${formatAdminLabel(capability)} override saved.`);
    } catch (caught) {
      setError(accountAdminError(caught, "We couldn’t save that override. Please try again."));
    }
  }

  async function removeSelectedOverride(value: CapabilityCodeType) {
    setError(null);
    setMessage(null);

    try {
      await removeOverride.mutateAsync({ userId: account.id, capabilityCode: value });
      await refreshAccess();
      setMessage(`${formatAdminLabel(value)} override removed.`);
    } catch (caught) {
      setError(accountAdminError(caught, "We couldn’t remove that override. Please try again."));
    }
  }

  const availableDesignations = Object.values(DesignationCode).filter(
    (value) => !designations.includes(value),
  );
  const selectedDesignation = availableDesignations.includes(designation)
    ? designation
    : availableDesignations[0] ?? DesignationCode.DPO;

  return (
    <div className="space-y-5">
      <AccountSection
        icon={KeyRound}
        title="Designations"
        description="Review the additional responsibilities assigned to this account."
      >
        <div className="flex flex-wrap gap-2">
          {designations.length ? (
            designations.map((value) => (
              <div key={value} className="flex items-center gap-2 rounded-full bg-[var(--compass-surface-subtle)] pl-1">
                <DesignationBadge designation={value} />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label={`Remove ${formatAdminLabel(value)} designation`}
                  disabled={removeDesignation.isPending}
                  onClick={() => void removeSelectedDesignation(value)}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No designations are assigned.</p>
          )}
        </div>
        {availableDesignations.length ? (
          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1">
              <Label htmlFor="admin-account-designation">Add designation</Label>
              <select
                id="admin-account-designation"
                className={`${selectClassName} mt-2`}
                value={selectedDesignation}
                onChange={(event) => setDesignation(event.target.value as DesignationCodeType)}
              >
                {availableDesignations.map((value) => (
                  <option key={value} value={value}>
                    {formatAdminLabel(value)}
                  </option>
                ))}
              </select>
            </div>
            <Button type="button" variant="outline" disabled={assignDesignation.isPending} onClick={() => void assignSelectedDesignation()}>
              <Plus aria-hidden="true" />
              {assignDesignation.isPending ? "Assigning…" : "Assign designation"}
            </Button>
          </div>
        ) : (
          <p className="mt-5 text-sm text-muted-foreground">All available designations are assigned.</p>
        )}
      </AccountSection>

      <AccountSection
        icon={ListChecks}
        title="Effective access"
        description="See the permissions this account receives from its role, designations, and any active override."
      >
        {accessQuery.isPending ? (
          <div className="h-48 animate-pulse rounded-2xl bg-muted" aria-live="polite" />
        ) : accessQuery.isError ? (
          <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] p-4">
            <p className="text-sm text-muted-foreground" role="alert">We couldn’t load effective access right now.</p>
            <Button className="mt-3" type="button" size="sm" variant="outline" onClick={() => void accessQuery.refetch()}>
              Try again
            </Button>
          </div>
        ) : access ? (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">Effective</p>
                <p className="mt-2 font-heading text-2xl font-bold">{access.effective_capabilities.length}</p>
              </div>
              <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">Available to review</p>
                <p className="mt-2 font-heading text-2xl font-bold">{access.capabilities.length}</p>
              </div>
              <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">Overrides</p>
                <p className="mt-2 font-heading text-2xl font-bold">{overrides.length}</p>
              </div>
            </div>
            <div className="mt-5 flex flex-col gap-3 sm:flex-row">
              <Input
                aria-label="Filter capabilities"
                className="h-10"
                placeholder="Filter permissions"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              />
              <Button type="button" variant="outline" className="sm:w-auto" onClick={() => setShowAll((current) => !current)}>
                {showAll ? "Show effective only" : "Show all"}
              </Button>
            </div>
            {capabilities.length ? (
              <ul className="mt-4 space-y-2">
                {capabilities.map((item) => (
                  <li key={item.code} className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold">{item.name}</p>
                          <Badge variant={item.effective ? "secondary" : "outline"}>
                            {item.effective ? "Effective" : "Not effective"}
                          </Badge>
                          {item.override ? (
                            <Badge variant="outline" className="border-[var(--compass-brand-gold)]/50 text-[var(--compass-brand-maroon)]">Override</Badge>
                          ) : null}
                        </div>
                        <p className="mt-1 break-all text-xs text-muted-foreground">{item.code}</p>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.description}</p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-1.5 sm:max-w-56 sm:justify-end">
                        {item.baseline_sources.map((source) => (
                          <Badge key={`${source.type}-${source.code}`} variant="outline">
                            {formatAdminLabel(source.type)}: {formatAdminLabel(source.code)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 rounded-2xl border border-dashed p-4 text-sm text-muted-foreground">
                No permissions match this view.
              </p>
            )}
          </>
        ) : null}
      </AccountSection>

      <AccountSection
        icon={ShieldCheck}
        title="Capability overrides"
        description="Apply a documented, account-specific grant or restriction when baseline access is not enough."
      >
        <form className="grid gap-4 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4" onSubmit={saveOverride}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="admin-account-capability">Permission</Label>
              <select
                id="admin-account-capability"
                className={`${selectClassName} mt-2`}
                value={capability}
                onChange={(event) => setCapability(event.target.value as CapabilityCodeType)}
              >
                {Object.values(CapabilityCode).map((value) => (
                  <option key={value} value={value}>
                    {formatAdminLabel(value)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="admin-account-effect">Effect</Label>
              <select
                id="admin-account-effect"
                className={`${selectClassName} mt-2`}
                value={effect}
                onChange={(event) => setEffect(event.target.value as EffectType)}
              >
                <option value={Effect.GRANT}>Grant</option>
                <option value={Effect.REVOKE}>Revoke</option>
              </select>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="admin-account-override-reason">Reason</Label>
              <Input
                id="admin-account-override-reason"
                className="mt-2 h-10"
                placeholder="Why is this exception needed?"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="admin-account-override-expiry">Expires (optional)</Label>
              <Input
                id="admin-account-override-expiry"
                className="mt-2 h-10"
                type="datetime-local"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
              />
            </div>
          </div>
          <div>
            <Button type="submit" disabled={setOverride.isPending}>
              <ShieldCheck aria-hidden="true" />
              {setOverride.isPending ? "Saving…" : "Save override"}
            </Button>
          </div>
        </form>

        {overridesQuery.isPending ? (
          <div className="mt-4 h-32 animate-pulse rounded-2xl bg-muted" aria-live="polite" />
        ) : overrides.length ? (
          <ul className="mt-4 space-y-3">
            {overrides.map((override) => (
              <li key={override.capability} className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold">{formatAdminLabel(override.capability)}</p>
                      <Badge variant={override.effect === Effect.GRANT ? "secondary" : "destructive"}>
                        {formatAdminLabel(override.effect)}
                      </Badge>
                    </div>
                    <p className="mt-1 break-all text-xs text-muted-foreground">{override.capability}</p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{override.reason}</p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Added {formatAdminDate(override.created_at)} · {override.expires_at ? `Expires ${formatAdminDate(override.expires_at)}` : "No expiry"}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={removeOverride.isPending}
                    onClick={() => void removeSelectedOverride(override.capability)}
                  >
                    <Trash2 aria-hidden="true" />
                    Remove
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 rounded-2xl border border-dashed p-4 text-sm text-muted-foreground">
            No account-specific overrides are assigned.
          </p>
        )}
      </AccountSection>

      <AccountActionMessage error={error} message={message} />
    </div>
  );
}

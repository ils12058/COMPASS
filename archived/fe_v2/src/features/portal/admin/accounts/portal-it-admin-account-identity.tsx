"use client";

import { FormEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { IdCard, Mail, Save } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getAccountsGetQueryKey,
  getAccountsListQueryKey,
  useAccountsUpdateIdentity,
} from "@/lib/api/generated/accounts/accounts";
import type { AccountDetailResponse, IdentityUpdateRequest } from "@/lib/api/generated/model";
import {
  AccountActionMessage,
  AccountField,
  AccountSection,
  VerificationBadge,
  accountAdminError,
} from "@/features/portal/admin/accounts/portal-it-admin-account-shared";

type IdentityDraft = {
  first_name: string;
  institutional_id: string;
  last_name: string;
  middle_name: string;
  suffix: string;
};

function getIdentityDraft(account: AccountDetailResponse): IdentityDraft {
  return {
    first_name: account.first_name,
    institutional_id: account.institutional_id ?? "",
    last_name: account.last_name,
    middle_name: account.middle_name,
    suffix: account.suffix,
  };
}

export function PortalItAdminAccountIdentity({
  account,
}: {
  account: AccountDetailResponse;
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<IdentityDraft>(() => getIdentityDraft(account));
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const updateIdentity = useAccountsUpdateIdentity();

  function updateDraft(field: keyof IdentityDraft, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  async function saveIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    if (!draft.first_name.trim() || !draft.last_name.trim()) {
      setError("First name and last name are required.");
      return;
    }

    const changes: IdentityUpdateRequest = {
      first_name: draft.first_name.trim(),
      institutional_id: draft.institutional_id.trim() || null,
      last_name: draft.last_name.trim(),
      middle_name: draft.middle_name.trim(),
      suffix: draft.suffix.trim(),
    };

    try {
      const response = await updateIdentity.mutateAsync({
        userId: account.id,
        data: changes,
      });
      queryClient.setQueryData(getAccountsGetQueryKey(account.id), response);
      await queryClient.invalidateQueries({ queryKey: getAccountsListQueryKey() });
      setEditing(false);
      setMessage("The account identity is up to date.");
    } catch (caught) {
      setError(accountAdminError(caught, "We couldn’t save the account identity. Please try again."));
    }
  }

  return (
    <AccountSection
      icon={IdCard}
      title="Identity"
      description="Review the institutional identity attached to this account."
    >
      {editing ? (
        <form className="space-y-5" onSubmit={saveIdentity}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="admin-account-first-name">First name</Label>
              <Input
                id="admin-account-first-name"
                className="mt-2 h-10"
                value={draft.first_name}
                onChange={(event) => updateDraft("first_name", event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="admin-account-last-name">Last name</Label>
              <Input
                id="admin-account-last-name"
                className="mt-2 h-10"
                value={draft.last_name}
                onChange={(event) => updateDraft("last_name", event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="admin-account-middle-name">Middle name</Label>
              <Input
                id="admin-account-middle-name"
                className="mt-2 h-10"
                value={draft.middle_name}
                onChange={(event) => updateDraft("middle_name", event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="admin-account-suffix">Suffix</Label>
              <Input
                id="admin-account-suffix"
                className="mt-2 h-10"
                value={draft.suffix}
                onChange={(event) => updateDraft("suffix", event.target.value)}
                placeholder="Jr., III, etc."
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="admin-account-institutional-id">Institutional ID</Label>
              <Input
                id="admin-account-institutional-id"
                className="mt-2 h-10"
                value={draft.institutional_id}
                onChange={(event) => updateDraft("institutional_id", event.target.value)}
                placeholder="Optional"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={updateIdentity.isPending}>
              <Save aria-hidden="true" />
              {updateIdentity.isPending ? "Saving…" : "Save identity"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={updateIdentity.isPending}
              onClick={() => {
                setDraft(getIdentityDraft(account));
                setEditing(false);
                setError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <>
          <dl className="grid gap-3 sm:grid-cols-2">
            <AccountField label="First name" value={account.first_name} />
            <AccountField label="Last name" value={account.last_name} />
            <AccountField label="Middle name" value={account.middle_name} />
            <AccountField label="Suffix" value={account.suffix} />
            <AccountField label="Institutional ID" value={account.institutional_id ?? "Not provided"} />
            <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
              <dt className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
                <Mail aria-hidden="true" className="size-3.5" />
                Email
              </dt>
              <dd className="mt-2 flex flex-wrap items-center gap-2 break-words text-sm font-semibold text-foreground">
                <span>{account.email}</span>
                <VerificationBadge verified={account.email_verified} />
              </dd>
            </div>
          </dl>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button type="button" variant="outline" onClick={() => setEditing(true)}>
              Edit identity
            </Button>
            <Badge variant="outline">
              {account.password_configured ? "Password configured" : "Password not configured"}
            </Badge>
          </div>
        </>
      )}
      <div className="mt-5">
        <AccountActionMessage error={error} message={message} />
      </div>
    </AccountSection>
  );
}

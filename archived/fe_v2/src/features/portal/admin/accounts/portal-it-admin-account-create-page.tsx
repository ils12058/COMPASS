"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, UserPlus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getAccountsListQueryKey,
  useAccountsCreate,
} from "@/lib/api/generated/accounts/accounts";
import { RoleCode } from "@/lib/api/generated/model";
import type { AccountCreateRequest, AccountDetailResponse, RoleCode as RoleCodeType } from "@/lib/api/generated/model";
import {
  AccountActionMessage,
  AccountSection,
  accountAdminError,
} from "@/features/portal/admin/accounts/portal-it-admin-account-shared";
import { formatAdminLabel } from "@/features/portal/admin/portal-it-admin-shared";

const selectClassName =
  "h-10 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

type AccountCreateDraft = {
  email: string;
  first_name: string;
  institutional_id: string;
  is_active: boolean;
  last_name: string;
  middle_name: string;
  role: RoleCodeType;
  suffix: string;
};

const INITIAL_DRAFT: AccountCreateDraft = {
  email: "",
  first_name: "",
  institutional_id: "",
  is_active: true,
  last_name: "",
  middle_name: "",
  role: RoleCode.STUDENT,
  suffix: "",
};

export function PortalItAdminAccountCreatePage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<AccountCreateDraft>(INITIAL_DRAFT);
  const [createdAccount, setCreatedAccount] = useState<AccountDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const createAccount = useAccountsCreate();

  function updateDraft(field: keyof AccountCreateDraft, value: string | boolean) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setCreatedAccount(null);

    const data: AccountCreateRequest = {
      email: draft.email.trim(),
      first_name: draft.first_name.trim(),
      institutional_id: draft.institutional_id.trim(),
      is_active: draft.is_active,
      last_name: draft.last_name.trim(),
      middle_name: draft.middle_name.trim(),
      role: draft.role,
      suffix: draft.suffix.trim(),
    };

    try {
      const response = await createAccount.mutateAsync({ data });
      setCreatedAccount(response.data);
      await queryClient.invalidateQueries({ queryKey: getAccountsListQueryKey() });
    } catch (caught) {
      setError(accountAdminError(caught, "We couldn’t create the account. Please review the details and try again."));
    }
  }

  if (createdAccount) {
    return (
      <div className="space-y-5">
        <Button asChild type="button" variant="ghost" className="-ml-2">
          <Link href="/portal/admin/accounts">
            <ArrowLeft aria-hidden="true" />
            Back to accounts
          </Link>
        </Button>
        <section className="rounded-3xl border border-[var(--compass-support)]/30 bg-card p-6 shadow-sm sm:p-8">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
            <CheckCircle2 aria-hidden="true" className="size-6" />
          </div>
          <h2 className="mt-5 font-heading text-3xl font-bold tracking-tight">Account created</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
            {createdAccount.full_name} now has a managed COMPASS account. No password was set here; the account owner can complete sign-in setup through the password access flow.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Badge variant="secondary">{formatAdminLabel(createdAccount.role)}</Badge>
            <Badge variant="outline">{createdAccount.email}</Badge>
          </div>
          <div className="mt-6 flex flex-wrap gap-2">
            <Button asChild type="button">
              <Link href={`/portal/admin/accounts/${createdAccount.id}`}>Open account details</Link>
            </Button>
            <Button asChild type="button" variant="outline">
              <Link href="/portal/admin/accounts">Return to directory</Link>
            </Button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Button asChild type="button" variant="ghost" className="-ml-2">
        <Link href="/portal/admin/accounts">
          <ArrowLeft aria-hidden="true" />
          Back to accounts
        </Link>
      </Button>
      <AccountSection
        icon={UserPlus}
        title="Create account"
        description="Add one managed account with its institutional identity and primary role."
      >
        <form className="space-y-6" onSubmit={submit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="create-account-first-name">First name</Label>
              <Input
                id="create-account-first-name"
                className="mt-2 h-10"
                value={draft.first_name}
                onChange={(event) => updateDraft("first_name", event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="create-account-last-name">Last name</Label>
              <Input
                id="create-account-last-name"
                className="mt-2 h-10"
                value={draft.last_name}
                onChange={(event) => updateDraft("last_name", event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="create-account-middle-name">Middle name</Label>
              <Input
                id="create-account-middle-name"
                className="mt-2 h-10"
                value={draft.middle_name}
                onChange={(event) => updateDraft("middle_name", event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="create-account-suffix">Suffix</Label>
              <Input
                id="create-account-suffix"
                className="mt-2 h-10"
                value={draft.suffix}
                onChange={(event) => updateDraft("suffix", event.target.value)}
                placeholder="Jr., III, etc."
              />
            </div>
            <div>
              <Label htmlFor="create-account-institutional-id">Institutional ID</Label>
              <Input
                id="create-account-institutional-id"
                className="mt-2 h-10"
                value={draft.institutional_id}
                onChange={(event) => updateDraft("institutional_id", event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="create-account-email">Email</Label>
              <Input
                id="create-account-email"
                className="mt-2 h-10"
                type="email"
                value={draft.email}
                onChange={(event) => updateDraft("email", event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="create-account-role">Primary role</Label>
              <select
                id="create-account-role"
                className={`${selectClassName} mt-2`}
                value={draft.role}
                onChange={(event) => updateDraft("role", event.target.value as RoleCodeType)}
              >
                {Object.values(RoleCode).map((value) => (
                  <option key={value} value={value}>
                    {formatAdminLabel(value)}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-start gap-3 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:mt-6">
              <input
                type="checkbox"
                className="mt-0.5 size-4 accent-[var(--compass-brand-maroon)]"
                checked={draft.is_active}
                onChange={(event) => updateDraft("is_active", event.target.checked)}
              />
              <span>
                <span className="block text-sm font-semibold">Allow sign-in</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                  Leave enabled when the account should be usable immediately.
                </span>
              </span>
            </label>
          </div>

          <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 text-sm leading-6 text-muted-foreground">
            The account starts without a COMPASS password. Creating it does not mark the email as verified; the account owner must complete the normal password access flow.
          </div>

          <AccountActionMessage error={error} />
          <Button type="submit" disabled={createAccount.isPending}>
            <UserPlus aria-hidden="true" />
            {createAccount.isPending ? "Creating…" : "Create account"}
          </Button>
        </form>
      </AccountSection>
    </div>
  );
}

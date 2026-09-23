"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ManagedActionFeedback,
  useInvalidateManagedAccount,
  useManagedAction,
} from "@/features/accounts/components/account-action";
import {
  isRoleCode,
  roleLabels,
  roles,
} from "@/features/accounts/presentation";
import { useAccountsCreate } from "@/lib/api/generated/accounts/accounts";
import { RoleCode, type AccountCreateRequest } from "@/lib/api/generated/model";

const fieldClass = "grid gap-2";
const selectClass =
  "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function CreateAccount() {
  const router = useRouter();
  const create = useAccountsCreate();
  const action = useManagedAction();
  const invalidate = useInvalidateManagedAccount();
  const [form, setForm] = useState<AccountCreateRequest>({
    institutional_id: "",
    email: "",
    first_name: "",
    middle_name: "",
    last_name: "",
    suffix: "",
    role: RoleCode.STUDENT,
    is_active: true,
  });

  function change<K extends keyof AccountCreateRequest>(
    field: K,
    value: AccountCreateRequest[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await action.run(
      () => create.mutateAsync({ data: form }),
      "The account could not be created.",
    );
    if (!response) return;
    await invalidate();
    router.push(`/portal/accounts/${encodeURIComponent(response.data.id)}`);
  }

  return (
    <section aria-labelledby="create-account-heading" className="max-w-2xl">
      <Link
        href="/portal/accounts"
        className="text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        ← Accounts
      </Link>
      <h1
        id="create-account-heading"
        className="mt-5 font-heading text-3xl font-bold text-ink"
      >
        Create account
      </h1>
      <p className="mt-2 text-sm leading-6 text-muted">
        The account holder can set up a COMPASS password using the registered
        email address.
      </p>
      <form className="mt-8 space-y-6" onSubmit={(event) => void submit(event)}>
        <div className="grid gap-5 sm:grid-cols-2">
          <div className={fieldClass}>
            <Label htmlFor="create-institutional-id">Institutional ID</Label>
            <Input
              id="create-institutional-id"
              required
              value={form.institutional_id}
              onChange={(event) =>
                change("institutional_id", event.target.value)
              }
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-email">Email</Label>
            <Input
              id="create-email"
              type="email"
              required
              value={form.email}
              onChange={(event) => change("email", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-first-name">First name</Label>
            <Input
              id="create-first-name"
              required
              value={form.first_name}
              onChange={(event) => change("first_name", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-middle-name">Middle name</Label>
            <Input
              id="create-middle-name"
              value={form.middle_name ?? ""}
              onChange={(event) => change("middle_name", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-last-name">Last name</Label>
            <Input
              id="create-last-name"
              required
              value={form.last_name}
              onChange={(event) => change("last_name", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-suffix">Suffix</Label>
            <Input
              id="create-suffix"
              value={form.suffix ?? ""}
              onChange={(event) => change("suffix", event.target.value)}
            />
          </div>
          <div className={fieldClass}>
            <Label htmlFor="create-role">Role</Label>
            <select
              id="create-role"
              className={selectClass}
              value={form.role}
              onChange={(event) => {
                if (isRoleCode(event.target.value))
                  change("role", event.target.value);
              }}
            >
              {roles.map((role) => (
                <option key={role} value={role}>
                  {roleLabels[role]}
                </option>
              ))}
            </select>
          </div>
        </div>
        <label className="flex items-center gap-3 text-sm font-medium text-ink">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(event) => change("is_active", event.target.checked)}
            className="size-4 accent-brand"
          />
          Active account
        </label>
        <ManagedActionFeedback action={action} />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating account…" : "Create account"}
          </Button>
          <Link
            href="/portal/accounts"
            className="inline-flex min-h-10 items-center px-3 text-sm font-semibold text-muted hover:underline"
          >
            Cancel
          </Link>
        </div>
      </form>
    </section>
  );
}

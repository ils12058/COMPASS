"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
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
  const [review, setReview] = useState<AccountCreateRequest | null>(null);

  function change<K extends keyof AccountCreateRequest>(
    field: K,
    value: AccountCreateRequest[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    action.setError(null);
    action.setNotice(null);
    setReview({ ...form });
  }

  async function confirmCreate() {
    if (!review) return;
    const reviewed = review;
    const response = await action.run(
      () => create.mutateAsync({ data: reviewed }),
      "The account could not be created.",
      () => setReview(null),
      undefined,
      () => setReview(reviewed),
    );
    if (!response) return;
    setReview(null);
    await invalidate();
    router.push(`/portal/accounts/${encodeURIComponent(response.data.id)}`);
  }

  const reviewName = review
    ? [review.first_name, review.middle_name, review.last_name, review.suffix]
        .filter((part) => part?.trim())
        .join(" ")
    : "";

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
        <ManagedActionFeedback action={action} showMessages={!review} />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={create.isPending}>
            Review account
          </Button>
          <Link
            href="/portal/accounts"
            className="inline-flex min-h-10 items-center px-3 text-sm font-semibold text-muted hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Cancel
          </Link>
        </div>
      </form>
      <ConsequentialActionDialog
        open={review !== null}
        title={review ? `Create account for ${reviewName}?` : "Create account?"}
        confirmLabel="Create account"
        pendingLabel="Creating account…"
        pending={create.isPending}
        error={action.error}
        onOpenChange={(open) => {
          if (!open) setReview(null);
        }}
        onConfirm={() => void confirmCreate()}
      >
        {review ? (
          <>
            <p>Review the account that will be created.</p>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted">Name</dt>
                <dd className="font-semibold text-ink">{reviewName}</dd>
              </div>
              <div>
                <dt className="text-muted">Institutional ID</dt>
                <dd className="font-semibold text-ink">{review.institutional_id}</dd>
              </div>
              <div>
                <dt className="text-muted">Email</dt>
                <dd className="break-words font-semibold text-ink">{review.email}</dd>
              </div>
              <div>
                <dt className="text-muted">Role</dt>
                <dd className="font-semibold text-ink">{roleLabels[review.role]}</dd>
              </div>
              <div>
                <dt className="text-muted">Account status</dt>
                <dd className="font-semibold text-ink">
                  {review.is_active ? "Active" : "Disabled"}
                </dd>
              </div>
            </dl>
            <p>
              {review.is_active
                ? "This account will be active after creation."
                : "This account will be created disabled and cannot sign in until enabled."}
            </p>
            {review.role === RoleCode.STUDENT ? (
              <p>New Student accounts begin with Current Student lifecycle status.</p>
            ) : null}
          </>
        ) : null}
      </ConsequentialActionDialog>
    </section>
  );
}

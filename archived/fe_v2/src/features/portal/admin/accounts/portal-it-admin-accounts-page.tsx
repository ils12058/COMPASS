"use client";

import Link from "next/link";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal, Upload, UserPlus, UsersRound } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiErrorMessage } from "@/features/auth/utils/errors";
import {
  AccountInitials,
  AccountRoleBadge,
  AccountStatusBadge,
  DesignationBadge,
  EmptyAccountState,
  VerificationBadge,
} from "@/features/portal/admin/accounts/portal-it-admin-account-shared";
import { formatAdminDate, formatAdminLabel } from "@/features/portal/admin/portal-it-admin-shared";
import {
  useAccountsList,
} from "@/lib/api/generated/accounts/accounts";
import type {
  AccountSummaryResponse,
  AccountsListParams,
  DesignationCode,
  RoleCode,
} from "@/lib/api/generated/model";
import { DesignationCode as DesignationCodeValues, RoleCode as RoleCodeValues } from "@/lib/api/generated/model";

const PAGE_SIZE = 20;

const selectClassName =
  "h-9 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

type BooleanFilter = "" | "true" | "false";

function getBooleanFilter(value: BooleanFilter) {
  if (value === "true") {
    return true;
  }

  if (value === "false") {
    return false;
  }

  return undefined;
}

function AccountListSkeleton() {
  return (
    <div className="space-y-3" aria-live="polite" aria-label="Loading accounts">
      {Array.from({ length: 5 }, (_, index) => (
        <div
          key={index}
          className="h-20 animate-pulse rounded-2xl bg-muted"
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

function AccountRow({
  account,
}: {
  account: AccountSummaryResponse;
}) {
  return (
    <tr className="border-t border-[var(--compass-border)] align-top transition-colors hover:bg-[var(--compass-surface-subtle)]">
      <td className="px-4 py-4">
        <Link
          href={`/portal/admin/accounts/${account.id}`}
          className="flex min-w-64 items-start gap-3 rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <AccountInitials account={account} />
          <span className="min-w-0">
            <span className="block truncate font-semibold text-foreground">{account.full_name}</span>
            <span className="mt-1 block truncate text-sm text-muted-foreground">{account.email}</span>
          </span>
        </Link>
      </td>
      <td className="px-4 py-4">
        <AccountRoleBadge role={account.role} />
        {account.student_lifecycle_status ? (
          <p className="mt-2 text-xs text-muted-foreground">
            {formatAdminLabel(account.student_lifecycle_status)}
          </p>
        ) : null}
      </td>
      <td className="px-4 py-4">
        <AccountStatusBadge active={account.is_active} />
        <div className="mt-2">
          <VerificationBadge verified={account.email_verified} />
        </div>
      </td>
      <td className="px-4 py-4">
        <div className="flex max-w-56 flex-wrap gap-1.5">
          {account.designations.length ? (
            account.designations.map((designation) => (
              <DesignationBadge key={designation} designation={designation} />
            ))
          ) : (
            <span className="text-sm text-muted-foreground">None</span>
          )}
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-4 text-sm text-muted-foreground">
        {formatAdminDate(account.created_at)}
      </td>
    </tr>
  );
}

function AccountMobileCard({
  account,
}: {
  account: AccountSummaryResponse;
}) {
  return (
    <Link
      href={`/portal/admin/accounts/${account.id}`}
      className="block rounded-2xl border border-[var(--compass-border)] bg-card p-4 shadow-sm outline-none transition-colors hover:bg-[var(--compass-surface-subtle)] focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className="flex items-start gap-3">
        <AccountInitials account={account} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="break-words font-semibold">{account.full_name}</p>
            <AccountStatusBadge active={account.is_active} />
          </div>
          <p className="mt-1 break-words text-sm text-muted-foreground">{account.email}</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <AccountRoleBadge role={account.role} />
        <VerificationBadge verified={account.email_verified} />
        {account.designations.map((designation) => (
          <DesignationBadge key={designation} designation={designation} />
        ))}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-[var(--compass-border)] pt-4 text-sm">
        <div>
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
            Institutional ID
          </dt>
          <dd className="mt-1 break-words font-medium">{account.institutional_id || "Not provided"}</dd>
        </div>
        <div>
          <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
            Created
          </dt>
          <dd className="mt-1 text-muted-foreground">{formatAdminDate(account.created_at)}</dd>
        </div>
      </dl>
    </Link>
  );
}

export function PortalItAdminAccountsPage() {
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<RoleCode | "">("");
  const [active, setActive] = useState<BooleanFilter>("");
  const [designation, setDesignation] = useState<DesignationCode | "">("");
  const [emailVerified, setEmailVerified] = useState<BooleanFilter>("");
  const [page, setPage] = useState(1);
  const params = useMemo<AccountsListParams>(
    () => ({
      page,
      page_size: PAGE_SIZE,
      search: search || undefined,
      role: role || undefined,
      is_active: getBooleanFilter(active),
      designation: designation || undefined,
      email_verified: getBooleanFilter(emailVerified),
    }),
    [active, designation, emailVerified, page, role, search],
  );
  const accountsQuery = useAccountsList(params, {
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const accounts = accountsQuery.data?.data?.items ?? [];
  const response = accountsQuery.data?.data;

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(draftSearch.trim());
  }

  function clearFilters() {
    setDraftSearch("");
    setSearch("");
    setRole("");
    setActive("");
    setDesignation("");
    setEmailVerified("");
    setPage(1);
  }

  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
              <UsersRound aria-hidden="true" className="size-5" />
            </span>
            <div>
              <h2 className="font-heading text-2xl font-bold tracking-tight">Account directory</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                Search managed accounts by name, email, role, status, or designation.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 sm:justify-end">
            <Button asChild type="button" variant="outline">
              <Link href="/portal/admin/accounts/import">
                <Upload aria-hidden="true" />
                Import CSV
              </Link>
            </Button>
            <Button asChild type="button">
              <Link href="/portal/admin/accounts/new">
                <UserPlus aria-hidden="true" />
                Create account
              </Link>
            </Button>
          </div>
        </div>

        <form className="mt-6 space-y-4" onSubmit={submitFilters}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1">
              <Label htmlFor="account-search">Search accounts</Label>
              <div className="relative mt-2">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="account-search"
                  className="h-10 pl-9"
                  placeholder="Name, email, or institutional ID"
                  value={draftSearch}
                  onChange={(event) => setDraftSearch(event.target.value)}
                />
              </div>
            </div>
            <Button type="submit" className="h-10 sm:w-auto">
              <Search aria-hidden="true" />
              Search
            </Button>
          </div>

          <details className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold [&::-webkit-details-marker]:hidden">
              <SlidersHorizontal aria-hidden="true" className="size-4 text-[var(--compass-brand-maroon)]" />
              More filters
            </summary>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div>
                <Label htmlFor="account-role">Role</Label>
                <select
                  id="account-role"
                  className={`${selectClassName} mt-2`}
                  value={role}
                  onChange={(event) => {
                    setRole(event.target.value as RoleCode | "");
                    setPage(1);
                  }}
                >
                  <option value="">All roles</option>
                  {Object.values(RoleCodeValues).map((value) => (
                    <option key={value} value={value}>
                      {formatAdminLabel(value)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="account-status">Account status</Label>
                <select
                  id="account-status"
                  className={`${selectClassName} mt-2`}
                  value={active}
                  onChange={(event) => {
                    setActive(event.target.value as BooleanFilter);
                    setPage(1);
                  }}
                >
                  <option value="">All statuses</option>
                  <option value="true">Active</option>
                  <option value="false">Disabled</option>
                </select>
              </div>
              <div>
                <Label htmlFor="account-designation">Designation</Label>
                <select
                  id="account-designation"
                  className={`${selectClassName} mt-2`}
                  value={designation}
                  onChange={(event) => {
                    setDesignation(event.target.value as DesignationCode | "");
                    setPage(1);
                  }}
                >
                  <option value="">All designations</option>
                  {Object.values(DesignationCodeValues).map((value) => (
                    <option key={value} value={value}>
                      {formatAdminLabel(value)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="account-email-status">Email status</Label>
                <select
                  id="account-email-status"
                  className={`${selectClassName} mt-2`}
                  value={emailVerified}
                  onChange={(event) => {
                    setEmailVerified(event.target.value as BooleanFilter);
                    setPage(1);
                  }}
                >
                  <option value="">All email statuses</option>
                  <option value="true">Verified</option>
                  <option value="false">Not verified</option>
                </select>
              </div>
            </div>
            <Button type="button" variant="ghost" className="mt-4" onClick={clearFilters}>
              Clear filters
            </Button>
          </details>
        </form>
      </section>

      {accountsQuery.isPending ? <AccountListSkeleton /> : null}

      {accountsQuery.isError ? (
        <EmptyAccountState
          title="Accounts are unavailable"
          description={getApiErrorMessage(accountsQuery.error) ?? "We couldn’t load the account directory right now."}
          action={
            <Button type="button" variant="outline" onClick={() => void accountsQuery.refetch()}>
              Try again
            </Button>
          }
        />
      ) : null}

      {!accountsQuery.isPending && !accountsQuery.isError && accounts.length === 0 ? (
        <EmptyAccountState
          title="No accounts found"
          description="Try a different search or clear one of the filters."
          action={
            <Button type="button" variant="outline" onClick={clearFilters}>
              Clear filters
            </Button>
          }
        />
      ) : null}

      {!accountsQuery.isPending && !accountsQuery.isError && accounts.length > 0 ? (
        <>
          <div className="hidden overflow-hidden rounded-3xl border border-[var(--compass-border)] bg-card shadow-sm lg:block">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[62rem] text-left text-sm">
                <caption className="sr-only">Managed accounts</caption>
                <thead className="bg-[var(--compass-surface-subtle)] text-xs uppercase tracking-[0.12em] text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-bold">Account</th>
                    <th className="px-4 py-3 font-bold">Role</th>
                    <th className="px-4 py-3 font-bold">Status</th>
                    <th className="px-4 py-3 font-bold">Designations</th>
                    <th className="px-4 py-3 font-bold">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <AccountRow key={account.id} account={account} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="space-y-3 lg:hidden">
            {accounts.map((account) => (
              <AccountMobileCard key={account.id} account={account} />
            ))}
          </div>

          <div className="flex flex-col gap-3 rounded-2xl border border-[var(--compass-border)] bg-card p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <p className="text-muted-foreground">
              Showing page {response?.page ?? page} · {accounts.length} {accounts.length === 1 ? "account" : "accounts"}
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={page <= 1 || accountsQuery.isFetching}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                <ChevronLeft aria-hidden="true" />
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!response?.has_next || accountsQuery.isFetching}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
                <ChevronRight aria-hidden="true" />
              </Button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

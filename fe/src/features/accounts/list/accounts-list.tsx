"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  accountName,
  designationLabels,
  designations,
  isDesignationCode,
  isRoleCode,
  roleLabels,
  roles,
} from "@/features/accounts/presentation";
import { managedAccountError } from "@/features/accounts/components/account-action";
import { useAccountsList } from "@/lib/api/generated/accounts/accounts";
import type { AccountsListParams } from "@/lib/api/generated/model";

const pageSize = 20;
const selectClass =
  "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

function parsePage(value: string | null): number {
  const page = Number(value);
  return value && Number.isSafeInteger(page) && page > 0 ? page : 1;
}

function SearchField({
  initial,
  onSearch,
}: {
  initial: string;
  onSearch: (value: string) => void;
}) {
  const [value, setValue] = useState(initial);
  useEffect(() => {
    if (value.trim() === initial) return;
    const timer = window.setTimeout(() => onSearch(value.trim()), 350);
    return () => window.clearTimeout(timer);
  }, [initial, onSearch, value]);

  return (
    <div className="min-w-0 flex-1">
      <Label htmlFor="accounts-search">Search accounts</Label>
      <div className="relative mt-2">
        <Search
          className="pointer-events-none absolute left-3 top-3 text-muted"
          size={18}
          aria-hidden="true"
        />
        <Input
          id="accounts-search"
          className="pl-10"
          value={value}
          maxLength={254}
          placeholder="Search by name, Institutional ID, or email"
          onChange={(event) => setValue(event.target.value)}
        />
      </div>
    </div>
  );
}

export function AccountsList() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const page = parsePage(searchParams.get("page"));
  const role = searchParams.get("role") ?? "";
  const designation = searchParams.get("designation") ?? "";
  const status = searchParams.get("is_active") ?? "";
  const verified = searchParams.get("email_verified") ?? "";
  const search = (searchParams.get("search") ?? "").slice(0, 254).trim();
  const filters: AccountsListParams = {
    page,
    page_size: pageSize,
    ...(isRoleCode(role) ? { role } : {}),
    ...(isDesignationCode(designation) ? { designation } : {}),
    ...(status === "true" || status === "false"
      ? { is_active: status === "true" }
      : {}),
    ...(verified === "true" || verified === "false"
      ? { email_verified: verified === "true" }
      : {}),
    ...(search ? { search } : {}),
  };
  const list = useAccountsList(filters, { query: { retry: false } });
  const filtered = Boolean(
    filters.role ||
      filters.designation ||
      filters.is_active !== undefined ||
      filters.email_verified !== undefined ||
      search,
  );

  function hrefWith(key: string, value: string, resetPage = true): string {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    if (resetPage) next.delete("page");
    const query = next.toString();
    return query ? `${pathname}?${query}` : pathname;
  }

  function update(key: string, value: string) {
    router.replace(hrefWith(key, value), { scroll: false });
  }

  const paramsText = searchParams.toString();
  const detailSuffix = paramsText
    ? `?return=${encodeURIComponent(paramsText)}`
    : "";

  return (
    <section aria-labelledby="accounts-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1
            id="accounts-heading"
            className="font-heading text-3xl font-bold text-ink sm:text-4xl"
          >
            Accounts
          </h1>
          <p className="mt-2 text-sm text-muted">
            Manage COMPASS accounts and access.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/portal/accounts/import"
            className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Import CSV
          </Link>
          <Link
            href="/portal/accounts/new"
            className="inline-flex min-h-10 items-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Create account
          </Link>
        </div>
      </div>

      <div className="mt-8 border-y border-border py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <SearchField
            key={search}
            initial={search}
            onSearch={(value) => update("search", value)}
          />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:w-[35rem]">
            <div>
              <Label htmlFor="accounts-role">Role</Label>
              <select
                id="accounts-role"
                className={`${selectClass} mt-2`}
                value={filters.role ?? ""}
                onChange={(event) => update("role", event.target.value)}
              >
                <option value="">All</option>
                {roles.map((value) => (
                  <option key={value} value={value}>
                    {roleLabels[value]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="accounts-status">Status</Label>
              <select
                id="accounts-status"
                className={`${selectClass} mt-2`}
                value={
                  filters.is_active === undefined
                    ? ""
                    : String(filters.is_active)
                }
                onChange={(event) => update("is_active", event.target.value)}
              >
                <option value="">All</option>
                <option value="true">Active</option>
                <option value="false">Disabled</option>
              </select>
            </div>
            <div>
              <Label htmlFor="accounts-designation">Designation</Label>
              <select
                id="accounts-designation"
                className={`${selectClass} mt-2`}
                value={filters.designation ?? ""}
                onChange={(event) => update("designation", event.target.value)}
              >
                <option value="">All</option>
                {designations.map((value) => (
                  <option key={value} value={value}>
                    {designationLabels[value]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="accounts-email">Email</Label>
              <select
                id="accounts-email"
                className={`${selectClass} mt-2`}
                value={
                  filters.email_verified === undefined
                    ? ""
                    : String(filters.email_verified)
                }
                onChange={(event) =>
                  update("email_verified", event.target.value)
                }
              >
                <option value="">All</option>
                <option value="true">Verified</option>
                <option value="false">Not verified</option>
              </select>
            </div>
          </div>
        </div>
        {filtered ? (
          <button
            type="button"
            className="mt-4 text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            onClick={() => router.replace(pathname, { scroll: false })}
          >
            Clear filters
          </button>
        ) : null}
      </div>

      {list.isPending ? (
        <div className="mt-6 space-y-3" aria-busy="true">
          <span className="sr-only">Loading accounts…</span>
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-14 w-full" />
          ))}
        </div>
      ) : list.isError ? (
        <div role="alert" className="mt-6 border-y border-border py-6">
          <p className="text-sm text-danger">
            {managedAccountError(list.error, "Accounts could not be loaded.")}
          </p>
          <Button
            variant="secondary"
            className="mt-4"
            onClick={() => void list.refetch()}
          >
            Retry
          </Button>
        </div>
      ) : (
        <>
          {list.isFetching ? (
            <p role="status" className="mt-4 text-xs text-muted">
              Refreshing accounts…
            </p>
          ) : null}
          {list.data.data.items.length === 0 ? (
            <div className="border-b border-border py-10 text-sm text-muted">
              <p>
                {page > 1
                  ? "No accounts are available on this page."
                  : filtered
                    ? "No accounts match the current search or filters."
                    : "No managed accounts are available."}
              </p>
              {filtered ? (
                <button
                  type="button"
                  className="mt-3 inline-flex min-h-10 items-center font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  onClick={() => router.replace(pathname, { scroll: false })}
                >
                  Clear filters
                </button>
              ) : null}
            </div>
          ) : (
            <div className="mt-5 overflow-x-auto border-y border-border">
              <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
                <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
                  <tr>
                    <th scope="col" className="px-4 py-3">
                      Account
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Role
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Designation
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Status
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Email
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.data.items.map((account) => (
                    <tr
                      key={account.id}
                      className="border-t border-border align-top"
                    >
                      <th
                        scope="row"
                        className="px-4 py-4 text-left font-normal"
                      >
                        <Link
                          href={`/portal/accounts/${encodeURIComponent(account.id)}${detailSuffix}`}
                          className="font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                        >
                          {accountName(account)}
                        </Link>
                        <span className="mt-1 block text-xs text-muted">
                          {account.institutional_id || "No Institutional ID"} ·{" "}
                          {account.email}
                        </span>
                      </th>
                      <td className="px-4 py-4">{roleLabels[account.role]}</td>
                      <td className="px-4 py-4">
                        {account.designations.length
                          ? account.designations
                              .map((code) => designationLabels[code])
                              .join(", ")
                          : "—"}
                      </td>
                      <td className="px-4 py-4">
                        {account.is_active ? "Active" : "Disabled"}
                      </td>
                      <td className="px-4 py-4">
                        {account.email_verified ? "Verified" : "Not verified"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {page > 1 || list.data.data.has_next ? (
            <nav
              aria-label="Accounts pagination"
              className="mt-5 flex items-center justify-between gap-4"
            >
              <Button
                variant="secondary"
                disabled={page <= 1}
                onClick={() =>
                  router.push(hrefWith("page", String(page - 1), false))
                }
              >
                Previous
              </Button>
              <span className="text-sm text-muted">
                Page {list.data.data.page}
              </span>
              <Button
                variant="secondary"
                disabled={!list.data.data.has_next}
                onClick={() =>
                  router.push(hrefWith("page", String(page + 1), false))
                }
              >
                Next
              </Button>
            </nav>
          ) : null}
        </>
      )}
    </section>
  );
}

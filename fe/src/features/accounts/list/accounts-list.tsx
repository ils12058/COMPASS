"use client";

import { Upload, UserPlus } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { PageActionGroup, PageActionLink } from "@/components/ui/page-action";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
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
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { useAccountsList } from "@/lib/api/generated/accounts/accounts";
import type { AccountsListParams } from "@/lib/api/generated/model";

const pageSize = 20;

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
    <ListSearchField
      id="accounts-search"
      name="search"
      label="Search accounts"
      value={value}
      maxLength={254}
      placeholder="Search by name, Institutional ID, or email"
      onChange={(event) => setValue(event.target.value)}
    />
  );
}

export function AccountsListSkeleton() {
  return (
    <RowsSkeleton label="Loading accounts…" rows={6} framed />
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
  const confirmed = safeQueryData(list);
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
      <PageHeader
        title="Accounts"
        headingId="accounts-heading"
        actions={
          <PageActionGroup>
            <PageActionLink href="/portal/accounts/import" icon={Upload} label="Import" labelDetail="CSV" variant="secondary" />
            <PageActionLink href="/portal/accounts/new" icon={UserPlus} label="Create" labelDetail="account" />
          </PageActionGroup>
        }
      />

      {/* A directory search: the text search applies as you type (or on Enter), and each choice
          applies on change. */}
      <form
        role="search"
        aria-label="Accounts"
        onSubmit={(event) => {
          event.preventDefault();
          const value = new FormData(event.currentTarget).get("search");
          update("search", typeof value === "string" ? value.trim().slice(0, 254) : "");
        }}
      >
        <FloatingListTools
          filterCount={
            [filters.role, filters.designation, filters.is_active !== undefined, filters.email_verified !== undefined].filter(Boolean).length
          }
          clear={
            filtered ? (
              <Button variant="quiet" onClick={() => router.replace(pathname, { scroll: false })}>
                Clear filters
              </Button>
            ) : undefined
          }
          filters={
            <>
              <FilterField label="Role" htmlFor="accounts-role">
                <Select
                  id="accounts-role"
                  value={filters.role ?? ""}
                  onChange={(event) => update("role", event.target.value)}
                >
                  <option value="">All</option>
                  {roles.map((value) => (
                    <option key={value} value={value}>
                      {roleLabels[value]}
                    </option>
                  ))}
                </Select>
              </FilterField>
              <FilterField label="Status" htmlFor="accounts-status">
                <Select
                  id="accounts-status"
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
                </Select>
              </FilterField>
              <FilterField label="Designation" htmlFor="accounts-designation">
                <Select
                  id="accounts-designation"
                  value={filters.designation ?? ""}
                  onChange={(event) => update("designation", event.target.value)}
                >
                  <option value="">All</option>
                  {designations.map((value) => (
                    <option key={value} value={value}>
                      {designationLabels[value]}
                    </option>
                  ))}
                </Select>
              </FilterField>
              <FilterField label="Email" htmlFor="accounts-email">
                <Select
                  id="accounts-email"
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
                </Select>
              </FilterField>
            </>
          }
        >
          <SearchField
            key={search}
            initial={search}
            onSearch={(value) => update("search", value)}
          />
        </FloatingListTools>
      </form>

      {list.isError && confirmed ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}
      <Panel aria-labelledby="accounts-results-heading">
        <PanelHeader
          title="Managed accounts"
          titleId="accounts-results-heading"
          context={
            list.isFetching && !list.isPending
              ? "Refreshing accounts…"
              : confirmed && !list.isError
                ? describeResultPage({
                    count: confirmed.data.items.length,
                    page: confirmed.data.page,
                    hasNext: confirmed.data.has_next,
                    noun: { one: "account", other: "accounts" },
                    filtered,
                  })
                : null
          }
        />
        {list.isPending ? (
          <RowsSkeleton label="Loading accounts…" rows={6} />
        ) : !confirmed ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={
              <Button variant="secondary" onClick={() => void list.refetch()}>
                Retry
              </Button>
            }
          >
            {managedAccountError(list.error, "Accounts could not be loaded.")}
          </PanelMessage>
        ) : (
          <>
            {confirmed.data.items.length === 0 ? (
              <PanelMessage
                action={
                  filtered ? (
                    <Button variant="secondary" onClick={() => router.replace(pathname, { scroll: false })}>
                      Clear filters
                    </Button>
                  ) : undefined
                }
              >
                {page > 1
                  ? "No accounts are available on this page."
                  : filtered
                    ? "No accounts match the current search or filters."
                    : "No managed accounts are available."}
              </PanelMessage>
            ) : (
              <div className={dataTable.scroll}>
                <table className={`${dataTable.table} min-w-[44rem]`}>
                  <caption className="sr-only">Managed accounts</caption>
                  <thead className={dataTable.head}>
                    <tr>
                      <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>
                        Account
                      </th>
                      <th scope="col" className={dataTable.headerCell}>
                        Role
                      </th>
                      <th scope="col" className={dataTable.headerCell}>
                        Designation
                      </th>
                      <th scope="col" className={dataTable.headerCell}>
                        Status
                      </th>
                      <th scope="col" className={dataTable.headerCell}>
                        Email
                      </th>
                    </tr>
                  </thead>
                  <tbody className={dataTable.body}>
                {confirmed.data.items.map((account) => (
                  <tr key={account.id} className={dataTable.row}>
                    <th
                      scope="row"
                      className={`${dataTable.cell} ${dataTable.stickyCell} text-left font-normal`}
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
                    <td className={dataTable.cell}>{roleLabels[account.role]}</td>
                    <td className={dataTable.cell}>
                      {account.designations.length
                        ? account.designations
                            .map((code) => designationLabels[code])
                            .join(", ")
                        : "—"}
                    </td>
                    <td className={dataTable.cell}>
                      {account.is_active ? "Active" : "Disabled"}
                    </td>
                    <td className={dataTable.cell}>
                      {account.email_verified ? "Verified" : "Not verified"}
                    </td>
                  </tr>
                ))}
                  </tbody>
                </table>
              </div>
            )}
            <CanonicalPagination
              className="border-brand-line px-4 py-3 sm:px-5"
              page={confirmed.data.page}
              hasNext={confirmed.data.has_next}
              label="Accounts pagination"
              onPageChange={(nextPage) =>
                router.push(hrefWith("page", String(nextPage), false))
              }
            />
          </>
        )}
      </Panel>
    </section>
  );
}

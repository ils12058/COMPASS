"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { createContext, useContext, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { managedAccountError } from "@/features/accounts/components/account-action";
import { accountName, roleLabels } from "@/features/accounts/presentation";
import { useAccountsGet } from "@/lib/api/generated/accounts/accounts";
import type { AccountDetailResponse } from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/errors";

const AccountContext = createContext<AccountDetailResponse | null>(null);

export function useManagedAccount(): AccountDetailResponse {
  const value = useContext(AccountContext);
  if (!value)
    throw new Error("Managed account detail is unavailable outside its route.");
  return value;
}

export function AccountDetailFrame({
  userId,
  children,
}: {
  userId: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const account = useAccountsGet(userId, { query: { retry: false } });
  const returnQuery = searchParams.get("return") ?? "";
  const listHref = returnQuery
    ? `/portal/accounts?${returnQuery}`
    : "/portal/accounts";
  const baseHref = `/portal/accounts/${encodeURIComponent(userId)}`;
  const suffix = returnQuery
    ? `?return=${encodeURIComponent(returnQuery)}`
    : "";

  if (account.isPending)
    return (
      <div aria-busy="true">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="mt-6 h-9 w-64" />
        <Skeleton className="mt-5 h-20 w-full" />
        <Skeleton className="mt-8 h-36 w-full" />
        <span className="sr-only">Loading account…</span>
      </div>
    );
  if (account.isError) {
    const missing =
      account.error instanceof CompassApiError && account.error.status === 404;
    return (
      <section role="alert" className="max-w-xl border-y border-border py-8">
        <h1 className="font-heading text-3xl font-bold text-ink">
          {missing ? "Account not found" : "Account unavailable"}
        </h1>
        <p className="mt-3 text-sm text-muted">
          {missing
            ? "This managed account could not be found."
            : managedAccountError(
                account.error,
                "The managed account could not be loaded.",
              )}
        </p>
        <div className="mt-5 flex gap-3">
          <Link
            href={listHref}
            className="inline-flex min-h-10 items-center text-sm font-semibold text-brand underline"
          >
            Back to Accounts
          </Link>
          {!missing ? (
            <Button variant="secondary" onClick={() => void account.refetch()}>
              Retry
            </Button>
          ) : null}
        </div>
      </section>
    );
  }

  const data = account.data.data;
  const tabs = [
    ["Overview", baseHref],
    ["Access", `${baseHref}/access`],
    ["Security", `${baseHref}/security`],
  ] as const;
  return (
    <AccountContext.Provider value={data}>
      <section aria-labelledby="account-detail-heading">
        <Link
          href={listHref}
          className="text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          ← Accounts
        </Link>
        <div className="mt-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1
              id="account-detail-heading"
              className="font-heading text-3xl font-bold text-ink"
            >
              {accountName(data)}
            </h1>
            <p className="mt-2 text-sm text-muted">
              {data.institutional_id || "No Institutional ID"} ·{" "}
              {roleLabels[data.role]} · {data.email}
            </p>
          </div>
          <span
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${data.is_active ? "border-support text-support-strong" : "border-danger text-danger"}`}
          >
            {data.is_active ? "Active" : "Disabled"}
          </span>
        </div>
        <nav
          aria-label="Account sections"
          className="mt-7 flex gap-5 overflow-x-auto border-b border-border"
        >
          {tabs.map(([label, href]) => (
            <Link
              key={label}
              href={`${href}${suffix}`}
              aria-current={pathname === href ? "page" : undefined}
              className={`whitespace-nowrap border-b-2 px-1 py-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${pathname === href ? "border-brand text-brand" : "border-transparent text-muted hover:text-ink"}`}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="pt-7">{children}</div>
      </section>
    </AccountContext.Provider>
  );
}

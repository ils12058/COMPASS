"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { createContext, useContext, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Notice } from "@/components/ui/notice";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
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
  const confirmed = safeQueryData(account);
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
      <LoadingRegion label="Loading account…">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="mt-3 h-9 w-64" />
        <Skeleton className="mt-3 h-4 w-80 max-w-full" />
        <Skeleton className="mt-6 h-11 w-72 max-w-full" />
        <div className="mt-6 rounded-sm border border-brand-line bg-surface-raised px-4 py-5 sm:px-5">
          <Skeleton className="h-28 w-full" />
        </div>
      </LoadingRegion>
    );
  if (!confirmed) {
    const missing =
      account.error instanceof CompassApiError && account.error.status === 404;
    return (
      <section className="max-w-2xl">
        <PageHeader
          title={missing ? "Account not found" : "Account unavailable"}
        />
        <Notice
          role="alert"
          tone={missing ? "neutral" : "danger"}
          action={
            <>
              <Link
                href={listHref}
                className="inline-flex min-h-10 items-center text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Back to Accounts
              </Link>
              {!missing ? (
                <Button variant="secondary" onClick={() => void account.refetch()}>
                  Retry
                </Button>
              ) : null}
            </>
          }
        >
          {missing
            ? "This managed account could not be found."
            : managedAccountError(
                account.error,
                "The managed account could not be loaded.",
              )}
        </Notice>
      </section>
    );
  }

  const data = confirmed.data;
  const tabs = [
    ["Overview", baseHref],
    ["Access", `${baseHref}/access`],
    ["Security", `${baseHref}/security`],
  ] as const;
  return (
    <AccountContext.Provider value={data}>
      <section aria-labelledby="account-detail-heading">
        {account.isError ? <RefreshFailureNotice onRetry={() => void account.refetch()} retrying={account.isFetching} /> : null}
        <PageHeader
          title={accountName(data)}
          headingId="account-detail-heading"
          back={
            <Link href={listHref} className={pageBackLinkClass}>
              Back to Accounts
            </Link>
          }
          meta={
            <span
              className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${data.is_active ? "border-support text-support-strong" : "border-danger text-danger"}`}
            >
              {data.is_active ? "Active" : "Disabled"}
            </span>
          }
          description={
            <>
              {data.institutional_id || "No Institutional ID"} ·{" "}
              {roleLabels[data.role]} · {data.email}
            </>
          }
          className="mb-5"
        />
        <WorkspaceTabs label="Account sections">
          {tabs.map(([label, href]) => (
            <Link
              key={label}
              href={`${href}${suffix}`}
              aria-current={pathname === href ? "page" : undefined}
              className={workspaceTabClass(pathname === href)}
            >
              {label}
            </Link>
          ))}
        </WorkspaceTabs>
        {children}
      </section>
    </AccountContext.Provider>
  );
}

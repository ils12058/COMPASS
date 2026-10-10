"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getApiErrorMessage } from "@/features/auth/utils/errors";
import {
  AccountDetailHeader,
  RetryAccountQuery,
} from "@/features/portal/admin/accounts/portal-it-admin-account-shared";
import { PortalItAdminAccountAccess } from "@/features/portal/admin/accounts/portal-it-admin-account-access";
import { PortalItAdminAccountActions } from "@/features/portal/admin/accounts/portal-it-admin-account-actions";
import { PortalItAdminAccountIdentity } from "@/features/portal/admin/accounts/portal-it-admin-account-identity";
import { PortalItAdminAccountRole } from "@/features/portal/admin/accounts/portal-it-admin-account-role";
import { useAccountsGet } from "@/lib/api/generated/accounts/accounts";

function AccountDetailLoading() {
  return (
    <div className="space-y-5" aria-live="polite">
      <div className="h-8 w-40 animate-pulse rounded-xl bg-muted" />
      <div className="h-36 animate-pulse rounded-3xl bg-card" />
      <div className="h-72 animate-pulse rounded-3xl bg-card" />
      <div className="h-64 animate-pulse rounded-3xl bg-card" />
    </div>
  );
}

export function PortalItAdminAccountDetailPage({ userId }: { userId: string }) {
  const accountQuery = useAccountsGet(userId, {
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const account = accountQuery.data?.data;

  if (accountQuery.isPending) {
    return <AccountDetailLoading />;
  }

  if (accountQuery.isError || !account) {
    return (
      <div className="space-y-5">
        <Button asChild type="button" variant="ghost" className="-ml-2">
          <Link href="/portal/admin/accounts">
            <ArrowLeft aria-hidden="true" />
            Back to accounts
          </Link>
        </Button>
        <RetryAccountQuery
          message={
            getApiErrorMessage(accountQuery.error) ??
            "We couldn’t load this account right now."
          }
          onRetry={() => void accountQuery.refetch()}
        />
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
      <AccountDetailHeader account={account} />
      <PortalItAdminAccountIdentity key={`${account.id}-${account.updated_at}`} account={account} />
      <PortalItAdminAccountRole key={`${account.id}-${account.updated_at}-role`} account={account} />
      <PortalItAdminAccountAccess account={account} />
      <PortalItAdminAccountActions account={account} />
    </div>
  );
}

import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  formatAdminDate,
  formatAdminLabel,
} from "@/features/portal/admin/portal-it-admin-shared";
import { getApiErrorMessage } from "@/features/auth/utils/errors";
import type {
  AccountDetailResponse,
  AccountSummaryResponse,
  DesignationCode,
  RoleCode,
  StudentLifecycleCode,
} from "@/lib/api/generated/model";

export function accountAdminError(
  error: unknown,
  fallback = "We couldn’t complete that account action. Please try again.",
) {
  return getApiErrorMessage(error) ?? fallback;
}

export function AccountStatusBadge({
  active,
  children,
}: {
  active: boolean;
  children?: ReactNode;
}) {
  return (
    <Badge
      variant="outline"
      className={
        active
          ? "border-[var(--compass-support)]/30 bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]"
          : "border-[var(--compass-brand-maroon)]/20 bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]"
      }
    >
      {children ?? (active ? "Active" : "Disabled")}
    </Badge>
  );
}

export function VerificationBadge({ verified }: { verified: boolean }) {
  return (
    <Badge
      variant="outline"
      className={
        verified
          ? "border-[var(--compass-support)]/30 text-[var(--compass-support-strong)]"
          : "border-[var(--compass-border-strong)] text-muted-foreground"
      }
    >
      {verified ? "Verified" : "Not verified"}
    </Badge>
  );
}

export function AccountRoleBadge({ role }: { role: RoleCode }) {
  return (
    <Badge variant="secondary" className="font-semibold">
      {formatAdminLabel(role)}
    </Badge>
  );
}

export function DesignationBadge({ designation }: { designation: DesignationCode }) {
  return (
    <Badge variant="outline" className="border-[var(--compass-brand-gold)]/40 text-[var(--compass-brand-maroon)]">
      {formatAdminLabel(designation)}
    </Badge>
  );
}

export function AccountInitials({
  account,
  className = "",
}: {
  account: Pick<AccountSummaryResponse, "first_name" | "last_name" | "email">;
  className?: string;
}) {
  const initials = [account.first_name, account.last_name]
    .map((part) => part.trim().charAt(0))
    .filter(Boolean)
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <span
      aria-hidden="true"
      className={`inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-[var(--compass-brand-maroon)] text-sm font-bold text-white ${className}`}
    >
      {initials || account.email.slice(0, 2).toUpperCase()}
    </span>
  );
}

export function AccountField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
      <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-2 break-words text-sm font-semibold text-foreground">
        {value || "Not provided"}
      </dd>
    </div>
  );
}

export function AccountSection({
  children,
  description,
  icon: Icon,
  title,
}: {
  children: ReactNode;
  description: string;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
      <header className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
          <Icon aria-hidden="true" className="size-5" />
        </span>
        <div className="min-w-0">
          <h2 className="font-heading text-2xl font-bold tracking-tight">{title}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
      </header>
      <div className="mt-6">{children}</div>
    </section>
  );
}

export function AccountActionMessage({
  error,
  message,
}: {
  error?: string | null;
  message?: string | null;
}) {
  if (!error && !message) {
    return null;
  }

  return (
    <Alert
      className={
        error
          ? "border-destructive/30 text-destructive"
          : "border-[var(--compass-support)]/30 text-[var(--compass-support-strong)]"
      }
      role={error ? "alert" : "status"}
    >
      <AlertDescription>{error ?? message}</AlertDescription>
    </Alert>
  );
}

export function AccountDetailHeader({ account }: { account: AccountDetailResponse }) {
  return (
    <div className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <AccountInitials account={account} className="size-14 text-lg" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="break-words font-heading text-2xl font-bold tracking-tight">
                {account.full_name}
              </h2>
              <AccountStatusBadge active={account.is_active} />
            </div>
            <p className="mt-1 break-words text-sm text-muted-foreground">{account.email}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <AccountRoleBadge role={account.role} />
              {account.designations.map((designation) => (
                <DesignationBadge key={designation} designation={designation} />
              ))}
            </div>
          </div>
        </div>
        <div className="text-left text-xs leading-5 text-muted-foreground sm:text-right">
          <p>Created {formatAdminDate(account.created_at)}</p>
          <p>Updated {formatAdminDate(account.updated_at)}</p>
        </div>
      </div>
    </div>
  );
}

export function LifecycleBadge({
  status,
}: {
  status: StudentLifecycleCode | null;
}) {
  return status ? (
    <Badge variant="outline">{formatAdminLabel(status)}</Badge>
  ) : (
    <span className="text-sm text-muted-foreground">Not applicable</span>
  );
}

export function EmptyAccountState({
  description,
  title,
  action,
}: {
  action?: ReactNode;
  description: string;
  title: string;
}) {
  return (
    <div className="rounded-3xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-8 text-center">
      <h2 className="font-heading text-xl font-bold">{title}</h2>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
        {description}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function RetryAccountQuery({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-3xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-8 text-center">
      <p className="text-sm leading-6 text-muted-foreground" role="alert">
        {message}
      </p>
      <Button className="mt-4" type="button" variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

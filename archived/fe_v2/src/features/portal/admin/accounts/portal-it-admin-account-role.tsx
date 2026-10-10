"use client";

import { FormEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, GraduationCap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  getAccountsGetEffectiveAccessQueryKey,
  getAccountsGetQueryKey,
  getAccountsListQueryKey,
  useAccountsChangeRole,
  useAccountsUpdateStudentLifecycle,
} from "@/lib/api/generated/accounts/accounts";
import {
  RoleCode,
  StudentLifecycleCode,
} from "@/lib/api/generated/model";
import type { AccountDetailResponse, RoleCode as RoleCodeType, StudentLifecycleCode as StudentLifecycleCodeType } from "@/lib/api/generated/model";
import {
  AccountActionMessage,
  AccountSection,
  LifecycleBadge,
  accountAdminError,
} from "@/features/portal/admin/accounts/portal-it-admin-account-shared";
import { formatAdminLabel } from "@/features/portal/admin/portal-it-admin-shared";

const selectClassName =
  "h-10 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function PortalItAdminAccountRole({
  account,
}: {
  account: AccountDetailResponse;
}) {
  const queryClient = useQueryClient();
  const [role, setRole] = useState<RoleCodeType>(account.role);
  const [lifecycle, setLifecycle] = useState<StudentLifecycleCodeType>(account.student_lifecycle_status ?? StudentLifecycleCode.CURRENT);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const changeRole = useAccountsChangeRole();
  const updateLifecycle = useAccountsUpdateStudentLifecycle();

  async function refreshAccount() {
    await queryClient.invalidateQueries({ queryKey: getAccountsGetQueryKey(account.id) });
    await queryClient.invalidateQueries({ queryKey: getAccountsGetEffectiveAccessQueryKey(account.id) });
    await queryClient.invalidateQueries({ queryKey: getAccountsListQueryKey() });
  }

  async function saveRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      await changeRole.mutateAsync({ userId: account.id, data: { role } });
      await refreshAccount();
      setMessage("The account role is up to date.");
    } catch (caught) {
      setError(accountAdminError(caught, "We couldn’t update the account role. Please try again."));
    }
  }

  async function saveLifecycle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      await updateLifecycle.mutateAsync({
        userId: account.id,
        data: { status: lifecycle },
      });
      await refreshAccount();
      setMessage("The student lifecycle status is up to date.");
    } catch (caught) {
      setError(accountAdminError(caught, "We couldn’t update the student lifecycle. Please try again."));
    }
  }

  const isStudent = account.role === RoleCode.STUDENT;

  return (
    <AccountSection
      icon={BadgeCheck}
      title="Role and lifecycle"
      description="Keep the account’s role and, where applicable, student lifecycle status aligned with its current responsibilities."
    >
      <div className="grid gap-5 xl:grid-cols-2">
        <form className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4" onSubmit={saveRole}>
          <Label htmlFor="admin-account-role">Role</Label>
          <select
            id="admin-account-role"
            className={`${selectClassName} mt-2`}
            value={role}
            onChange={(event) => setRole(event.target.value as RoleCodeType)}
          >
            {Object.values(RoleCode).map((value) => (
              <option key={value} value={value}>
                {formatAdminLabel(value)}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Role changes affect the access granted by the account’s baseline role.
          </p>
          <Button className="mt-4" type="submit" variant="outline" disabled={changeRole.isPending || role === account.role}>
            {changeRole.isPending ? "Saving…" : "Save role"}
          </Button>
        </form>

        <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
          <div className="flex items-start gap-3">
            <GraduationCap aria-hidden="true" className="mt-0.5 size-5 text-[var(--compass-brand-maroon)]" />
            <div>
              <p className="font-semibold">Student lifecycle</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                This status is available for student accounts.
              </p>
            </div>
            <div className="ml-auto">
              <LifecycleBadge status={account.student_lifecycle_status} />
            </div>
          </div>
          {isStudent ? (
            <form className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={saveLifecycle}>
              <div className="min-w-0 flex-1">
                <Label htmlFor="admin-account-lifecycle">Lifecycle status</Label>
                <select
                  id="admin-account-lifecycle"
                  className={`${selectClassName} mt-2`}
                  value={lifecycle}
                  onChange={(event) => setLifecycle(event.target.value as StudentLifecycleCodeType)}
                >
                  {Object.values(StudentLifecycleCode).map((value) => (
                    <option key={value} value={value}>
                      {formatAdminLabel(value)}
                    </option>
                  ))}
                </select>
              </div>
              <Button type="submit" variant="outline" disabled={updateLifecycle.isPending || lifecycle === account.student_lifecycle_status}>
                {updateLifecycle.isPending ? "Saving…" : "Save status"}
              </Button>
            </form>
          ) : (
            <p className="mt-4 rounded-xl border border-dashed border-[var(--compass-border-strong)] p-3 text-sm text-muted-foreground">
              Lifecycle status does not apply to this role.
            </p>
          )}
        </div>
      </div>
      <div className="mt-5">
        <AccountActionMessage error={error} message={message} />
      </div>
    </AccountSection>
  );
}

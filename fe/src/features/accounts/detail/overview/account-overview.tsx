"use client";

import { useState, type FormEvent } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  isTurnstileConfigured,
  TurnstileWidget,
} from "@/features/auth/components/turnstile-widget";
import {
  ManagedActionFeedback,
  useInvalidateManagedAccount,
  useManagedAction,
} from "@/features/accounts/components/account-action";
import { useManagedAccount } from "@/features/accounts/detail/account-detail-frame";
import {
  accountName,
  formatAccountDate,
  lifecycleLabels,
  lifecycles,
} from "@/features/accounts/presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useAccountsDisable,
  useAccountsEnable,
  useAccountsRequestEmailChange,
  useAccountsUpdateIdentity,
  useAccountsUpdateStudentLifecycle,
} from "@/lib/api/generated/accounts/accounts";
import {
  RoleCode,
  StudentLifecycleCode,
  type IdentityUpdateRequest,
} from "@/lib/api/generated/model";

type Confirmation = "disable" | "enable" | "lifecycle" | null;

export function AccountOverview() {
  const account = useManagedAccount();
  const { user } = usePortalSession();
  const self = user.id === account.id;
  const invalidate = useInvalidateManagedAccount(account.id);
  const action = useManagedAction();
  const updateIdentity = useAccountsUpdateIdentity();
  const changeEmail = useAccountsRequestEmailChange();
  const disable = useAccountsDisable();
  const enable = useAccountsEnable();
  const updateLifecycle = useAccountsUpdateStudentLifecycle();
  const [identityOpen, setIdentityOpen] = useState(false);
  const [identity, setIdentity] = useState<IdentityUpdateRequest>({});
  const [emailOpen, setEmailOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [stagedEmail, setStagedEmail] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [turnstileReset, setTurnstileReset] = useState(0);
  const [confirm, setConfirm] = useState<Confirmation>(null);
  const [lifecycle, setLifecycle] = useState<StudentLifecycleCode | null>(
    account.student_lifecycle_status,
  );
  const busy =
    disable.isPending || enable.isPending || updateLifecycle.isPending;

  function beginIdentity() {
    setIdentity({
      institutional_id: account.institutional_id,
      first_name: account.first_name,
      middle_name: account.middle_name,
      last_name: account.last_name,
      suffix: account.suffix,
    });
    action.setError(null);
    setIdentityOpen(true);
  }

  async function saveIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await action.run(
      () => updateIdentity.mutateAsync({ userId: account.id, data: identity }),
      "Identity changes could not be saved.",
      () => setIdentityOpen(false),
    );
    if (!response) return;
    setIdentityOpen(false);
    await invalidate();
    action.setNotice("Identity updated.");
  }

  async function stageEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requested = newEmail.trim();
    const response = await action.run(
      () =>
        changeEmail.mutateAsync({
          userId: account.id,
          data: {
            new_email: requested,
            ...(isTurnstileConfigured ? { turnstile_token: token } : {}),
          },
        }),
      "Verification could not be sent to the proposed email.",
      () => setEmailOpen(false),
    );
    setToken(null);
    setTurnstileReset((value) => value + 1);
    if (!response) return;
    setEmailOpen(false);
    setStagedEmail(requested);
    action.setNotice(
      "A verification code was sent to the proposed new email address. The current sign-in email remains unchanged until the account holder confirms the new address.",
    );
  }

  async function confirmAction() {
    const kind = confirm;
    if (!kind) return;
    const selectedLifecycle = lifecycle;
    if (kind === "lifecycle" && !selectedLifecycle) return;
    const response = await action.run(
      () => {
        if (kind === "disable")
          return disable.mutateAsync({ userId: account.id });
        if (kind === "enable")
          return enable.mutateAsync({ userId: account.id });
        if (!selectedLifecycle)
          throw new Error("Select a Student lifecycle status.");
        return updateLifecycle.mutateAsync({
          userId: account.id,
          data: { status: selectedLifecycle },
        });
      },
      kind === "lifecycle"
        ? "Student lifecycle could not be updated."
        : "Account status could not be changed.",
      () => setConfirm(null),
    );
    if (!response) return;
    setConfirm(null);
    await invalidate();
    action.setNotice(
      kind === "disable"
        ? "Account disabled."
        : kind === "enable"
          ? "Account enabled."
          : "Student lifecycle updated.",
    );
  }

  return (
    <div className="space-y-9">
      <section aria-labelledby="identity-heading">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2
            id="identity-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Identity
          </h2>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={beginIdentity}>
              Edit identity
            </Button>
            <Button
              variant="secondary"
              disabled={!account.is_active}
              onClick={() => {
                setNewEmail("");
                action.setError(null);
                setEmailOpen(true);
              }}
            >
              Change sign-in email
            </Button>
          </div>
        </div>
        <dl className="mt-4 grid gap-4 border-t border-border pt-5 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted">Institutional ID</dt>
            <dd className="mt-1 font-medium text-ink">
              {account.institutional_id || "Not set"}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Name</dt>
            <dd className="mt-1 font-medium text-ink">{account.full_name}</dd>
          </div>
          <div>
            <dt className="text-muted">Current sign-in email</dt>
            <dd className="mt-1 break-all font-medium text-ink">
              {account.email}
            </dd>
          </div>
        </dl>
        {stagedEmail ? (
          <p
            role="status"
            className="mt-4 border-l-2 border-support px-3 text-sm leading-6 text-ink"
          >
            Verification required for {stagedEmail}. The current email remains
            unchanged until the account holder confirms the proposed address.
          </p>
        ) : null}
        {!account.is_active ? (
          <p className="mt-3 text-sm text-muted">
            Enable this account before requesting a sign-in email change.
          </p>
        ) : null}
      </section>

      <section aria-labelledby="status-heading">
        <h2
          id="status-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Account status
        </h2>
        <dl className="mt-4 grid gap-4 border-t border-border pt-5 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-muted">Access</dt>
            <dd className="mt-1 font-medium text-ink">
              {account.is_active ? "Active" : "Disabled"}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Password</dt>
            <dd className="mt-1 font-medium text-ink">
              {account.password_configured ? "Configured" : "Not configured"}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Email</dt>
            <dd className="mt-1 font-medium text-ink">
              {account.email_verified ? "Verified" : "Not verified"}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Created</dt>
            <dd className="mt-1 font-medium text-ink">
              {formatAccountDate(account.created_at)}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Updated</dt>
            <dd className="mt-1 font-medium text-ink">
              {formatAccountDate(account.updated_at)}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Email verified</dt>
            <dd className="mt-1 font-medium text-ink">
              {formatAccountDate(account.email_verified_at)}
            </dd>
          </div>
        </dl>
        <div className="mt-5">
          {account.is_active ? (
            self ? (
              <p className="text-sm text-muted">
                You cannot disable your own account from administrative account
                management.
              </p>
            ) : (
              <Button variant="danger" onClick={() => setConfirm("disable")}>
                Disable account
              </Button>
            )
          ) : (
            <Button variant="secondary" onClick={() => setConfirm("enable")}>
              Enable account
            </Button>
          )}
        </div>
      </section>

      {account.role === RoleCode.STUDENT ? (
        <section aria-labelledby="lifecycle-heading">
          <h2
            id="lifecycle-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Student lifecycle
          </h2>
          <p className="mt-3 text-sm text-muted">
            Current status:{" "}
            {account.student_lifecycle_status
              ? lifecycleLabels[account.student_lifecycle_status]
              : "Not set"}
          </p>
          {self ? (
            <p className="mt-3 text-sm text-muted">
              You cannot change your own Student lifecycle through
              administrative account management.
            </p>
          ) : (
            <div className="mt-4 flex flex-wrap items-end gap-3">
              <div>
                <Label htmlFor="student-lifecycle">New status</Label>
                <select
                  id="student-lifecycle"
                  className="mt-2 min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm"
                  value={lifecycle ?? ""}
                  onChange={(event) =>
                    setLifecycle(
                      lifecycles.find(
                        (status) => status === event.target.value,
                      ) ?? null,
                    )
                  }
                >
                  <option value="" disabled>
                    Select status
                  </option>
                  {lifecycles.map((status) => (
                    <option key={status} value={status}>
                      {lifecycleLabels[status]}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                variant="secondary"
                disabled={
                  !lifecycle || lifecycle === account.student_lifecycle_status
                }
                onClick={() => setConfirm("lifecycle")}
              >
                Update lifecycle
              </Button>
            </div>
          )}
        </section>
      ) : null}

      <ManagedActionFeedback action={action} />
      <Dialog
        open={identityOpen}
        onOpenChange={(open) => {
          if (!updateIdentity.isPending) setIdentityOpen(open);
        }}
      >
        <DialogContent>
          <DialogTitle>Edit identity</DialogTitle>
          <DialogDescription>
            Update the managed account&apos;s institutional identity. Sign-in
            email is changed separately.
          </DialogDescription>
          <form
            className="mt-6 space-y-4"
            onSubmit={(event) => void saveIdentity(event)}
          >
            {[
              ["institutional_id", "Institutional ID"],
              ["first_name", "First name"],
              ["middle_name", "Middle name"],
              ["last_name", "Last name"],
              ["suffix", "Suffix"],
            ].map(([key, label]) => (
              <div key={key} className="grid gap-2">
                <Label htmlFor={`identity-${key}`}>{label}</Label>
                <Input
                  id={`identity-${key}`}
                  value={identity[key as keyof IdentityUpdateRequest] ?? ""}
                  required={key === "first_name" || key === "last_name"}
                  onChange={(event) =>
                    setIdentity((current) => ({
                      ...current,
                      [key]: event.target.value,
                    }))
                  }
                />
              </div>
            ))}
            {action.error ? (
              <p role="alert" className="text-sm text-danger">
                {action.error}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                disabled={updateIdentity.isPending}
                onClick={() => setIdentityOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateIdentity.isPending}>
                {updateIdentity.isPending ? "Saving changes…" : "Save changes"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={emailOpen}
        onOpenChange={(open) => {
          if (!changeEmail.isPending) setEmailOpen(open);
        }}
      >
        <DialogContent>
          <DialogTitle>Change sign-in email</DialogTitle>
          <DialogDescription>
            Verification goes to the proposed new mailbox. The account holder
            must confirm the change.
          </DialogDescription>
          <form
            className="mt-6 space-y-4"
            onSubmit={(event) => void stageEmail(event)}
          >
            <p className="text-sm text-muted">
              Current email:{" "}
              <span className="font-semibold text-ink">{account.email}</span>
            </p>
            <div className="grid gap-2">
              <Label htmlFor="managed-new-email">New email</Label>
              <Input
                id="managed-new-email"
                type="email"
                required
                value={newEmail}
                onChange={(event) => setNewEmail(event.target.value)}
              />
            </div>
            <TurnstileWidget
              action="email_otp"
              onTokenChange={setToken}
              resetKey={turnstileReset}
            />
            {action.error ? (
              <p role="alert" className="text-sm text-danger">
                {action.error}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                disabled={changeEmail.isPending}
                onClick={() => setEmailOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={
                  changeEmail.isPending || (isTurnstileConfigured && !token)
                }
              >
                {changeEmail.isPending
                  ? "Sending verification…"
                  : "Send verification"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
      <AlertDialog
        open={confirm !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setConfirm(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>
            {confirm === "disable"
              ? `Disable ${accountName(account)}'s account?`
              : confirm === "enable"
                ? `Enable ${accountName(account)}'s account?`
                : `Update ${accountName(account)}'s Student lifecycle?`}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {confirm === "disable"
              ? "The account will no longer be able to sign in. Existing authentication state will be invalidated."
              : confirm === "enable"
                ? "This restores account access. Password, email verification, and MFA states remain separate."
                : lifecycle === StudentLifecycleCode.CURRENT
                  ? "Change the Student lifecycle to Current. Current-student workflows such as Individual Inventory, Appointment booking, and Routine Interviews become available again. Sign-in and existing records are not affected."
                  : `Change the Student lifecycle to ${lifecycle ? lifecycleLabels[lifecycle] : "the selected status"}. The Student will no longer be able to start or update current-student workflows such as Individual Inventory, Appointment booking, Routine Interviews, and Exit Interviews. Sign-in and historical records remain available.`}
          </AlertDialogDescription>
          {action.error ? (
            <p role="alert" className="mt-3 text-sm text-danger">
              {action.error}
            </p>
          ) : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={busy}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant={confirm === "disable" ? "danger" : "primary"}
              disabled={busy}
              onClick={() => void confirmAction()}
            >
              {busy
                ? confirm === "disable"
                  ? "Disabling…"
                  : confirm === "enable"
                    ? "Enabling…"
                    : "Updating lifecycle…"
                : confirm === "disable"
                  ? "Disable account"
                  : confirm === "enable"
                    ? "Enable account"
                    : "Update lifecycle"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

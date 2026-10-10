"use client";

import { useState } from "react";
import {
  Check,
  CircleAlert,
  Laptop,
  MonitorSmartphone,
  Smartphone,
  Trash2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  friendlyAuthError,
  getApiErrorCode,
} from "@/features/auth/utils/errors";
import type { SessionSummary, TrustedSessionSummary } from "@/lib/api/generated/model";

export type SecurityConfirmationRequest = {
  title: string;
  description: string;
  confirmLabel: string;
  run: () => Promise<void>;
};

export type RequestSecurityConfirmation = (
  request: SecurityConfirmationRequest,
) => void;

export function securityError(error: unknown, fallback: string) {
  const code = getApiErrorCode(error);

  if (code === "recent_mfa_required" || code === "totp_step_up_required") {
    return "Confirm two-step verification before continuing with this change.";
  }

  if (code === "invalid_mfa_code" || code === "mfa_verification_failed") {
    return "That verification code didn’t work. Check the latest code and try again.";
  }

  return friendlyAuthError(error, fallback);
}

export function formatSecurityDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function SecuritySectionHeading({
  description,
  icon: Icon,
  title,
}: {
  description: string;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
        <Icon aria-hidden="true" className="size-5" />
      </div>
      <div>
        <h2 className="font-heading text-2xl font-bold">{title}</h2>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      </div>
    </div>
  );
}

export function SecurityMessage({
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
      {error ? <CircleAlert aria-hidden="true" /> : <Check aria-hidden="true" />}
      <AlertDescription>{error ?? message}</AlertDescription>
    </Alert>
  );
}

function DeviceIcon({ userAgent }: { userAgent: string | null }) {
  const value = userAgent?.toLowerCase() ?? "";

  if (value.includes("mobile") || value.includes("android") || value.includes("iphone")) {
    return <Smartphone aria-hidden="true" className="size-5" />;
  }

  if (value.includes("safari") || value.includes("chrome") || value.includes("firefox")) {
    return <Laptop aria-hidden="true" className="size-5" />;
  }

  return <MonitorSmartphone aria-hidden="true" className="size-5" />;
}

export function SessionRow({
  session,
  onRevoke,
}: {
  session: SessionSummary;
  onRevoke: (session: SessionSummary) => void;
}) {
  return (
    <li className="flex flex-col gap-4 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-card text-[var(--compass-brand-maroon)]">
          <DeviceIcon userAgent={session.user_agent_summary} />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{session.user_agent_summary || "Browser session"}</p>
            {session.is_current ? <Badge variant="secondary">This device</Badge> : null}
          </div>
          <dl className="mt-2 grid gap-x-5 gap-y-1 text-xs leading-5 text-muted-foreground sm:grid-cols-2">
            <div>
              <dt className="inline font-semibold">Last active: </dt>
              <dd className="inline">{formatSecurityDate(session.last_used_at)}</dd>
            </div>
            <div>
              <dt className="inline font-semibold">Signed in: </dt>
              <dd className="inline">{formatSecurityDate(session.created_at)}</dd>
            </div>
            <div>
              <dt className="inline font-semibold">IP address: </dt>
              <dd className="inline">{session.last_ip_address || session.initial_ip_address || "Not available"}</dd>
            </div>
            <div>
              <dt className="inline font-semibold">Expires: </dt>
              <dd className="inline">{formatSecurityDate(session.expires_at)}</dd>
            </div>
          </dl>
        </div>
      </div>
      {!session.is_current ? (
        <Button type="button" variant="outline" size="sm" onClick={() => onRevoke(session)}>
          <Trash2 aria-hidden="true" />
          Sign out
        </Button>
      ) : null}
    </li>
  );
}

export function TrustedBrowserRow({
  session,
  onRevoke,
}: {
  session: TrustedSessionSummary;
  onRevoke: (session: TrustedSessionSummary) => void;
}) {
  return (
    <li className="flex flex-col gap-4 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-card text-[var(--compass-brand-maroon)]">
          <DeviceIcon userAgent={session.user_agent_summary} />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{session.user_agent_summary || "Trusted browser"}</p>
            {session.is_current ? <Badge variant="secondary">This device</Badge> : null}
          </div>
          <dl className="mt-2 grid gap-x-5 gap-y-1 text-xs leading-5 text-muted-foreground sm:grid-cols-2">
            <div>
              <dt className="inline font-semibold">Last active: </dt>
              <dd className="inline">{formatSecurityDate(session.last_used_at)}</dd>
            </div>
            <div>
              <dt className="inline font-semibold">Trusted until: </dt>
              <dd className="inline">{formatSecurityDate(session.expires_at)}</dd>
            </div>
            <div>
              <dt className="inline font-semibold">IP address: </dt>
              <dd className="inline">{session.last_ip_address || session.created_ip_address || "Not available"}</dd>
            </div>
          </dl>
        </div>
      </div>
      {!session.is_current ? (
        <Button type="button" variant="outline" size="sm" onClick={() => onRevoke(session)}>
          <Trash2 aria-hidden="true" />
          Remove trust
        </Button>
      ) : null}
    </li>
  );
}

export function SecurityConfirmationDialog({
  onOpenChange,
  request,
}: {
  onOpenChange: (open: boolean) => void;
  request: SecurityConfirmationRequest | null;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!request) {
    return null;
  }

  const currentRequest = request;

  async function run() {
    setError(null);
    setPending(true);
    try {
      await currentRequest.run();
      onOpenChange(false);
    } catch (caught) {
      setError(securityError(caught, "That action could not be completed. Please try again."));
    } finally {
      setPending(false);
    }
  }

  return (
    <AlertDialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) {
          onOpenChange(false);
        }
      }}
    >
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogTitle>{currentRequest.title}</AlertDialogTitle>
          <AlertDialogDescription>{currentRequest.description}</AlertDialogDescription>
        </AlertDialogHeader>
        {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={pending}
            onClick={(event) => {
              event.preventDefault();
              void run();
            }}
          >
            {pending ? "Working…" : currentRequest.confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

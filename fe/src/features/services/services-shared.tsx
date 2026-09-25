"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { hasServicesWorkspace } from "@/features/services/services-access";
import {
  CompassApiError,
  readApiErrorCode,
  readApiErrorMessage,
} from "@/lib/api/errors";

const knownErrors: Record<string, string> = {
  permission_denied: "You do not have permission to use this Services action.",
  service_not_found: "The requested Service is no longer available.",
  service_catalog_conflict:
    "The Service configuration conflicts with the current Service Catalog rules.",
  invalid_service_catalog_request:
    "The Service request contains a value that is not accepted by the Service Catalog.",
  recent_mfa_required: "Recent authenticator verification is required.",
};

export function servicesErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  const backendMessage = readApiErrorMessage(error.body);
  if (
    code === "service_catalog_conflict" ||
    code === "invalid_service_catalog_request" ||
    code === "service_not_found"
  ) {
    return backendMessage ?? knownErrors[code] ?? fallback;
  }
  return (code && knownErrors[code]) || backendMessage || fallback;
}

export function ServicesGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return hasServicesWorkspace(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Services unavailable">
      Your current access does not include Service Catalog management.
    </WorkspaceUnavailable>
  );
}

export function useServicesAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [afterStepUp, setAfterStepUp] = useState<(() => void) | null>(null);

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
    options?: {
      onStepUpRequired?: () => void;
      onStepUpVerified?: () => void;
    },
  ): Promise<T | undefined> {
    setError(null);
    setNotice(null);
    try {
      return await operation();
    } catch (caught) {
      const code =
        caught instanceof CompassApiError
          ? readApiErrorCode(caught.body)
          : undefined;
      if (code === "recent_mfa_required") {
        options?.onStepUpRequired?.();
        setAfterStepUp(() => options?.onStepUpVerified ?? null);
        setNotice("Verify your authenticator, then submit the action again.");
        setStepUpOpen(true);
      } else {
        setError(servicesErrorMessage(caught, fallback));
      }
      return undefined;
    }
  }

  const messages = (
    <>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="mt-4 text-sm text-success">
          {notice}
        </p>
      ) : null}
    </>
  );

  const stepUpDialog = (
    <StepUpDialog
      open={stepUpOpen}
      onOpenChange={setStepUpOpen}
      onVerified={() => {
        setNotice("Verification complete. Submit the action again to continue.");
        const resume = afterStepUp;
        setAfterStepUp(null);
        resume?.();
      }}
    />
  );

  return {
    error,
    notice,
    setError,
    setNotice,
    run,
    messages,
    stepUpDialog,
  };
}

export const servicesSelectClass =
  "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function ServicesPageHeading({
  title,
  action,
  backHref,
  backLabel,
}: {
  title: string;
  action?: ReactNode;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <div>
      {backHref ? (
        <Link
          href={backHref}
          className="mb-5 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          ← {backLabel ?? "Services"}
        </Link>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
          {title}
        </h1>
        {action}
      </div>
    </div>
  );
}

export function ServicesStatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold " +
        (active
          ? "border-success/30 bg-success/10 text-success"
          : "border-border bg-surface-muted text-muted")
      }
    >
      {active ? "Active" : "Inactive"}
    </span>
  );
}

export function ServicesSearchField() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current = (searchParams.get("search") ?? "").slice(0, 160);
  const [value, setValue] = useState(current);

  useEffect(() => {
    if (value === current) return;
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams.toString());
      const trimmed = value.trim();
      if (trimmed) next.set("search", trimmed);
      else next.delete("search");
      next.delete("page");
      const query = next.toString();
      router.replace(query ? pathname + "?" + query : pathname, {
        scroll: false,
      });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [current, pathname, router, searchParams, value]);

  return (
    <div className="min-w-0 flex-1">
      <Label htmlFor="services-search">Search Services</Label>
      <div className="relative mt-2">
        <Search
          size={18}
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-3 text-muted"
        />
        <Input
          id="services-search"
          className="pl-10"
          maxLength={160}
          placeholder="Search by Service name or code"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
      </div>
    </div>
  );
}

export function ServicesQueryError({
  error,
  fallback,
  onRetry,
}: {
  error: unknown;
  fallback: string;
  onRetry: () => void;
}) {
  return (
    <div role="alert" className="border-y border-border py-6">
      <p className="text-sm text-danger">
        {servicesErrorMessage(error, fallback)}
      </p>
      <Button variant="secondary" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export function ServicesListSkeleton() {
  return (
    <div className="mt-6 space-y-3" aria-busy="true">
      {Array.from({ length: 5 }, (_, index) => (
        <Skeleton key={index} className="h-24 w-full" />
      ))}
      <p className="sr-only">Loading Services…</p>
    </div>
  );
}

export function ServicesDetailSkeleton() {
  return (
    <div className="space-y-7" aria-busy="true">
      <Skeleton className="h-12 w-72 max-w-full" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-36 w-full" />
      <p className="sr-only">Loading Service…</p>
    </div>
  );
}

export function replaceServicesQueryParam(
  pathname: string,
  searchParams: URLSearchParams,
  key: string,
  value: string,
  resetPage = true,
): string {
  const next = new URLSearchParams(searchParams.toString());
  if (value) next.set(key, value);
  else next.delete(key);
  if (resetPage) next.delete("page");
  const query = next.toString();
  return query ? pathname + "?" + query : pathname;
}
